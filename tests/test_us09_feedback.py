"""
Tests for User Story US-09: Command Feedback.
Requirement Traceability: SRS FR-10, Architecture 3.3 Feedback Module.

Acceptance Criteria:
- A visible or audible acknowledgement (e.g., LED blink or log message) is given on every successful command (FR-10).
- A distinct indication (e.g., short tone) is given when a command is rejected or fails.
"""

import numpy as np
import pytest

from voice_control.feedback.indicator import (
    FeedbackEvent,
    FeedbackModule,
    LEDColor,
    ToneType,
)
from voice_control.models.command import SystemState
from voice_control.security.error_handler import (
    ErrorHandler,
    MicrophoneUnavailableError,
    UnrecognizedCommandError,
)


class TestUS09CommandFeedback:
    """Test suite verifying US-09 command feedback requirements."""

    @pytest.fixture
    def feedback_module(self):
        return FeedbackModule(enable_audio_tones=True)

    def test_successful_command_feedback(self, feedback_module):
        """
        US-09 Criterion 1 / FR-10:
        Verify visible and audible acknowledgement on every successful command.
        """
        feedback_module.notify("ok")

        assert feedback_module.current_color == LEDColor.GREEN
        assert feedback_module.last_status == "ok"
        assert feedback_module.last_event is not None
        assert feedback_module.last_event.status == "ok"
        assert feedback_module.last_event.color == LEDColor.GREEN
        assert feedback_module.last_event.tone_type == ToneType.SUCCESS
        assert feedback_module.last_event.tone_samples is not None
        assert len(feedback_module.last_event.tone_samples) > 0
        assert "executed successfully" in feedback_module.last_event.message.lower()

    def test_rejected_command_feedback(self, feedback_module):
        """
        US-09 Criterion 2:
        Verify distinct indication (short tone / red LED) when a command is rejected or fails.
        """
        feedback_module.notify("error")

        assert feedback_module.current_color == LEDColor.RED
        assert feedback_module.last_status == "error"
        assert feedback_module.last_event is not None
        assert feedback_module.last_event.status == "error"
        assert feedback_module.last_event.color == LEDColor.RED
        assert feedback_module.last_event.tone_type == ToneType.REJECTION
        assert feedback_module.last_event.tone_samples is not None
        assert len(feedback_module.last_event.tone_samples) > 0
        assert "rejected" in feedback_module.last_event.message.lower()

    def test_distinct_tone_synthesis(self, feedback_module):
        """Verify that SUCCESS and REJECTION tones have distinct acoustic properties."""
        success_tone_bytes = feedback_module.synthesize_tone(ToneType.SUCCESS)
        rejection_tone_bytes = feedback_module.synthesize_tone(ToneType.REJECTION)

        assert success_tone_bytes != rejection_tone_bytes

        # Convert to numpy arrays for acoustic analysis
        success_samples = np.frombuffer(success_tone_bytes, dtype=np.int16).astype(np.float32)
        rejection_samples = np.frombuffer(rejection_tone_bytes, dtype=np.int16).astype(np.float32)

        # Zero crossing rate of rejection tone (square wave buzz) is markedly distinct
        success_zcr = np.mean(np.abs(np.diff(np.signbit(success_samples))))
        rejection_zcr = np.mean(np.abs(np.diff(np.signbit(rejection_samples))))

        assert success_zcr > 0.0
        assert rejection_zcr > 0.0
        assert abs(success_zcr - rejection_zcr) > 0.005

    def test_feedback_history_logging(self, feedback_module):
        """Verify that every feedback notification is preserved in chronological history."""
        initial_count = len(feedback_module.feedback_history)

        feedback_module.notify("ok")
        feedback_module.notify("error")
        feedback_module.notify("mic_error")

        assert len(feedback_module.feedback_history) == initial_count + 3
        statuses = [e.status for e in feedback_module.feedback_history[-3:]]
        assert statuses == ["ok", "error", "mic_error"]

    def test_feedback_listener_dispatch(self, feedback_module):
        """Verify external subscribers receive feedback event objects."""
        dispatched_events = []

        def on_feedback(event: FeedbackEvent):
            dispatched_events.append(event)

        feedback_module.register_listener(on_feedback)
        feedback_module.notify("ok")

        assert len(dispatched_events) == 1
        assert dispatched_events[0].color == LEDColor.GREEN

    def test_error_handler_triggers_feedback(self, feedback_module):
        """Verify ErrorHandler funnels errors into distinct feedback notifications."""
        error_handler = ErrorHandler(feedback_module)

        # Trigger command rejection error
        error_handler.handle_error(UnrecognizedCommandError("Command 'fly' not recognized"))
        assert feedback_module.current_color == LEDColor.RED
        assert feedback_module.last_event.tone_type == ToneType.REJECTION

        # Trigger microphone error
        error_handler.handle_error(MicrophoneUnavailableError("Device not detected"))
        assert feedback_module.current_color == LEDColor.RED
        assert feedback_module.last_event.tone_type == ToneType.HARDWARE_FAULT
