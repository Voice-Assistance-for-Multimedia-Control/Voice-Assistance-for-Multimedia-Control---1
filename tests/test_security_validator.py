"""
Tests for SecurityValidator Component.
Traceability: Architecture 3.3 API validate_source(command), SO-1, SR-1.
"""

from datetime import datetime, timezone
import pytest

from voice_control.detector.state import SessionManager
from voice_control.models.command import Command, SystemState
from voice_control.security.validator import SecurityValidator


class TestSecurityValidator:
    """Verifies command validation and wake-word gating authorization."""

    def test_validate_valid_command(self, session_manager, security_validator):
        """A command matching an open session must be authorized."""
        token = session_manager.open_session()
        assert session_manager.current_state == SystemState.LISTENING

        cmd = Command(type="play", confidence=0.92, session_id=token)
        assert security_validator.validate_source(cmd) is True

    def test_reject_when_no_active_session(self, security_validator):
        """Reject when system is in IDLE state."""
        cmd = Command(type="pause", confidence=0.88, session_id="any-token")
        assert security_validator.validate_source(cmd) is False

    def test_reject_null_command(self, security_validator):
        """Reject None / empty command."""
        assert security_validator.validate_source(None) is False

    def test_reject_mismatched_session_token(self, session_manager, security_validator):
        """Reject if token does not match the active session."""
        session_manager.open_session()

        cmd = Command(type="next", confidence=0.90, session_id="wrong-token")
        assert security_validator.validate_source(cmd) is False

    def test_reject_out_of_bounds_confidence(self, session_manager, security_validator):
        """Reject commands with invalid confidence scores."""
        token = session_manager.open_session()

        cmd_negative = Command(type="play", confidence=-0.1, session_id=token)
        assert security_validator.validate_source(cmd_negative) is False

        cmd_overflow = Command(type="play", confidence=1.5, session_id=token)
        assert security_validator.validate_source(cmd_overflow) is False

    def test_violation_counter_increments(self, security_validator):
        """Verify that security rejections increment the violation audit counter."""
        initial_violations = security_validator.security_violations_count
        cmd = Command(type="volume down", confidence=0.80, session_id="bad-token")
        security_validator.validate_source(cmd)

        assert security_validator.security_violations_count == initial_violations + 1
