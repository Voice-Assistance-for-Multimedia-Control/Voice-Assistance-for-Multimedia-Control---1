"""
Feedback / LED Module (Output Layer).
Implements the exact API from Architecture Specification Section 3.3:
    notify(status: 'ok' | 'error') -> None

SRS Requirement FR-10 & User Story US-09:
    Visible or audible acknowledgement (e.g. LED blink or log message) on every successful command.
    Distinct indication (e.g., short tone) when a command is rejected or fails.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
import sys
from typing import Callable, List, Optional

import numpy as np

from voice_control.models.command import SystemState

logger = logging.getLogger(__name__)


class LEDColor(str, Enum):
    OFF = "OFF"
    BLUE = "BLUE"      # Listening / Wake Word Detected
    GREEN = "GREEN"    # Command Success (OK)
    RED = "RED"        # Error / Command Rejection / Hardware Fault
    YELLOW = "YELLOW"  # Warning / Hardware Suspended


class ToneType(str, Enum):
    SUCCESS = "SUCCESS"          # Pleasant double chime (high frequency)
    REJECTION = "REJECTION"      # Low buzzing error tone
    HARDWARE_FAULT = "FAULT"     # Urgent warning pulse
    WAKE = "WAKE"                # Short rising chime


@dataclass
class FeedbackEvent:
    """Record of a visible/audible feedback occurrence."""
    status: str
    color: LEDColor
    message: str
    tone_type: Optional[ToneType] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tone_samples: Optional[bytes] = None


class FeedbackModule:
    """
    Console, audible tone, and hardware LED feedback driver.
    Signals listening state, successful execution, rejection errors, and hardware faults.
    """

    def __init__(self, hardware_pin: Optional[int] = None, enable_audio_tones: bool = True):
        self.hardware_pin = hardware_pin
        self.enable_audio_tones = enable_audio_tones
        self.current_color = LEDColor.OFF
        self.last_status: Optional[str] = None
        self.last_event: Optional[FeedbackEvent] = None
        self.feedback_history: List[FeedbackEvent] = []
        self._listeners: List[Callable[[FeedbackEvent], None]] = []

    def register_listener(self, listener: Callable[[FeedbackEvent], None]) -> None:
        """Register listener for feedback events (e.g. GUI, hardware GPIO, or test harness)."""
        self._listeners.append(listener)

    def synthesize_tone(self, tone_type: ToneType, sample_rate: int = 16000) -> bytes:
        """
        Synthesize distinctive PCM audio tones in pure NumPy (FR-10, US-09).
        Guarantees audible feedback works on any platform without requiring audio files.
        """
        if tone_type == ToneType.SUCCESS:
            # Ascending two-tone chime (587 Hz -> 880 Hz, D5 -> A5)
            t1 = np.linspace(0, 0.08, int(0.08 * sample_rate), False)
            t2 = np.linspace(0, 0.12, int(0.12 * sample_rate), False)
            tone1 = 0.5 * np.sin(2 * np.pi * 587.33 * t1)
            tone2 = 0.6 * np.sin(2 * np.pi * 880.00 * t2)
            audio = np.concatenate([tone1, tone2])
        elif tone_type == ToneType.REJECTION:
            # Low buzzing rejection tone (220 Hz descending to 180 Hz)
            t = np.linspace(0, 0.20, int(0.20 * sample_rate), False)
            freq = np.linspace(220, 180, len(t))
            audio = 0.6 * np.sign(np.sin(2 * np.pi * freq * t))  # Square wave buzz
        elif tone_type == ToneType.HARDWARE_FAULT:
            # Rapid warning pulse (440 Hz square wave pulses)
            t_pulse = np.linspace(0, 0.06, int(0.06 * sample_rate), False)
            t_silence = np.zeros(int(0.04 * sample_rate))
            pulse = 0.7 * np.sin(2 * np.pi * 440 * t_pulse)
            audio = np.concatenate([pulse, t_silence, pulse, t_silence, pulse])
        elif tone_type == ToneType.WAKE:
            # Quick bright chime (784 Hz, G5)
            t = np.linspace(0, 0.08, int(0.08 * sample_rate), False)
            audio = 0.5 * np.sin(2 * np.pi * 783.99 * t)
        else:
            audio = np.zeros(int(0.1 * sample_rate))

        # Apply short fade-out envelope to prevent click artifacts
        fade_len = int(0.01 * sample_rate)
        if len(audio) > fade_len:
            audio[-fade_len:] *= np.linspace(1.0, 0.0, fade_len)

        # Convert float [-1.0, 1.0] to 16-bit signed PCM
        pcm16 = (audio * 32767).astype(np.int16)
        return pcm16.tobytes()

    def play_tone(self, tone_type: ToneType) -> None:
        """Emit audible tone via system bell or speaker output."""
        if not self.enable_audio_tones:
            return

        # Always trigger terminal audible bell
        try:
            sys.stdout.write("\a")
            sys.stdout.flush()
        except Exception:
            pass

        # If sounddevice is available and functional, play the waveform
        try:
            import sounddevice as sd
            pcm_bytes = self.synthesize_tone(tone_type)
            samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            sd.play(samples, samplerate=16000, blocking=False)
        except Exception:
            # Headless or missing audio device gracefully handled
            pass

    def on_state_change(self, state: SystemState, token: Optional[str] = None) -> None:
        """Handle state change from SessionManager."""
        if state == SystemState.LISTENING:
            self._record_and_dispatch(
                status="wake",
                color=LEDColor.BLUE,
                message=f"[FEEDBACK] Wake word detected! System is now LISTENING (Token: {token})",
                tone_type=ToneType.WAKE,
            )
        elif state == SystemState.IDLE:
            self._record_and_dispatch(
                status="idle",
                color=LEDColor.OFF,
                message="[FEEDBACK] System returned to IDLE (Awaiting wake word).",
            )
        elif state == SystemState.PROCESSING:
            self._record_and_dispatch(
                status="processing",
                color=LEDColor.BLUE,
                message="[FEEDBACK] Processing recognized command...",
            )

    def notify(self, status: str) -> None:
        """
        Architecture 3.3 Core API: notify(status: 'ok' | 'error').
        Drives visible LED and audible tone output to the user (FR-10, US-09).
        """
        status_key = status.strip().lower()
        self.last_status = status_key

        if status_key in ("ok", "success"):
            self._record_and_dispatch(
                status="ok",
                color=LEDColor.GREEN,
                message="[FEEDBACK ✓] Command executed successfully.",
                tone_type=ToneType.SUCCESS,
            )
        elif status_key in ("error", "rejected", "fail", "failure"):
            self._record_and_dispatch(
                status="error",
                color=LEDColor.RED,
                message="[FEEDBACK ✗] Command rejected or execution failed.",
                tone_type=ToneType.REJECTION,
            )
        elif status_key in ("mic_error", "mic_unavailable", "hardware_fault"):
            self._record_and_dispatch(
                status="mic_error",
                color=LEDColor.RED,
                message="[FEEDBACK ⚠] Microphone unavailable or audio stream faulted.",
                tone_type=ToneType.HARDWARE_FAULT,
            )
        elif status_key == "muted":
            self._record_and_dispatch(
                status="muted",
                color=LEDColor.YELLOW,
                message="[FEEDBACK] Microphone OFF: not listening. Type m + Enter to turn it on.",
            )
        elif status_key == "unmuted":
            self._record_and_dispatch(
                status="unmuted",
                color=LEDColor.OFF,
                message="[FEEDBACK] Microphone ON: say 'hey media' to give a command.",
            )
        else:
            self._record_and_dispatch(
                status=status_key,
                color=LEDColor.OFF,
                message=f"[FEEDBACK] Status update: {status}",
            )

    def _record_and_dispatch(
        self,
        status: str,
        color: LEDColor,
        message: str,
        tone_type: Optional[ToneType] = None,
    ) -> None:
        self.current_color = color
        tone_data = self.synthesize_tone(tone_type) if tone_type else None

        event = FeedbackEvent(
            status=status,
            color=color,
            message=message,
            tone_type=tone_type,
            tone_samples=tone_data,
        )

        self.last_event = event
        self.feedback_history.append(event)
        logger.info(message)

        if tone_type:
            self.play_tone(tone_type)

        for listener in self._listeners:
            try:
                listener(event)
            except Exception as e:
                logger.error(f"Error in feedback listener: {e}")
