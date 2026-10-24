"""
Security Validator Component (Control Layer).
Implements the exact API from Architecture Specification Section 3.3:
    validate_source(command: Command) -> bool

Enforces Security Requirements:
    SO-1 (Command Source Integrity)
    SR-1 (Wake-Word Gating)
Ensures commands are strictly rejected if received outside an active wake-word session.
"""

from datetime import datetime, timezone
import logging
from typing import Optional

from voice_control.detector.state import SessionManager
from voice_control.models.command import Command

logger = logging.getLogger(__name__)


class SecurityValidator:
    """
    Security gate placed before Command Executor.
    Confirms each command originated from an active, authorized wake-word-gated session.
    """

    def __init__(self, session_manager: SessionManager, min_confidence: float = 0.5):
        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError("min_confidence must be between 0 and 1")
        self.session_manager = session_manager
        self.min_confidence = min_confidence
        self.security_violations_count = 0

    def validate_source(self, command: Command) -> bool:
        """
        Architecture Specification 3.3:
            Function: validate_source(command)
            Parameters: command: Command
            Returns: bool – True if authorized
            Notes: Checks the command originated within an active, wake-word-gated session.

        Returns False if:
            - System is in IDLE state (no wake word was spoken)
            - Listening window has expired
            - Command lacks a valid session token matching the current session
            - Confidence score is below minimal safety threshold
        """
        if not command:
            self._log_security_violation("Null command object presented")
            return False

        if not self.session_manager.is_session_valid(command.session_id):
            self._log_security_violation(
                f"Command '{command.type}' attempted with invalid or expired session '{command.session_id}'. "
                f"Active session is: '{self.session_manager.current_token}', State: {self.session_manager.current_state}"
            )
            return False

        if command.confidence < 0.0 or command.confidence > 1.0:
            self._log_security_violation(f"Command '{command.type}' has invalid confidence: {command.confidence}")
            return False

        if command.confidence < self.min_confidence:
            self._log_security_violation(
                f"Command '{command.type}' confidence {command.confidence:.2f} is below "
                f"the minimum {self.min_confidence:.2f}"
            )
            return False

        logger.info(f"Security validation passed for command '{command.type}' in session '{command.session_id}'.")
        return True

    def _log_security_violation(self, reason: str) -> None:
        self.security_violations_count += 1
        logger.warning(f"[SECURITY EVENT SR-1/SO-1] Access denied: {reason}")
