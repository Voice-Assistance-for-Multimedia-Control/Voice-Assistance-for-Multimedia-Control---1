"""
Audio Capture Component (Hardware Layer).
Architecture 2.2: Continuously samples audio from the microphone into
a rolling buffer for the Wake-Word Detector.
Architecture 3.4 & User Story US-13:
- Detects microphone initialization or access failures.
- An error indication is provided when audio input is unavailable.
- Suspends listening and blocks commands when audio input is faulted.
- Resumes listening once hardware input is restored.
"""

import logging
import threading
import time
from typing import Callable, Iterable, List, Optional, Tuple

from voice_control.audio.buffer import AudioBuffer
from voice_control.config import VoiceControlConfig
from voice_control.feedback.indicator import FeedbackModule
from voice_control.security.error_handler import MicrophoneUnavailableError

logger = logging.getLogger(__name__)


class AudioCaptureComponent:
    """
    Manages live microphone audio capture or streaming input into a rolling AudioBuffer.
    Detects hardware access faults, suspends listening on failure, and dispatches error events.
    """

    def __init__(
        self,
        config: Optional[VoiceControlConfig] = None,
        feedback_module: Optional[FeedbackModule] = None,
    ):
        self.config = config or VoiceControlConfig()
        self.feedback = feedback_module or FeedbackModule()
        self.buffer = AudioBuffer(
            max_bytes=self.config.buffer_max_bytes,
            sample_rate=self.config.sample_rate,
            bytes_per_sample=self.config.bytes_per_sample,
        )

        self._running = False
        self._healthy = True
        self._suspended = False
        self._suspension_reason: Optional[str] = None
        self._thread: Optional[threading.Thread] = None
        self._callbacks: List[Callable[[bytes], None]] = []
        self._error_callbacks: List[Callable[[Exception], None]] = []
        self._lock = threading.Lock()

    @staticmethod
    def check_microphone_availability() -> Tuple[bool, str]:
        """
        US-13 Acceptance Criterion 1:
        Detects microphone initialization or access failures before or during streaming.
        Returns:
            Tuple[bool, str]: (is_available, description_or_error_message)
        """
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            default_in = sd.default.device[0]

            if default_in is None or default_in < 0:
                # Search for any valid input device
                input_devs = [d for d in devices if d.get("max_input_channels", 0) > 0]
                if not input_devs:
                    return False, "No microphone or audio input device detected on the system."
                return True, f"Audio input available: {input_devs[0].get('name')}"

            dev_info = sd.query_devices(default_in, "input")
            return True, f"Default microphone available: {dev_info.get('name')}"

        except ImportError:
            # Check for PyAudio as alternative
            try:
                import pyaudio
                pa = pyaudio.PyAudio()
                count = pa.get_device_count()
                input_found = False
                for i in range(count):
                    info = pa.get_device_info_by_index(i)
                    if info.get("maxInputChannels", 0) > 0:
                        input_found = True
                        break
                pa.terminate()
                if input_found:
                    return True, "Audio input device detected via PyAudio."
                return False, "No recording input devices found via PyAudio."
            except Exception as e:
                return False, f"Audio driver interface error: {e}"

        except Exception as e:
            return False, f"Microphone access check failed: {e}"

    def register_callback(self, callback: Callable[[bytes], None]) -> None:
        """Register a subscriber callback that receives each incoming audio chunk."""
        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable[[bytes], None]) -> None:
        """Unregister a subscriber callback."""
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

    def register_error_callback(self, callback: Callable[[Exception], None]) -> None:
        """Register an error subscriber for hardware / capture faults (Architecture 3.4)."""
        with self._lock:
            self._error_callbacks.append(callback)

    def can_capture(self) -> bool:
        """
        US-13 Acceptance Criterion 3:
        Ensures the system does not process or execute commands without valid audio input.
        """
        with self._lock:
            return self._healthy and not self._suspended and self._running

    def suspend_stream(self, reason: str) -> None:
        """
        Suspend audio capture due to hardware fault or microphone disconnection.
        Provides user error indication (US-13 Criterion 2).
        """
        with self._lock:
            self._healthy = False
            self._suspended = True
            self._suspension_reason = reason

        logger.error(f"[HARDWARE FAULT] Audio stream suspended: {reason}")
        self.feedback.notify("mic_error")

        exc = MicrophoneUnavailableError(f"Microphone input suspended: {reason}")
        self._notify_error(exc)

    def resume_stream(self) -> None:
        """
        Resume audio capture once microphone input has been restored.
        """
        with self._lock:
            self._healthy = True
            self._suspended = False
            self._suspension_reason = None

        logger.info("[HARDWARE RECOVERY] Audio input stream restored to healthy state.")
        self.feedback.notify("ok")

    def feed_chunk(self, chunk: bytes) -> None:
        """
        Feed a raw audio chunk into the capture pipeline.
        Pushes to rolling buffer and dispatches to registered callbacks.
        Blocks chunk ingestion if the microphone is faulted/suspended (US-13).
        """
        if not self._healthy or self._suspended:
            logger.warning("Audio chunk discarded: microphone capture is suspended.")
            return

        if not chunk or len(chunk) == 0:
            return

        self.buffer.append(chunk)

        with self._lock:
            callbacks = list(self._callbacks)

        for cb in callbacks:
            try:
                cb(chunk)
            except Exception as e:
                logger.error(f"Error in audio frame callback: {e}", exc_info=True)

    def start_stream(self, stream_source: Optional[Iterable[bytes]] = None) -> None:
        """
        Start capturing audio in a background worker thread.
        If stream_source is provided (e.g. generator for testing), reads from it.
        Otherwise, attempts to bind to default microphone hardware.
        """
        if self._running:
            return

        # Pre-check microphone hardware access if capturing live
        if stream_source is None:
            available, msg = self.check_microphone_availability()
            if not available:
                self.suspend_stream(f"Initialization failure: {msg}")
                # Start in suspended state rather than crashing
                self._running = True
                return

        self._running = True
        self._healthy = True
        self._suspended = False

        if stream_source is not None:
            self._thread = threading.Thread(
                target=self._run_stream_source, args=(stream_source,), daemon=True
            )
        else:
            self._thread = threading.Thread(target=self._run_hardware_mic, daemon=True)

        self._thread.start()
        logger.info("AudioCaptureComponent started.")

    def stop_stream(self) -> None:
        """Stop capturing audio and join the worker thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None
        logger.info("AudioCaptureComponent stopped.")

    def _run_stream_source(self, stream: Iterable[bytes]) -> None:
        """Worker loop reading from an iterable stream (files, test generators)."""
        try:
            for chunk in stream:
                if not self._running:
                    break
                if self._suspended:
                    time.sleep(0.05)
                    continue
                self.feed_chunk(chunk)
        except Exception as e:
            self.suspend_stream(f"Stream read error: {e}")
        finally:
            self._running = False

    def _run_hardware_mic(self) -> None:
        """Attempt live capture via sounddevice or pyaudio."""
        try:
            import sounddevice as sd

            def audio_callback(indata, frames, time_info, status):
                if status:
                    logger.warning(f"SoundDevice status warning: {status}")
                if self._running and self._healthy and not self._suspended:
                    self.feed_chunk(bytes(indata))

            with sd.RawInputStream(
                samplerate=self.config.sample_rate,
                blocksize=self.config.chunk_size,
                channels=self.config.channels,
                dtype="int16",
                callback=audio_callback,
            ):
                while self._running:
                    time.sleep(0.05)

        except Exception as e:
            self.suspend_stream(f"Live hardware capture fault: {e}")
            self._running = False

    def _notify_error(self, err: Exception) -> None:
        with self._lock:
            handlers = list(self._error_callbacks)
        for h in handlers:
            try:
                h(err)
            except Exception:
                pass

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_healthy(self) -> bool:
        return self._healthy

    @property
    def is_suspended(self) -> bool:
        return self._suspended

    @property
    def suspension_reason(self) -> Optional[str]:
        return self._suspension_reason
