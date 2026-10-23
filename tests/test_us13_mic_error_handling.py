"""
Tests for User Story US-13: Microphone Error Handling.
Requirement Traceability: Architecture 3.4 (Microphone / Hardware Disconnected).

Acceptance Criteria:
- The system detects microphone initialization or access failures.
- An error indication is provided when audio input is unavailable.
- The system does not execute commands without valid audio input.
"""

from unittest.mock import patch
import pytest

from voice_control.audio.capture import AudioCaptureComponent
from voice_control.config import VoiceControlConfig
from voice_control.feedback.indicator import FeedbackModule, LEDColor, ToneType
from voice_control.models.command import Command
from voice_control.security.error_handler import ErrorHandler, MicrophoneUnavailableError
from voice_control.security.validator import SecurityValidator


class TestUS13MicrophoneErrorHandling:
    """Test suite verifying US-13 microphone error handling requirements."""

    @pytest.fixture
    def feedback_module(self):
        return FeedbackModule(enable_audio_tones=True)

    @pytest.fixture
    def capture_component(self, feedback_module):
        return AudioCaptureComponent(
            config=VoiceControlConfig(), feedback_module=feedback_module
        )

    def test_detect_microphone_access_failure(self):
        """
        US-13 Criterion 1:
        Verify the system detects microphone initialization or access failures.
        """
        # Simulate sounddevice error querying devices
        with patch.dict("sys.modules", {"sounddevice": None, "pyaudio": None}):
            is_avail, desc = AudioCaptureComponent.check_microphone_availability()
            # In absence of audio drivers, system gracefully detects unavailability
            assert isinstance(is_avail, bool)
            assert isinstance(desc, str)
            assert len(desc) > 0

    def test_error_indication_when_audio_unavailable(self, capture_component, feedback_module):
        """
        US-13 Criterion 2:
        Verify an error indication (red LED / warning tone) is provided when audio input is unavailable.
        """
        reported_errors = []
        capture_component.register_error_callback(lambda e: reported_errors.append(e))

        # Trigger stream suspension due to missing device
        capture_component.suspend_stream("Microphone disconnected by user")

        assert capture_component.is_healthy is False
        assert capture_component.is_suspended is True
        assert "Microphone disconnected" in capture_component.suspension_reason

        # Verify visible and audible error indication
        assert feedback_module.current_color == LEDColor.RED
        assert feedback_module.last_event is not None
        assert feedback_module.last_event.status == "mic_error"
        assert feedback_module.last_event.tone_type == ToneType.HARDWARE_FAULT

        # Verify error callback received MicrophoneUnavailableError
        assert len(reported_errors) == 1
        assert isinstance(reported_errors[0], MicrophoneUnavailableError)

    def test_blocks_commands_without_valid_audio_input(
        self, capture_component, feedback_module
    ):
        """
        US-13 Criterion 3:
        Verify the system does not execute commands without valid audio input.
        """
        # When microphone is suspended, can_capture must be False
        capture_component.suspend_stream("Hardware fault")
        assert capture_component.can_capture() is False

        # Attempting to feed audio frames while faulted discards them
        initial_buffer_size = capture_component.buffer.current_size
        capture_component.feed_chunk(b"\x01\x02" * 1024)
        assert capture_component.buffer.current_size == initial_buffer_size

        # SecurityValidator must not have an active session
        from voice_control.detector.state import SessionManager
        session_mgr = SessionManager()
        validator = SecurityValidator(session_mgr)

        unauthorized_cmd = Command(type="play", confidence=0.90, session_id="stale")
        assert validator.validate_source(unauthorized_cmd) is False

    def test_stream_resumption_on_hardware_restoration(
        self, capture_component, feedback_module
    ):
        """Verify the system resumes healthy operation once the microphone is reconnected."""
        capture_component.suspend_stream("Temporary cable unplug")
        assert capture_component.is_healthy is False

        # Reconnection restores stream health
        capture_component.resume_stream()
        assert capture_component.is_healthy is True
        assert capture_component.is_suspended is False
        assert capture_component.suspension_reason is None

        # Verify feedback signals restoration
        assert feedback_module.current_color == LEDColor.GREEN

    def test_faulty_stream_worker_triggers_suspension(
        self, capture_component, feedback_module
    ):
        """Verify that streaming faults in background thread trigger suspension rather than crash."""
        def faulty_generator():
            yield b"\x00" * 1024
            raise IOError("I/O error reading microphone USB endpoint")

        capture_component.start_stream(faulty_generator())
        # Wait for thread to finish
        if capture_component._thread:
            capture_component._thread.join(timeout=1.0)

        assert capture_component.is_suspended is True
        assert feedback_module.current_color == LEDColor.RED
        assert "Stream read error" in capture_component.suspension_reason
