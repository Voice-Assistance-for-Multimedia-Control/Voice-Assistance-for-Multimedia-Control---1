"""
US-19 (listening status indicator) and US-17 (local voice processing).

Drives the same VoiceAssistant that main.py runs, with synthetic audio, a
scripted recognizer and a fake media player (helpers from the Sprint 1 tests).
"""

import os
import socket

import pytest

from tests.test_sprint1_integration import make_assistant, say, utterance
from voice_control.audio.buffer import AudioBuffer
from voice_control.audio.segmenter import UtteranceSegmenter
from voice_control.config import VoiceControlConfig
from voice_control.models.command import SystemState
from voice_control.recognition.transcriber import (
    GoogleTranscriber,
    VoskTranscriber,
    create_transcriber,
)
from voice_control.runtime import AssistantStatus

READY, LISTENING, MUTED, UNAVAILABLE = (
    AssistantStatus.READY,
    AssistantStatus.LISTENING,
    AssistantStatus.MUTED,
    AssistantStatus.UNAVAILABLE,
)


# ------------------------------------------------------------------ US-19
def test_starts_ready():
    assistant, _, _, _ = make_assistant([])
    assert assistant.status == READY
    assert "READY" in assistant.status_message()
    assert "hey media" in assistant.status_message()


def test_shows_listening_after_wake_word_and_ready_after_command():
    assistant, _, _, _ = make_assistant(["hey media", "pause"])
    say(assistant, 1)
    assert assistant.status == LISTENING
    say(assistant, 1)
    assert assistant.status == READY
    assert list(assistant.status_history) == [LISTENING, READY]


def test_listening_message_states_the_window():
    assistant, _, _, _ = make_assistant([])
    assert "4 s" in assistant.status_message(LISTENING)


def test_goes_back_to_ready_when_the_window_expires():
    assistant, _, _, _ = make_assistant(["hey media"], window=0.2)
    say(assistant, 1)
    assert assistant.status == LISTENING
    import time
    time.sleep(0.3)
    assistant.tick()
    assert assistant.status == READY


def test_one_breath_command_ends_ready():
    assistant, media, _, _ = make_assistant(["hey media next"])
    say(assistant, 1)
    assert media.calls == ["next_track"]
    assert assistant.status == READY


def test_muted_is_shown_and_never_listening():
    assistant, _, _, _ = make_assistant(["hey media", "play"])
    assistant.set_muted(True)
    say(assistant, 2)
    assert assistant.status == MUTED
    assert LISTENING not in assistant.status_history


def test_muting_during_listening_shows_muted_not_ready():
    assistant, _, _, _ = make_assistant(["hey media"])
    say(assistant, 1)
    assistant.set_muted(True)
    # LISTENING -> MUTED directly: no "READY / awaiting wake word" in between
    assert list(assistant.status_history) == [LISTENING, MUTED]


def test_muting_does_not_announce_awaiting_wake_word():
    assistant, _, feedback, _ = make_assistant(["hey media"])
    say(assistant, 1)
    assistant.set_muted(True)
    idle_messages = [e for e in feedback.feedback_history if e.status == "idle"]
    assert idle_messages == []


def test_unmute_shows_ready_again():
    assistant, _, _, _ = make_assistant([])
    assistant.set_muted(True)
    assistant.set_muted(False)
    assert assistant.status == READY
    assert list(assistant.status_history) == [MUTED, READY]


def test_microphone_unavailable_is_shown_and_cancels_listening():
    assistant, _, _, _ = make_assistant(["hey media"])
    say(assistant, 1)
    assistant.set_microphone_available(False)
    assert assistant.status == UNAVAILABLE
    assert assistant.sessions.current_state == SystemState.IDLE
    assistant.set_microphone_available(True)
    assert assistant.status == READY


def test_muted_wins_over_unavailable():
    assistant, _, _, _ = make_assistant([])
    assistant.set_microphone_available(False)
    assistant.set_muted(True)
    assert assistant.status == MUTED


def test_status_line_is_printed_only_on_change(capsys):
    assistant, _, _, _ = make_assistant([])
    assistant._update_status()
    assistant._update_status()
    assistant.set_muted(True)
    assistant.set_muted(True)
    out = capsys.readouterr().out
    assert out.count("[STATUS] READY") == 1
    assert out.count("[STATUS] MUTED") == 1


# ------------------------------------------------------------------ US-17
@pytest.fixture
def no_network(monkeypatch):
    """Fail the test if anything tries to open a network connection."""
    attempts = []

    def refuse(self, address, *args, **kwargs):
        attempts.append(address)
        raise AssertionError(f"network connection attempted to {address!r}")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: refuse(None, a))
    return attempts


def test_whole_command_pipeline_runs_with_the_network_blocked(no_network):
    script = ["hey media", "play", "hey media", "volume up", "hey media pause"]
    assistant, media, _, _ = make_assistant(script)
    say(assistant, len(script))
    assert media.calls == ["play_media", "adjust_volume:up", "pause_media"]
    assert no_network == []


def test_default_recognizer_is_the_local_one():
    assert VoiceControlConfig().recognizer_backend == "vosk"
    assert VoskTranscriber.is_local is True
    assert GoogleTranscriber.is_local is False


def test_default_config_never_builds_a_cloud_recognizer(monkeypatch, tmp_path):
    """With the default backend, create_transcriber can only produce Vosk."""
    built = []
    monkeypatch.setattr(
        "voice_control.recognition.transcriber.VoskTranscriber.__init__",
        lambda self, *a, **k: built.append("vosk"),
    )
    monkeypatch.setattr(
        "voice_control.recognition.transcriber.GoogleTranscriber.__init__",
        lambda self, *a, **k: built.append("google"),
    )
    create_transcriber(VoiceControlConfig(vosk_model_path=str(tmp_path)), ["play"])
    assert built == ["vosk"]


def test_no_audio_is_written_to_disk(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    script = ["hey media", "next", "hey media", "previous"]
    assistant, _, _, _ = make_assistant(script)
    say(assistant, len(script))
    assert os.listdir(tmp_path) == []


def test_utterance_audio_is_discarded_after_use():
    segmenter = UtteranceSegmenter(VoiceControlConfig())
    result = None
    for chunk in utterance():
        result = segmenter.feed(chunk) or result
    assert result is not None
    assert len(segmenter._buffer) == 0          # nothing kept after handing it over


def test_rolling_buffer_never_grows_past_its_limit():
    config = VoiceControlConfig()
    buffer = AudioBuffer(
        max_bytes=config.buffer_max_bytes,
        sample_rate=config.sample_rate,
        bytes_per_sample=config.bytes_per_sample,
    )
    for _ in range(500):
        buffer.append(b"\x01\x00" * config.chunk_size)
    assert len(buffer.get_all()) <= config.buffer_max_bytes
