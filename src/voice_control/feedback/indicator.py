"""
Feedback / LED Module (Output Layer).
Implements the exact API from Architecture Specification Section 3.3:
    notify(status: 'ok' | 'error') -> None

SRS Requirement FR-10:
    Visible or audible acknowledgement (e.g. LED blink or log message)
    each time a command or wake-word status changes.
"""

from enum import Enum
import logging
from typing import Callable, List, Optional

from voice_control.models.command import SystemState

logger = logging.getLogger(__name__)


class LEDColor(str, Enum):
    OFF = "OFF"
    BLUE = "BLUE"      # Listening
    GREEN = "GREEN"    # Command Success (OK)
    RED = "RED"        # Error / Command Rejection / Security


class FeedbackModule:
    """
    Console and hardware LED feedback driver.
    Signals listening state, successful execution, and rejection errors.
    """

    def __init__(self, hardware_pin: Optional[int] = None):
        self.hardware_pin = hardware_pin
        self.current_color = LEDColor.OFF
        self.last_status: Optional[str] = None
        self._listeners: List[Callable[[str, LEDColor], None]] = []

    def register_listener(self, listener: Callable[[str, LEDColor], None]) -> None:
        """Register listener for status/LED events (e.g. GUI or hardware GPIO)."""
        self._listeners.append(listener)

    def on_state_change(self, state: SystemState, token: Optional[str] = None) -> None:
        """Handle state change from SessionManager."""
        if state == SystemState.LISTENING:
            self._set_led(LEDColor.BLUE, f"[FEEDBACK] Wake word detected! System is now LISTENING (Token: {token})")
        elif state == SystemState.IDLE:
            self._set_led(LEDColor.OFF, "[FEEDBACK] System returned to IDLE (Awaiting wake word).")
        elif state == SystemState.PROCESSING:
            self._set_led(LEDColor.BLUE, "[FEEDBACK] Processing recognized command...")

    def notify(self, status: str) -> None:
        """
        Architecture 3.3: notify(status: 'ok' | 'error').
        Drives the LED / tone output visible or audible to the user.
        """
        self.last_status = status.lower()

        if self.last_status == "ok":
            self._set_led(LEDColor.GREEN, "[FEEDBACK ✓] Command executed successfully.")
        elif self.last_status == "error":
            self._set_led(LEDColor.RED, "[FEEDBACK ✗] Command rejected or error encountered.")
        else:
            self._set_led(LEDColor.OFF, f"[FEEDBACK] Status update: {status}")

    def _set_led(self, color: LEDColor, message: str) -> None:
        self.current_color = color
        logger.info(message)
        for listener in self._listeners:
            try:
                listener(message, color)
            except Exception:
                pass
