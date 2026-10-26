"""
Integrated Sprint 1 runtime: wake word -> one command -> validation -> media
action -> feedback (Architecture 2.3 pipeline, Sequence Diagrams 1 and 2).

One SessionManager instance is shared by the WakeWordDetector and the
SecurityValidator, and every command carries the active session token as its
session_id. A command is executed only if it is fully recognized while that
session is still valid; the session closes after one command (or when the
listening window runs out).

``process_chunk`` is synchronous and deterministic so the whole flow can be
tested by feeding audio chunks; ``run`` wires it to the live microphone.

Sprint 2 additions:
- Timing log (NFR-1, US-11): every command logs the time from the end of the
  user's speech to the end of the media action, and ``run`` prints a summary.
- Microphone privacy control (US-16): ``set_muted`` / ``toggle_mute``; in
  ``run``, typing ``m`` + Enter turns the microphone off and on. While muted the
  audio stream is stopped and nothing is processed.
"""

from collections import deque
import logging
import queue
import sys
import threading
import time
from typing import Callable, Deque, Dict, Optional

from voice_control.audio.capture import AudioCaptureComponent
from voice_control.audio.segmenter import UtteranceSegmenter
from voice_control.config import VoiceControlConfig
from voice_control.control.command_mapper import map_command
from voice_control.control.executor import CommandExecutor
from voice_control.detector.engine import BaseWakeWordEngine, TranscriptWakeWordEngine
from voice_control.detector.state import SessionManager
from voice_control.detector.wake_word import WakeWordDetector
from voice_control.feedback.indicator import FeedbackModule
from voice_control.models.command import ExecutionResult, SystemState
from voice_control.recognition.transcriber import BaseTranscriber
from voice_control.security.error_handler import ErrorHandler, UnrecognizedCommandError
from voice_control.security.validator import SecurityValidator

logger = logging.getLogger(__name__)


class ListeningWindowExpired(Exception):
    """The user started a command but the listening window closed first."""


class VoiceAssistant:
    def __init__(
        self,
        transcriber: BaseTranscriber,
        actions: Dict[str, Callable[[], bool]],
        config: Optional[VoiceControlConfig] = None,
        wake_engine: Optional[BaseWakeWordEngine] = None,
        feedback: Optional[FeedbackModule] = None,
    ):
        self.config = config or VoiceControlConfig()
        self.transcriber = transcriber
        self.feedback = feedback or FeedbackModule()
        self.error_handler = ErrorHandler(self.feedback)

        # The single shared session manager (detector + validator).
        self.sessions = SessionManager(self.config.listening_window_seconds)
        self.sessions.register_state_callback(self.feedback.on_state_change)

        self.detector = WakeWordDetector(
            config=self.config,
            engine=wake_engine or TranscriptWakeWordEngine(transcriber, self.config),
            session_manager=self.sessions,
        )
        self.validator = SecurityValidator(self.sessions, self.config.min_command_confidence)
        self.executor = CommandExecutor(
            self.validator, actions, self.feedback, self.error_handler
        )
        self.command_segmenter = UtteranceSegmenter(self.config)

        self._session_token: Optional[str] = None
        # Bounded history so a long run (US-10) does not grow memory.
        self.results: Deque[ExecutionResult] = deque(maxlen=200)
        self.latencies_ms: Deque[float] = deque(maxlen=200)
        self._speech_end: Optional[float] = None

        # US-16 microphone privacy control
        self._muted = False
        self._controls: "queue.Queue[str]" = queue.Queue()

    # ------------------------------------------------------------------ flow
    def process_chunk(self, chunk: bytes) -> Optional[ExecutionResult]:
        """Feed one audio chunk. Returns an ExecutionResult when a command finished."""
        if self._muted:
            return None  # US-16: nothing is processed while the microphone is off

        if not self._session_is_open():
            if self.detector.detect_wake_word(chunk):
                self._session_token = self.detector.active_session_token
                self.command_segmenter.reset()
                # "Hey Media play" said in one breath: the command is already here.
                trailing = getattr(self.detector.engine, "trailing_text", "")
                if trailing and map_command(trailing) is not None:
                    confidence = getattr(self.detector.engine, "last_confidence", 1.0)
                    self._mark_speech_end(getattr(self.detector.engine, "segmenter", None))
                    return self._execute_text(trailing, confidence)
                logger.info("Wake word heard. Say a command within %.1fs.",
                            self.config.listening_window_seconds)
            return None

        utterance = self.command_segmenter.feed(chunk)
        if utterance is None:
            return None
        self._mark_speech_end(self.command_segmenter)
        return self._handle_command(utterance)

    def tick(self) -> None:
        """Call when no audio arrived, so an expired window is still noticed."""
        self._session_is_open()

    def _session_is_open(self) -> bool:
        state = self.sessions.check_and_update()
        if state == SystemState.LISTENING and self._session_token:
            return True
        if self._session_token is not None:
            # The window ran out before a complete command arrived.
            if self.command_segmenter.in_speech:
                self.error_handler.handle_error(
                    ListeningWindowExpired("Command not finished inside the listening window")
                )
            else:
                logger.info("Listening window closed with no command.")
            self._end_session()
        return False

    def _handle_command(self, utterance: bytes) -> ExecutionResult:
        try:
            transcript = self.transcriber.transcribe(utterance)
        except Exception as exc:
            self.error_handler.handle_error(exc)
            self._end_session()
            return self._record(
                ExecutionResult(False, f"recognition failed: {exc}")
            )

        if transcript is None:
            print("Didn't catch that, please repeat")
            self.error_handler.handle_error(
                UnrecognizedCommandError("Speech was not understood")
            )
            self._end_session()
            return self._record(
                ExecutionResult(False, "not understood")
            )

        return self._execute_text(
            transcript.text, transcript.confidence
        )

    def _execute_text(self, text: str, confidence: float) -> ExecutionResult:
        """Map recognized text to a command and run it inside the current session."""
        token = self._session_token
        try:
            command = map_command(text, confidence, session_id=token)
            if command is None:
                self.error_handler.handle_error(
                    UnrecognizedCommandError(f"'{text}' is not a supported command")
                )
                return self._record(ExecutionResult(False, f"unsupported: {text}"))

            logger.info("Heard '%s' -> %s (confidence %.2f)",
                        text, command.type, command.confidence)
            # The validator re-checks the session now, after recognition, so a
            # command that finished after the window closed is rejected.
            result = self.executor.execute(command)
            self._log_timing(command.type, result)
            return self._record(result)
        finally:
            self._end_session()  # one command per wake word

    # ---------------------------------------------------------------- timing
    def _mark_speech_end(self, segmenter) -> None:
        """Remember when the user stopped speaking (NFR-1 is measured from here)."""
        silence = getattr(segmenter, "last_trailing_silence_seconds", 0.0) or 0.0
        self._speech_end = time.perf_counter() - silence

    def _log_timing(self, command_type: str, result: ExecutionResult) -> None:
        if self._speech_end is None:
            return
        elapsed_ms = (time.perf_counter() - self._speech_end) * 1000.0
        self._speech_end = None
        self.latencies_ms.append(elapsed_ms)
        limit_ms = 1000 if command_type in ("volume up", "volume down") else 2000
        logger.info(
            "[TIMING] '%s' %s in %.0f ms (end of speech -> action; target < %d ms)%s",
            command_type,
            "executed" if result.success else "failed",
            elapsed_ms,
            limit_ms,
            "" if elapsed_ms < limit_ms else "  <-- SLOWER THAN TARGET",
        )

    def timing_summary(self) -> Optional[Dict[str, float]]:
        """Count, average and slowest command time so far (for the US-11 test log)."""
        if not self.latencies_ms:
            return None
        values = list(self.latencies_ms)
        return {
            "count": len(values),
            "average_ms": sum(values) / len(values),
            "max_ms": max(values),
        }

    # ------------------------------------------------------- privacy (US-16)
    @property
    def is_muted(self) -> bool:
        return self._muted

    def set_muted(self, muted: bool) -> None:
        """Turn listening off (muted=True) or back on. Safe to call repeatedly."""
        if muted == self._muted:
            return
        self._muted = muted
        if muted:
            self._end_session_if_open()  # an open listening window is cancelled
            self.feedback.notify("muted")
        else:
            self.command_segmenter.reset()
            self.detector.engine.reset()  # never act on audio from before the mute
            self.feedback.notify("unmuted")

    def toggle_mute(self) -> bool:
        """Flip the microphone state. Returns True when now muted."""
        self.set_muted(not self._muted)
        return self._muted

    def handle_control(self, text: str) -> bool:
        """Apply a typed control ('m', 'mute', 'unmute'). Returns True if it was one."""
        word = (text or "").strip().lower()
        if word in ("m", "mic"):
            self.toggle_mute()
        elif word in ("mute", "off"):
            self.set_muted(True)
        elif word in ("unmute", "on"):
            self.set_muted(False)
        else:
            return False
        return True

    def _end_session(self) -> None:
        self._session_token = None
        self.command_segmenter.reset()
        self.detector.engine.reset()
        if self.sessions.current_state != SystemState.IDLE:
            self.sessions.close_session()

    def _record(self, result: ExecutionResult) -> ExecutionResult:
        self.results.append(result)
        return result

    def _apply_controls(self, capture: AudioCaptureComponent, chunks: "queue.Queue[bytes]") -> None:
        """Apply typed controls on the main loop thread; start/stop the microphone."""
        while True:
            try:
                text = self._controls.get_nowait()
            except queue.Empty:
                break
            was_muted = self._muted
            if not self.handle_control(text):
                if text.strip():
                    print("Type m + Enter to turn the microphone off or on.")
                continue
            if self._muted and not was_muted:
                capture.stop_stream()       # the microphone is really closed
                _drain(chunks)
            elif was_muted and not self._muted:
                _drain(chunks)
                capture.start_stream()

    def _start_keyboard_listener(self) -> None:
        """Read typed controls from the Terminal without blocking the audio loop."""
        if sys.stdin is None or not sys.stdin.isatty():
            return

        def read_lines() -> None:
            for line in sys.stdin:
                self._controls.put(line)

        threading.Thread(target=read_lines, name="keyboard-controls", daemon=True).start()

    def _print_timing_summary(self) -> None:
        summary = self.timing_summary()
        if summary:
            print(
                f"Timing: {summary['count']:.0f} commands, average "
                f"{summary['average_ms']:.0f} ms, slowest {summary['max_ms']:.0f} ms "
                "(end of speech -> action)."
            )

    # ------------------------------------------------------------------ live
    def run(self, capture: Optional[AudioCaptureComponent] = None) -> int:
        """Listen on the microphone until Ctrl+C. Returns a process exit code."""
        capture = capture or AudioCaptureComponent(self.config, self.feedback)
        chunks: "queue.Queue[bytes]" = queue.Queue(maxsize=200)

        def enqueue(chunk: bytes) -> None:
            try:
                chunks.put_nowait(chunk)
            except queue.Full:  # processing fell behind; drop the oldest audio
                try:
                    chunks.get_nowait()
                except queue.Empty:
                    pass
                chunks.put_nowait(chunk)

        capture.register_callback(enqueue)
        capture.start_stream()
        if capture.is_suspended:
            print(f"[ERROR] Microphone unavailable: {capture.suspension_reason}")
            return 1

        print(f"Listening. Say '{self.config.wake_word}', then one of: "
              "play, pause, resume, next, previous, volume up, volume down.")
        print("Type m + Enter at any time to turn the microphone off or on.")
        self._start_keyboard_listener()
        try:
            while True:
                self._apply_controls(capture, chunks)
                if self._muted:
                    time.sleep(0.2)  # microphone closed; only typed controls matter
                    continue
                if capture.is_suspended or not capture.is_running:
                    # US-13: no commands without audio; retry the microphone.
                    self._end_session_if_open()
                    time.sleep(5.0)
                    capture.stop_stream()
                    capture.start_stream()
                    continue
                try:
                    chunk = chunks.get(timeout=0.2)
                except queue.Empty:
                    self.tick()
                    continue
                self.process_chunk(chunk)
        except KeyboardInterrupt:
            print("\nStopping voice assistant.")
            return 0
        finally:
            capture.stop_stream()
            self._print_timing_summary()

    def _end_session_if_open(self) -> None:
        if self._session_token is not None or self.sessions.current_state != SystemState.IDLE:
            self._end_session()

def _drain(chunks: "queue.Queue[bytes]") -> None:
    """Throw away queued audio (it was captured before a mute / unmute)."""
    while True:
        try:
            chunks.get_nowait()
        except queue.Empty:
            return
