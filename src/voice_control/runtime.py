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
"""

import logging
import queue
import time
from typing import Callable, Dict, List, Optional

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
        self.results: List[ExecutionResult] = []

    # ------------------------------------------------------------------ flow
    def process_chunk(self, chunk: bytes) -> Optional[ExecutionResult]:
        """Feed one audio chunk. Returns an ExecutionResult when a command finished."""
        if not self._session_is_open():
            if self.detector.detect_wake_word(chunk):
                self._session_token = self.detector.active_session_token
                self.command_segmenter.reset()
                logger.info("Wake word heard. Say a command within %.1fs.",
                            self.config.listening_window_seconds)
            return None

        utterance = self.command_segmenter.feed(chunk)
        if utterance is None:
            return None
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
        token = self._session_token
        try:
            try:
                transcript = self.transcriber.transcribe(utterance)
            except Exception as exc:
                self.error_handler.handle_error(exc)
                return self._record(ExecutionResult(False, f"recognition failed: {exc}"))

            if transcript is None:
                self.error_handler.handle_error(
                    UnrecognizedCommandError("Speech was not understood")
                )
                return self._record(ExecutionResult(False, "not understood"))

            command = map_command(transcript.text, transcript.confidence, session_id=token)
            if command is None:
                self.error_handler.handle_error(
                    UnrecognizedCommandError(f"'{transcript.text}' is not a supported command")
                )
                return self._record(ExecutionResult(False, f"unsupported: {transcript.text}"))

            logger.info("Heard '%s' -> %s (confidence %.2f)",
                        transcript.text, command.type, command.confidence)
            # The validator re-checks the session now, after recognition, so a
            # command that finished after the window closed is rejected.
            return self._record(self.executor.execute(command))
        finally:
            self._end_session()  # one command per wake word

    def _end_session(self) -> None:
        self._session_token = None
        self.command_segmenter.reset()
        self.detector.engine.reset()
        if self.sessions.current_state != SystemState.IDLE:
            self.sessions.close_session()

    def _record(self, result: ExecutionResult) -> ExecutionResult:
        self.results.append(result)
        return result

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
        try:
            while True:
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

    def _end_session_if_open(self) -> None:
        if self._session_token is not None or self.sessions.current_state != SystemState.IDLE:
            self._end_session()
