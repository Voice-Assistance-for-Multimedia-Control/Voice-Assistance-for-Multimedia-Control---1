"""
IEEE Test Case TC-10: Verify system does not act on audio without the wake word.
Traceability: Security Requirement SR-1 (Wake-Word Gating) and SO-1 (Command Source Integrity).

Acceptance Criteria:
- System remains in IDLE state when receiving background noise, music, or unrelated speech.
- No listening window is opened.
- Any commands dispatched without a valid wake-word session are rejected by SecurityValidator.
"""

import numpy as np
import pytest

from voice_control.models.command import Command, SystemState


class TestTC10SecurityGating:
    """Test suite for IEEE Test Plan Case TC-10."""

    def test_silence_does_not_trigger_listening(self, wake_detector, sample_audio_chunk):
        """Precondition: System idle. Feed silence -> System remains idle."""
        detected = wake_detector.detect_wake_word(sample_audio_chunk)

        assert detected is False
        assert wake_detector.is_listening is False
        assert wake_detector.current_state == SystemState.IDLE
        assert wake_detector.active_session_token is None

    def test_background_noise_does_not_trigger_listening(self, live_pattern_detector, noise_audio_chunks):
        """
        TC-10 Step 1 & 2:
        Play background audio / ambient noise. System must remain IDLE.
        """
        for chunk in noise_audio_chunks:
            detected = live_pattern_detector.detect_wake_word(chunk)
            assert detected is False, "Noise chunk must NOT trigger wake detection"
            assert live_pattern_detector.is_listening is False
            assert live_pattern_detector.current_state == SystemState.IDLE

    def test_command_without_wake_word_is_rejected_by_security_validator(
        self, wake_detector, security_validator
    ):
        """
        TC-10 Expected Result:
        No command is executed without wake word; confirms wake-word gating (SR-1).
        """
        # Ensure system is in IDLE state
        assert wake_detector.current_state == SystemState.IDLE

        # Attempt to forge an unauthorized 'play' command without wake-word session
        unauthorized_command = Command(
            type="play",
            confidence=0.98,
            session_id=None,  # No session token
        )

        authorized = security_validator.validate_source(unauthorized_command)
        assert authorized is False, "Command lacking session token must be REJECTED (SR-1)"
        assert security_validator.security_violations_count >= 1

    def test_forged_session_token_is_rejected(self, wake_detector, security_validator):
        """Verify arbitrary fake session tokens are blocked by the SecurityValidator."""
        fake_command = Command(
            type="volume up",
            confidence=0.90,
            session_id="fake-forged-session-token-12345",
        )

        authorized = security_validator.validate_source(fake_command)
        assert authorized is False, "Forged session token must be REJECTED (SO-1, SR-1)"

    def test_command_after_session_timeout_is_rejected(
        self, wake_detector, simulated_engine, security_validator, sample_audio_chunk
    ):
        """Verify commands sent after listening window has expired are rejected."""
        # Step 1: Detect wake word and open session
        simulated_engine.arm_trigger()
        wake_detector.detect_wake_word(sample_audio_chunk)
        valid_token = wake_detector.active_session_token
        assert valid_token is not None

        # Step 2: Manually expire the session (simulate timeout)
        wake_detector.session_manager.close_session()
        assert wake_detector.current_state == SystemState.IDLE

        # Step 3: Attempt to execute command with old/expired token
        stale_command = Command(type="play", confidence=0.95, session_id=valid_token)
        authorized = security_validator.validate_source(stale_command)
        assert authorized is False, "Expired session command must be REJECTED (SR-1)"
