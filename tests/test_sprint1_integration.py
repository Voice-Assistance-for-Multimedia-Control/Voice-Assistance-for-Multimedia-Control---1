"""
Sprint 1 end-to-end tests: the full pipeline driven through VoiceAssistant,
the same object main.py runs.

Audio is synthetic (tone bursts separated by silence) and the recognizer is
scripted, so each test controls exactly what is "heard" for each utterance.
Media functions are fakes that record calls.

Covers TC-01..TC-08 (all 7 commands via one runtime), TC-10 (no wake word,
speech-like audio), FR-9 (rejection), FR-10 (feedback) and the 4 s window rule.
"""

import time
import types

import numpy as np
import pytest

from voice_control.config import VoiceControlConfig
from voice_control.control.command_mapper import map_command
from voice_control.control.media_actions import bind_media_actions, missing_functions
from voice_control.detector.engine import TranscriptWakeWordEngine
from voice_control.feedback.indicator import FeedbackModule
from voice_control.models.command import Command, SystemState
from voice_control.recognition.transcriber import BaseTranscriber, Transcript
from voice_control.runtime import VoiceAssistant

SR = 16000
CHUNK = 1024


# --------------------------------------------------------------------- helpers
def speech(seconds=0.4):
    t = np.arange(int(seconds * SR)) / SR
    wave = 0.3 * np.sin(2 * np.pi * 220 * t)
    return (wave * 32767).astype(np.int16).tobytes()


def silence(seconds=0.6):
    return np.zeros(int(seconds * SR), dtype=np.int16).tobytes()


def chunks(pcm):
    step = CHUNK * 2
    return [pcm[i:i + step] for i in range(0, len(pcm), step)]


def utterance():
    """One spoken utterance followed by enough silence to end it."""
    return chunks(speech() + silence())


class ScriptedTranscriber(BaseTranscriber):
    """Returns the next scripted transcript for each utterance it is given."""

    def __init__(self, script, delay=0.0):
        self.script = list(script)
        self.delay = delay
        self.calls = 0

    def transcribe(self, pcm):
        self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        item = self.script.pop(0) if self.script else None
        if item is None:
            return None
        if isinstance(item, Exception):
            raise item
        text, conf = item if isinstance(item, tuple) else (item, 0.95)
        return Transcript(text, conf)


class FakeMedia:
    """Stands in for media_controls.py with the agreed function names."""

    def __init__(self, result=True):
        self.calls = []
        self.result = result

    def _rec(self, name):
        self.calls.append(name)
        return self.result

    def play_media(self): return self._rec("play_media")
    def pause_media(self): return self._rec("pause_media")
    def resume_media(self): return self._rec("resume_media")
    def next_track(self): return self._rec("next_track")
    def previous_track(self): return self._rec("previous_track")
    def adjust_volume(self, direction): return self._rec(f"adjust_volume:{direction}")


def make_assistant(script, media=None, window=4.0, delay=0.0, **cfg):
    config = VoiceControlConfig(listening_window_seconds=window, **cfg)
    transcriber = ScriptedTranscriber(script, delay=delay)
    feedback = FeedbackModule(enable_audio_tones=False)
    media = media or FakeMedia()
    assistant = VoiceAssistant(transcriber, bind_media_actions(media), config, feedback=feedback)
    return assistant, media, feedback, transcriber


def say(assistant, n=1):
    for _ in range(n):
        for c in utterance():
            assistant.process_chunk(c)


def statuses(feedback):
    return [e.status for e in feedback.feedback_history if e.status in ("ok", "error", "mic_error")]


# ----------------------------------------------------- TC-02..TC-08: all seven
@pytest.mark.parametrize(
    "spoken, expected_call",
    [
        ("play", "play_media"),                   # TC-02 / US-02
        ("pause", "pause_media"),                 # TC-03 / US-03
        ("resume", "resume_media"),               # TC-04 / US-04
        ("next", "next_track"),                   # TC-05 / US-05
        ("previous", "previous_track"),           # TC-06 / US-06
        ("volume up", "adjust_volume:up"),        # TC-07 / US-07
        ("volume down", "adjust_volume:down"),    # TC-08 / US-07
    ],
)
def test_each_command_runs_after_wake_word(spoken, expected_call):
    assistant, media, feedback, _ = make_assistant(["hey media", spoken])
    say(assistant, 2)
    assert media.calls == [expected_call]
    assert assistant.results[-1].success
    assert statuses(feedback) == ["ok"]           # FR-10
    assert assistant.sessions.current_state == SystemState.IDLE


def test_all_seven_commands_in_one_running_session_sequence():
    spoken = ["play", "pause", "resume", "next", "previous", "volume up", "volume down"]
    script = [x for cmd in spoken for x in ("hey media", cmd)]
    assistant, media, _, _ = make_assistant(script)
    say(assistant, len(script))
    assert media.calls == [
        "play_media", "pause_media", "resume_media", "next_track",
        "previous_track", "adjust_volume:up", "adjust_volume:down",
    ]


def test_wake_phrase_inside_a_sentence_still_counts():
    assistant, media, _, _ = make_assistant(["okay hey media", "play"])
    say(assistant, 2)
    assert media.calls == ["play_media"]


# --------------------------------------------------------------- TC-10 / SR-1
def test_command_words_without_wake_word_do_nothing():
    """Background speech containing command words never reaches the player."""
    assistant, media, feedback, transcriber = make_assistant(
        ["play", "pause the video", "volume up", "next song"]
    )
    say(assistant, 4)
    assert media.calls == []
    assert assistant.sessions.current_state == SystemState.IDLE
    assert transcriber.calls == 4                  # every utterance was checked
    assert statuses(feedback) == []


@pytest.mark.parametrize("heard", ["hey mediate", "hay medium", "media", "hey", "they media play"])
def test_similar_phrases_do_not_open_a_session(heard):
    assistant, media, _, _ = make_assistant([heard, "play"])
    say(assistant, 2)
    assert media.calls == []


def test_speech_like_audio_is_not_a_wake_word():
    """The old acoustic engine fired on any 2-4 syllable sound; this one checks words."""
    config = VoiceControlConfig()
    engine = TranscriptWakeWordEngine(ScriptedTranscriber(["turn it up"] * 3), config)
    syllables = b"".join(speech(0.18) + silence(0.12) for _ in range(3)) + silence(0.6)
    fired = [engine.process_chunk(c)[0] for c in chunks(syllables)]
    assert not any(fired)


def test_low_confidence_wake_word_is_ignored():
    assistant, media, _, _ = make_assistant([("hey media", 0.3), "play"])
    say(assistant, 2)
    assert media.calls == []


# ------------------------------------------------------ listening window rules
def test_one_command_per_wake_word():
    assistant, media, _, _ = make_assistant(["hey media", "play", "pause"])
    say(assistant, 3)
    assert media.calls == ["play_media"]

def test_new_wake_word_allows_next_command_after_session_ends():
    assistant, media, _, _ = make_assistant(
        ["hey media", "play", "hey media", "pause"]
    )

    say(assistant, 4)

    assert media.calls == ["play_media", "pause_media"]
    assert len(assistant.results) == 2
    assert assistant.sessions.current_state == SystemState.IDLE

def test_one_command_executes_only_once_per_wake_word():
    assistant, media, _, _ = make_assistant(["hey media", "play"])

    say(assistant, 2)

    assert media.calls.count("play_media") == 1
    assert len(assistant.results) == 1

def test_replayed_command_without_new_wake_word_is_ignored():
    assistant, media, _, _ = make_assistant(
        ["hey media", "play", "pause"]
    )

    say(assistant, 3)

    assert media.calls == ["play_media"]
    assert assistant.sessions.current_state == SystemState.IDLE


def test_identical_command_audio_replay_without_new_wake_word_is_ignored():
    assistant, media, _, _ = make_assistant(["hey media", "play"])

    wake_audio = utterance()
    command_audio = utterance()

    # Open a session, then execute one command.
    for chunk in wake_audio:
        assistant.process_chunk(chunk)

    for chunk in command_audio:
        assistant.process_chunk(chunk)

    assert media.calls == ["play_media"]

    # Replay the exact same command audio without a new wake word.
    for chunk in command_audio:
        assistant.process_chunk(chunk)

    assert media.calls == ["play_media"]
    assert len(assistant.results) == 1
    assert assistant.sessions.current_state == SystemState.IDLE


def test_command_after_window_expired_is_ignored():
    assistant, media, _, _ = make_assistant(["hey media", "play"], window=0.3)
    say(assistant, 1)
    assert assistant.sessions.current_state == SystemState.LISTENING
    time.sleep(0.4)
    say(assistant, 1)                              # treated as a non-wake utterance
    assert media.calls == []
    assert assistant.sessions.current_state == SystemState.IDLE


def test_command_recognized_after_expiry_is_rejected_by_validator():
    """Recognition that finishes after the window must not execute (decision 5)."""
    assistant, media, feedback, _ = make_assistant(
        ["hey media", "play"], window=1.0, delay=0.0
    )
    say(assistant, 1)                              # wake word
    assistant.transcriber.delay = 1.2              # command recognition is slow
    say(assistant, 1)
    assert media.calls == []
    assert assistant.results[-1].message == "rejected by security validator"
    assert statuses(feedback) == ["error"]


def test_tick_closes_an_expired_window_without_audio():
    assistant, _, _, _ = make_assistant(["hey media"], window=0.2)
    say(assistant, 1)
    time.sleep(0.3)
    assistant.tick()
    assert assistant.sessions.current_state == SystemState.IDLE


# ----------------------------------------------------- FR-9 and error handling
@pytest.mark.parametrize("heard", ["open netflix", "pause and play", "play next", None])
def test_unsupported_or_unclear_command_is_rejected(heard):
    assistant, media, feedback, _ = make_assistant(["hey media", heard])
    say(assistant, 2)
    assert media.calls == []
    assert statuses(feedback) == ["error"]
    assert assistant.sessions.current_state == SystemState.IDLE


def test_low_confidence_command_is_rejected():
    assistant, media, _, _ = make_assistant(["hey media", ("play", 0.2)])
    say(assistant, 2)
    assert media.calls == []


def test_recognizer_failure_does_not_crash():
    assistant, media, feedback, _ = make_assistant(["hey media", ConnectionError("offline")])
    say(assistant, 2)
    assert media.calls == []
    assert statuses(feedback) == ["error"]


def test_media_function_exception_does_not_crash():
    class Broken(FakeMedia):
        def play_media(self):
            raise RuntimeError("player closed")

    assistant, _, feedback, _ = make_assistant(["hey media", "play"], media=Broken())
    say(assistant, 2)
    assert not assistant.results[-1].success
    assert statuses(feedback) == ["error"]


def test_media_function_returning_false_gives_error_feedback():
    assistant, media, feedback, _ = make_assistant(
        ["hey media", "next"],
        media=FakeMedia(False),
    )
    say(assistant, 2)

    assert media.calls == ["next_track"]
    assert assistant.results[-1].success is False
    assert statuses(feedback) == ["error"]

# ------------------------------------------------------------- wiring checks
def test_detector_and_validator_share_one_session_manager():
    assistant, _, _, _ = make_assistant([])
    assert assistant.detector.session_manager is assistant.sessions
    assert assistant.validator.session_manager is assistant.sessions


def test_command_has_no_session_unless_one_is_passed():
    assert Command(type="play", confidence=0.9).session_id is None


def test_missing_media_function_is_reported_and_fails_safely():
    partial = types.SimpleNamespace(next_track=lambda: True)
    actions = bind_media_actions(partial)
    assert actions["next"]() is True
    assert actions["play"]() is False
    assert "play_media" in missing_functions(partial)
    assert missing_functions(None)  # module failed to import


# ------------------------------------------------------------- command mapper
@pytest.mark.parametrize(
    "text, expected",
    [
        ("Play", "play"), ("pause", "pause"), ("resume", "resume"),
        ("next", "next"), ("next track", "next"), ("Next song.", "next"),
        ("previous", "previous"), ("previous track", "previous"),
        ("volume up", "volume up"), ("Volume Down", "volume down"),
        ("please pause the video", "pause"),
    ],
)
def test_map_command_accepts_vocabulary(text, expected):
    cmd = map_command(text, 0.9, session_id="tok")
    assert cmd.type == expected
    assert cmd.session_id == "tok"
    assert cmd.confidence == 0.9


@pytest.mark.parametrize(
    "text",
    [
        "",
        "hello",
        "pause and play",
        "play next",
        "volume",
        "up",
        "stop music",
        "send an email",
        "turn on the lights",
    ],
)
def test_map_command_rejects_everything_else(text):
    assert map_command(text) is None


# ------------------------------------------- wake word + command in one breath
@pytest.mark.parametrize(
    "heard, expected",
    [
        ("hey media play", "play_media"),
        ("hey media pause the video", "pause_media"),
        ("hey media volume up", "adjust_volume:up"),
        ("okay hey media next", "next_track"),
    ],
)
def test_wake_word_and_command_in_one_utterance(heard, expected):
    assistant, media, feedback, _ = make_assistant([heard])
    say(assistant, 1)
    assert media.calls == [expected]
    assert statuses(feedback) == ["ok"]
    assert assistant.sessions.current_state == SystemState.IDLE


def test_wake_word_with_non_command_words_keeps_window_open():
    assistant, media, _, _ = make_assistant(["hey media um", "pause"])
    say(assistant, 2)
    assert media.calls == ["pause_media"]


def test_command_before_wake_word_is_not_executed():
    assistant, media, _, _ = make_assistant(["play hey media"])
    say(assistant, 1)
    assert media.calls == []
    assert assistant.sessions.current_state == SystemState.LISTENING


def test_one_breath_command_still_needs_confidence():
    assistant, media, _, _ = make_assistant([("hey media play", 0.3)])
    say(assistant, 1)
    assert media.calls == []
