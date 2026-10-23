
"""Wake-word detection engines for multimedia voice control."""

from abc import ABC, abstractmethod
import logging
import threading
import time
from typing import Optional, Tuple

import speech_recognition as sr

from voice_control.config import VoiceControlConfig

logger = logging.getLogger(__name__)


class BaseWakeWordEngine(ABC):
    """Abstract interface for wake-word detection backends."""

    @abstractmethod
    def process_chunk(self, chunk: bytes) -> Tuple[bool, float]:
        raise NotImplementedError

    @abstractmethod
    def reset(self) -> None:
        raise NotImplementedError


class AcousticPatternEngine(BaseWakeWordEngine):
    """Recognize the configured wake phrase in background audio windows."""

    def __init__(self, config: Optional[VoiceControlConfig] = None):
        self.config = config or VoiceControlConfig()
        self.target_phrase = self.config.wake_word.lower().strip()
        self.wake_marker = b"WAKE_WORD_MARKER_HEY_MEDIA"

        self.recognizer = sr.Recognizer()
        self.bytes_per_second = (
            self.config.sample_rate * self.config.bytes_per_sample
        )
        self.window_seconds = 2.0
        self.check_interval_seconds = 0.8
        self.max_buffer_seconds = 3.0

        self._buffer = bytearray()
        self._lock = threading.Lock()
        self._last_check = 0.0
        self._last_detection = 0.0
        self._pending = False
        self._detected = False
        self._worker = None

    def reset(self) -> None:
        with self._lock:
            self._buffer.clear()
            self._detected = False
            self._last_check = 0.0
            self._last_detection = 0.0

    def _recognize(self, raw_audio: bytes) -> None:
        """Run network recognition outside the microphone callback."""
        try:
            audio = sr.AudioData(
                raw_audio,
                self.config.sample_rate,
                self.config.sample_width,
            )
            transcript = self.recognizer.recognize_google(
                audio, language="en-IN"
            ).lower().strip()
            transcript = " ".join(transcript.split())
            logger.info("Wake-word recognizer heard: %s", transcript)

            # Accept the wake phrase when it appears as a complete phrase.
            import re
            pattern = r"(?<!\w)" + re.escape(self.target_phrase) + r"(?!\w)"
            if re.search(pattern, transcript):
                with self._lock:
                    self._detected = True

        except sr.UnknownValueError:
            logger.debug("Speech was not understood as a wake phrase.")
        except sr.RequestError as exc:
            logger.warning("Google wake-word recognition failed: %s", exc)
        except Exception:
            logger.exception("Unexpected wake-word recognition error")
        finally:
            with self._lock:
                self._pending = False

    def process_chunk(self, chunk: bytes) -> Tuple[bool, float]:
        if not chunk:
            return False, 0.0

        if self.wake_marker in chunk:
            return True, 0.98

        now = time.monotonic()

        with self._lock:
            self._buffer.extend(chunk)
            max_bytes = int(self.max_buffer_seconds * self.bytes_per_second)
            if len(self._buffer) > max_bytes:
                del self._buffer[:-max_bytes]

            if self._detected:
                self._detected = False
                self._last_detection = now
                return True, 0.95

            required_bytes = int(self.window_seconds * self.bytes_per_second)
            if len(self._buffer) < required_bytes:
                return False, 0.0

            if self._pending or now - self._last_check < self.check_interval_seconds:
                return False, 0.0

            self._last_check = now
            self._pending = True
            snapshot = bytes(self._buffer[-required_bytes:])

            self._worker = threading.Thread(
                target=self._recognize,
                args=(snapshot,),
                daemon=True,
            )
            self._worker.start()

        return False, 0.0


class SimulatedEngine(BaseWakeWordEngine):
    """Deterministic engine for automated tests."""

    def __init__(self, default_confidence: float = 0.95):
        self.default_confidence = default_confidence
        self._triggered = False
        self._audio_signature_trigger = b"__TRIGGER_WAKE_WORD__"

    def arm_trigger(self) -> None:
        self._triggered = True

    def reset(self) -> None:
        self._triggered = False

    def process_chunk(self, chunk: bytes) -> Tuple[bool, float]:
        if self._triggered or (
            chunk and self._audio_signature_trigger in chunk
        ):
            self._triggered = False
            return True, self.default_confidence
        return False, 0.0
