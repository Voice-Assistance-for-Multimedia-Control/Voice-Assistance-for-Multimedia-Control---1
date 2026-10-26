"""
US-16 (microphone privacy control) and the NFR-1 timing log used by US-11.

Drives the same VoiceAssistant that main.py runs, with synthetic audio, a
scripted recognizer and a fake media player (helpers from the Sprint 1 tests).
"""

import queue

import pytest

from tests.test_sprint1_integration import make_assistant, say, statuses
from voice_control.feedback.indicator import LEDColor
from voice_control.models.command import SystemState


class FakeCapture:
    """Stands in for AudioCaptureComponent: records start/stop of the microphone."""

    def __init__(self):
        self.events = []

    def stop_stream(self):
        self.events.append("stop")

    def start_stream(self):
        self.events.append("start")


def feedback_statuses(feedback):
    return [e.status for e in feedback.feedback_history]


# ------------------------------------------------------------------ US-16
def test_nothing_is_processed_while_muted():
    assistant, media, _, transcriber = make_assistant(["hey media", "play"])
    assistant.set_muted(True)
    say(assistant, 2)
    assert media.calls == []
    assert transcriber.calls == 0          # audio is not even transcribed
    assert assistant.sessions.current_state == SystemState.IDLE


def test_one_breath_command_is_ignored_while_muted():
    assistant, media, _, transcriber = make_assistant(["hey media pause"])
    assistant.set_muted(True)
    say(assistant, 1)
    assert media.calls == []
    assert transcriber.calls == 0


def test_muting_cancels_an_open_listening_window():
    assistant, media, _, _ = make_assistant(["hey media", "pause"])
    say(assistant, 1)                        # wake word -> window open
    assert assistant.sessions.current_state == SystemState.LISTENING
    assistant.set_muted(True)
    assert assistant.sessions.current_state == SystemState.IDLE
    say(assistant, 1)                        # "pause" spoken while muted
    assert media.calls == []


def test_commands_work_again_after_unmuting():
    assistant, media, _, _ = make_assistant(["hey media", "next"])
    assistant.set_muted(True)
    assistant.set_muted(False)
    say(assistant, 2)
    assert media.calls == ["next_track"]


def test_wake_word_heard_before_mute_is_not_used_after_unmute():
    assistant, media, _, _ = make_assistant(["hey media", "play"])
    say(assistant, 1)                        # session open
    assistant.set_muted(True)
    assistant.set_muted(False)
    say(assistant, 1)                        # "play" without a new wake word
    assert media.calls == []


def test_mute_and_unmute_are_indicated():
    assistant, _, feedback, _ = make_assistant([])
    assistant.set_muted(True)
    assert feedback.last_event.status == "muted"
    assert feedback.current_color == LEDColor.YELLOW
    assert "Microphone OFF" in feedback.last_event.message
    assistant.set_muted(False)
    assert feedback.last_event.status == "unmuted"
    assert "Microphone ON" in feedback.last_event.message


def test_repeated_mute_does_not_repeat_the_indication():
    assistant, _, feedback, _ = make_assistant([])
    assistant.set_muted(True)
    assistant.set_muted(True)
    assert feedback_statuses(feedback).count("muted") == 1


def test_toggle_mute_flips_state():
    assistant, _, _, _ = make_assistant([])
    assert assistant.toggle_mute() is True
    assert assistant.is_muted
    assert assistant.toggle_mute() is False
    assert not assistant.is_muted


@pytest.mark.parametrize(
    "typed, muted_after",
    [("m\n", True), ("M", True), ("mute", True), ("off", True), ("unmute", False), ("on", False)],
)
def test_typed_controls(typed, muted_after):
    assistant, _, _, _ = make_assistant([])
    if typed.strip().lower() in ("unmute", "on"):
        assistant.set_muted(True)
    assert assistant.handle_control(typed) is True
    assert assistant.is_muted is muted_after


def test_unknown_typed_text_is_not_a_control():
    assistant, _, _, _ = make_assistant([])
    assert assistant.handle_control("play") is False
    assert assistant.handle_control("") is False
    assert not assistant.is_muted


def test_mute_really_stops_and_restarts_the_microphone():
    assistant, _, _, _ = make_assistant([])
    capture, chunks = FakeCapture(), queue.Queue()
    chunks.put(b"old audio")
    assistant._controls.put("m\n")
    assistant._apply_controls(capture, chunks)
    assert capture.events == ["stop"]
    assert chunks.empty()                    # audio from before the mute is dropped
    assistant._controls.put("m\n")
    assistant._apply_controls(capture, chunks)
    assert capture.events == ["stop", "start"]
    assert not assistant.is_muted


# ------------------------------------------------- timing log (NFR-1, US-11)
def test_each_command_records_time_from_end_of_speech():
    assistant, _, _, _ = make_assistant(["hey media", "pause"])
    say(assistant, 2)
    assert len(assistant.latencies_ms) == 1
    # The test audio ends with ~0.5 s of silence before the utterance is complete,
    # so the measured time must include it.
    assert 450 <= assistant.latencies_ms[-1] < 1500


def test_slow_recognition_shows_up_in_the_timing():
    assistant, _, _, _ = make_assistant(["hey media", "pause"])
    say(assistant, 1)
    assistant.transcriber.delay = 0.3
    say(assistant, 1)
    assert assistant.latencies_ms[-1] >= 750


def test_one_breath_command_is_timed():
    assistant, _, _, _ = make_assistant(["hey media volume up"])
    say(assistant, 1)
    assert len(assistant.latencies_ms) == 1


def test_rejected_or_unclear_commands_are_not_timed():
    assistant, _, _, _ = make_assistant(["hey media", "open netflix", "hey media", None])
    say(assistant, 4)
    assert len(assistant.latencies_ms) == 0


def test_timing_summary():
    assistant, _, _, _ = make_assistant([])
    assert assistant.timing_summary() is None
    assistant.latencies_ms.extend([500.0, 700.0, 900.0])
    summary = assistant.timing_summary()
    assert summary["count"] == 3
    assert summary["average_ms"] == pytest.approx(700.0)
    assert summary["max_ms"] == 900.0


def test_timing_is_logged(caplog):
    assistant, _, _, _ = make_assistant(["hey media", "next"])
    with caplog.at_level("INFO", logger="voice_control.runtime"):
        say(assistant, 2)
    lines = [r.getMessage() for r in caplog.records if "[TIMING]" in r.getMessage()]
    assert len(lines) == 1
    assert "'next' executed in" in lines[0]
    assert "target < 2000 ms" in lines[0]


def test_history_is_bounded_for_long_runs():
    assistant, _, _, _ = make_assistant([])
    assistant.latencies_ms.extend([1.0] * 1000)
    assert len(assistant.latencies_ms) == 200
