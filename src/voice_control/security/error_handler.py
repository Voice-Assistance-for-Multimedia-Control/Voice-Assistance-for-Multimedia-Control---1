"""
Error Handler Component (Control Layer).
Implements the exact API from Architecture Specification Section 3.3:
    handle_error(error: Exception) -> None

Funnels all system error conditions (Architecture 3.4):
- Catches unrecognized commands or execution failures (FR-9)
- Catches microphone / hardware disconnect faults (US-13, NFR-3)
- Catches security validation failures (SR-1, SO-1)
- Logs the error and triggers feedback indication; never raises further.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import List, Optional

from voice_control.feedback.indicator import FeedbackModule

logger = logging.getLogger(__name__)


@dataclass
class ErrorRecord:
    """Record of an intercepted error condition."""
    error_type: str
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    handled_gracefully: bool = True


class VoiceControlError(Exception):
    """Base exception for voice control system errors."""
    pass


class MicrophoneUnavailableError(VoiceControlError):
    """Raised when microphone hardware is unavailable, disconnected, or permission denied."""
    pass


class UnrecognizedCommandError(VoiceControlError):
    """Raised when recognized text does not match the command vocabulary (FR-9)."""
    pass


class SecurityGatingError(VoiceControlError):
    """Raised when a command fails wake-word session gating (SR-1, SO-1)."""
    pass


class ErrorHandler:
    """
    Central error handling component.
    Logs every fault, triggers appropriate user feedback, and protects system stability.
    """

    def __init__(self, feedback_module: Optional[FeedbackModule] = None):
        self.feedback = feedback_module or FeedbackModule()
        self.error_history: List[ErrorRecord] = []
        self.total_errors_handled = 0

    def handle_error(self, error: Exception) -> None:
        """
        Architecture Specification 3.3 API:
            Function: handle_error(error)
            Parameters: error: Exception
            Returns: none (logs only)
            Notes: Logs the error and triggers a feedback tone; never raises further.
        """
        self.total_errors_handled += 1
        err_type = type(error).__name__
        err_msg = str(error)

        record = ErrorRecord(error_type=err_type, message=err_msg)
        self.error_history.append(record)

        logger.error(f"[ERROR HANDLER] Handled {err_type}: {err_msg}")

        # Trigger distinct feedback depending on error category
        if isinstance(error, MicrophoneUnavailableError):
            self.feedback.notify("mic_error")
        elif isinstance(error, (UnrecognizedCommandError, SecurityGatingError)):
            self.feedback.notify("error")
        else:
            self.feedback.notify("error")

    @property
    def last_error(self) -> Optional[ErrorRecord]:
        """Return the most recent error record."""
        return self.error_history[-1] if self.error_history else None
