"""
Wake-Word Detector Component (Recognition Layer).
Implements the exact API from Architecture Specification Section 3.3:
    detect_wake_word(audio_chunk: bytes) -> bool

Functional Requirement FR-1:
    System enters active listening state within 1 second of wake word detection.
Security Requirement SR-1 & SO-1:
    Opens listening window only upon valid wake word; audio without wake word is ignored.
"""

from datetime import datetime, timezone
import logging
import time
from typing import Callable, List, Optional

from voice_control.config import VoiceControlConfig
from voice_control.detector.engine import AcousticPatternEngine, BaseWakeWordEngine
from voice_control.detector.state import SessionManager
from voice_control.models.command import SystemState

logger = logging.getLogger(__name__)


class WakeWordDetector:
    """
    Monitors streaming audio chunks for the defined wake word.
    On detection, opens a gated listening window and activates listening state.
    """

    def __init__(
        self,
        config: Optional[VoiceControlConfig] = None,
        engine: Optional[BaseWakeWordEngine] = None,
        session_manager: Optional[SessionManager] = None,
    ):
        self.config = config or VoiceControlConfig()
        self.engine = engine or AcousticPatternEngine(self.config)
        self.session_manager = session_manager or SessionManager(
            window_duration_seconds=self.config.listening_window_seconds
        )

        # Callbacks for wake-word events
        self._wake_callbacks: List[Callable[[str, float], None]] = []
        self._last_detection_timestamp: Optional[float] = None
        self._detection_latency: Optional[float] = None

    def register_wake_callback(self, callback: Callable[[str, float], None]) -> None:
        """Register callback for when wake word is detected: callback(session_token, confidence)."""
        self._wake_callbacks.append(callback)

    def detect_wake_word(self, audio_chunk: bytes) -> bool:
        """
        Architecture Specification 3.3 Core API:
            Function: detect_wake_word(audio_chunk)
            Parameters: audio_chunk: bytes
            Returns: bool – True if wake word present
            Notes: Called continuously on each incoming audio frame.

        On detection:
            - Transitions system to LISTENING state within 1 second (FR-1)
            - Opens a security-gated listening session window (SR-1)
            - Dispatches notification to registered subscribers.
        """
        start_time = time.perf_counter()

        # Update and check if previous listening window has expired
        self.session_manager.check_and_update()

        # Process audio frame with detection engine
        is_detected, confidence = self.engine.process_chunk(audio_chunk)

        if is_detected:
            # Measure processing latency to satisfy FR-1 (< 1.0s)
            self._detection_latency = time.perf_counter() - start_time
            self._last_detection_timestamp = time.time()

            # Open authorized session window (transitions state to LISTENING)
            session_token = self.session_manager.open_session()
            logger.info(
                f"Wake word detected ('{self.config.wake_word}', confidence={confidence:.2f}). "
                f"Active listening session: {session_token} (latency: {self._detection_latency*1000:.2f}ms)"
            )

            # Fire wake event callbacks
            for cb in self._wake_callbacks:
                try:
                    cb(session_token, confidence)
                except Exception as e:
                    logger.error(f"Error in wake callback: {e}", exc_info=True)

            return True

        return False

    @property
    def is_listening(self) -> bool:
        """Returns True if the system is currently in the active listening state."""
        return self.session_manager.current_state == SystemState.LISTENING

    @property
    def current_state(self) -> SystemState:
        """Get the current system state."""
        return self.session_manager.current_state

    @property
    def active_session_token(self) -> Optional[str]:
        """Returns the active session token, or None if in IDLE."""
        return self.session_manager.current_token

    @property
    def time_remaining_seconds(self) -> float:
        """Seconds remaining in the active listening window."""
        return self.session_manager.time_remaining_seconds

    @property
    def last_detection_latency(self) -> Optional[float]:
        """Processing latency of the most recent wake word detection in seconds."""
        return self._detection_latency

    def reset(self) -> None:
        """Reset the detector and engine state."""
        self.engine.reset()
        self.session_manager.close_session()
        self._last_detection_timestamp = None
        self._detection_latency = None
