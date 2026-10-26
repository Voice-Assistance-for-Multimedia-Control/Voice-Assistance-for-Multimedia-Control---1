"""
Tests for User Story US-15: Recover from Recognition Errors.

Acceptance Criteria (GitHub issue #24):
- Recognition errors do not crash the application.
- The system returns to wake-word detection after handling an error.
- A new valid command can be processed without restarting the system.

The full pipeline is driven through VoiceAssistant (the object main.py runs).
The recognizer is scripted so each test decides exactly which utterance fails.
"""

import pytest

from voice_control.models.command import SystemState

# Reuse the Sprint 1 helpers instead of duplicating them.
from tests.test_sprint1_integration import (
    FakeMedia,
    make_assistant,
    say,
    statuses,
)


# ------------------------------------------------------------ Criterion 1 + 2
@pytest.mark.parametrize(
    "error",
    [
        ConnectionError("offline"),            # e.g. Wi-Fi lost with the Google backend
        RuntimeError("recognizer crashed"),
        ValueError("bad audio data"),
        TimeoutError("recognizer timed out"),
    ],
)
def test_error_while_hearing_a_command_does_not_crash_and_returns_to_idle(error):
    assistant, media, feedback, _ = make_assistant(["hey media", error])
    say(assistant, 2)                                  # must not raise

    assert media.calls == []                           # nothing was executed
    assert not assistant.results[-1].success
    assert statuses(feedback) == ["error"]             # user is told it failed
    assert assistant.sessions.current_state == SystemState.IDLE
    assert assistant._session_token is None            # back to wake-word detection


def test_unintelligible_speech_after_wake_word_returns_to_idle():
    """Recognizer returns None ("not understood"), which is also a recognition error."""
    assistant, media, feedback, _ = make_assistant(["hey media", None])
    say(assistant, 2)

    assert media.calls == []
    assert statuses(feedback) == ["error"]
    assert assistant.sessions.current_state == SystemState.IDLE


def test_error_during_wake_word_detection_does_not_crash_or_open_session():
    assistant, media, _, _ = make_assistant([RuntimeError("recognizer crashed")])
    say(assistant, 1)                                  # must not raise

    assert media.calls == []
    assert assistant.sessions.current_state == SystemState.IDLE


# ----------------------------------------------------------------- Criterion 3
@pytest.mark.parametrize(
    "spoken, expected_call",
    [
        ("play", "play_media"),
        ("pause", "pause_media"),
        ("resume", "resume_media"),
        ("next", "next_track"),
        ("previous", "previous_track"),
        ("volume up", "adjust_volume:up"),
        ("volume down", "adjust_volume:down"),
    ],
)
def test_valid_command_works_after_a_recognition_error(spoken, expected_call):
    """Error first, then a normal 'hey media <command>' with no restart."""
    script = [
        "hey media", ConnectionError("offline"),       # attempt 1 fails
        "hey media", spoken,                           # attempt 2 must work
    ]
    assistant, media, feedback, _ = make_assistant(script)
    say(assistant, 4)

    assert media.calls == [expected_call]
    assert assistant.results[-1].success
    assert statuses(feedback) == ["error", "ok"]       # failure, then success
    assert assistant.sessions.current_state == SystemState.IDLE


def test_valid_command_works_after_error_in_wake_word_stage():
    script = [
        RuntimeError("recognizer crashed"),            # wake-word transcription fails
        "hey media", "pause",                          # then a normal command
    ]
    assistant, media, _, _ = make_assistant(script)
    say(assistant, 3)

    assert media.calls == ["pause_media"]
    assert assistant.results[-1].success


def test_valid_command_works_after_unintelligible_speech():
    script = ["hey media", None, "hey media", "next"]
    assistant, media, feedback, _ = make_assistant(script)
    say(assistant, 4)

    assert media.calls == ["next_track"]
    assert statuses(feedback) == ["error", "ok"]


def test_several_errors_in_a_row_then_a_valid_command():
    """Repeated failures never leave the system stuck."""
    script = [
        "hey media", ConnectionError("offline"),
        "hey media", RuntimeError("crash"),
        "hey media", None,
        "hey media", "play",
    ]
    assistant, media, feedback, _ = make_assistant(script)
    say(assistant, 8)

    assert media.calls == ["play_media"]
    assert statuses(feedback) == ["error", "error", "error", "ok"]
    assert assistant.sessions.current_state == SystemState.IDLE


def test_recovery_is_repeatable_across_the_whole_run():
    """error, ok, error, ok ... the same running assistant keeps recovering."""
    script = [
        "hey media", ConnectionError("offline"), "hey media", "play",
        "hey media", ConnectionError("offline"), "hey media", "pause",
    ]
    assistant, media, _, transcriber = make_assistant(script)
    say(assistant, 8)

    assert media.calls == ["play_media", "pause_media"]
    assert transcriber.calls == 8                      # same transcriber object throughout


def test_failed_command_is_not_retried_and_does_not_leak_into_next_session():
    """After an error the old session is closed; the next command needs a new wake word."""
    script = ["hey media", ConnectionError("offline"), "play"]
    assistant, media, _, _ = make_assistant(script)
    say(assistant, 3)                                  # 'play' arrives with NO wake word

    assert media.calls == []                           # security gating still holds
    assert assistant.sessions.current_state == SystemState.IDLE