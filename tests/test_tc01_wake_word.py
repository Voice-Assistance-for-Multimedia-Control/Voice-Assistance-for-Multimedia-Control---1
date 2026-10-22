"""
IEEE Test Case TC-01: Verify system enters listening state on wake word.
Traceability: Functional Requirement FR-1, User Story US-01.

Acceptance Criteria:
- System enters active listening state within 1 second of wake word detection.
- Active listening session token is generated.
- Callbacks notify downstream components (ASR / Feedback LED).
"""

import time
import pytest

from voice_control.models.command import SystemState


class TestTC01WakeWordDetection:
    """Test suite for IEEE Test Plan Case TC-01."""

    def test_initial_state_is_idle(self, wake_detector):
        """Precondition check: System powered on and idle."""
        assert wake_detector.current_state == SystemState.IDLE
        assert not wake_detector.is_listening
        assert wake_detector.active_session_token is None

    def test_enters_listening_state_within_one_second(self, wake_detector, simulated_engine, sample_audio_chunk):
        """
        TC-01 / FR-1:
        Verify system enters active listening state within 1 second of wake word.
        """
        # Step 1: Arm wake word detection in simulated engine
        simulated_engine.arm_trigger()

        # Step 2: Feed audio chunk and measure latency
        start_time = time.perf_counter()
        detected = wake_detector.detect_wake_word(sample_audio_chunk)
        elapsed_seconds = time.perf_counter() - start_time

        # Assertions
        assert detected is True, "detect_wake_word must return True when wake word is detected"
        assert wake_detector.is_listening is True, "System must enter LISTENING state"
        assert wake_detector.current_state == SystemState.LISTENING
        assert elapsed_seconds < 1.0, f"Detection latency ({elapsed_seconds:.4f}s) must be strictly < 1.0s (FR-1)"
        assert wake_detector.last_detection_latency is not None
        assert wake_detector.last_detection_latency < 1.0

    def test_generates_unique_session_token(self, wake_detector, simulated_engine, sample_audio_chunk):
        """Verify wake detection creates an authorized session token for security gating (SR-1)."""
        simulated_engine.arm_trigger()
        wake_detector.detect_wake_word(sample_audio_chunk)

        token = wake_detector.active_session_token
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
        assert wake_detector.session_manager.is_session_valid(token) is True

    def test_wake_callback_triggered(self, wake_detector, simulated_engine, sample_audio_chunk):
        """Verify downstream listeners receive event notification upon wake word detection."""
        received_events = []

        def on_wake(token, confidence):
            received_events.append({"token": token, "confidence": confidence})

        wake_detector.register_wake_callback(on_wake)

        simulated_engine.arm_trigger()
        wake_detector.detect_wake_word(sample_audio_chunk)

        assert len(received_events) == 1
        assert received_events[0]["token"] == wake_detector.active_session_token
        assert received_events[0]["confidence"] >= 0.5

    def test_live_acoustic_pattern_detection(self, live_pattern_detector, wake_word_audio_chunk):
        """Verify the AcousticPatternEngine detects synthetic wake word marker within latency bounds."""
        start_t = time.perf_counter()
        detected = live_pattern_detector.detect_wake_word(wake_word_audio_chunk)
        elapsed = time.perf_counter() - start_t

        assert detected is True
        assert live_pattern_detector.is_listening is True
        assert elapsed < 1.0, f"Acoustic detection latency must be < 1s (got {elapsed:.4f}s)"

    def test_listening_window_stays_open_for_configured_duration(self, wake_detector, simulated_engine, sample_audio_chunk):
        """Verify the listening window remains active for the configured duration."""
        simulated_engine.arm_trigger()
        wake_detector.detect_wake_word(sample_audio_chunk)

        assert wake_detector.is_listening is True
        assert wake_detector.time_remaining_seconds > 0.0
        assert wake_detector.time_remaining_seconds <= wake_detector.config.listening_window_seconds
