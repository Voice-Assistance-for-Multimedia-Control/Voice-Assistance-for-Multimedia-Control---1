"""Unit tests for dispatch logic; these do not launch Chrome."""
from voice_control.playback_command_service import PlaybackCommandService
from voice_control.youtube_player import YouTubePlayer


class FakeValidator:
    def __init__(self, allowed=True):
        self.allowed = allowed

    def validate_source(self, command):
        return self.allowed


class FakePlayer:
    def __init__(self, result=True):
        self.result = result
        self.calls = []

    def play(self):
        self.calls.append("play")
        return self.result

    def pause(self):
        self.calls.append("pause")
        return self.result

    def resume(self):
        self.calls.append("resume")
        return self.result


class FakeFeedback:
    def __init__(self):
        self.statuses = []

    def notify(self, status):
        self.statuses.append(status)


class FakeCommand:
    def __init__(self, command_type):
        self.type = command_type


def test_play_pause_resume_dispatch():
    player, feedback = FakePlayer(), FakeFeedback()
    service = PlaybackCommandService(FakeValidator(), player, feedback)
    for action in ("play", "pause", "resume"):
        assert service.execute(FakeCommand(action))
    assert player.calls == ["play", "pause", "resume"]
    assert feedback.statuses == ["ok", "ok", "ok"]


def test_invalid_session_is_rejected():
    player, feedback = FakePlayer(), FakeFeedback()
    service = PlaybackCommandService(FakeValidator(False), player, feedback)
    assert not service.execute(FakeCommand("play"))
    assert player.calls == []
    assert feedback.statuses == ["error"]


def test_unknown_command_is_rejected():
    player, feedback = FakePlayer(), FakeFeedback()
    service = PlaybackCommandService(FakeValidator(), player, feedback)
    assert not service.execute(FakeCommand("next"))
    assert player.calls == []
    assert feedback.statuses == ["error"]


def test_playback_failure_reports_error():
    player, feedback = FakePlayer(False), FakeFeedback()
    service = PlaybackCommandService(FakeValidator(), player, feedback)
    assert not service.execute(FakeCommand("pause"))
    assert feedback.statuses == ["error"]


def test_youtube_player_requires_open_before_action():
    player = YouTubePlayer()
    try:
        player.pause()
    except RuntimeError as exc:
        assert "not open" in str(exc)
    else:
        raise AssertionError("Expected player to require an open browser")
