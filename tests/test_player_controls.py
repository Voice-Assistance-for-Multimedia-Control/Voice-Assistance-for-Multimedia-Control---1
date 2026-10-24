"""Unit tests for US-02/03/04 (play, pause, resume) using a fake player."""

import pytest

import media_controls


class FakePlayer:
    def __init__(self, result=True, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def _do(self, name):
        self.calls.append(name)
        if self.error:
            raise self.error
        return self.result

    def play(self):
        return self._do("play")

    def pause(self):
        return self._do("pause")

    def resume(self):
        return self._do("resume")


@pytest.fixture(autouse=True)
def clean_player():
    media_controls._player = None
    yield
    media_controls._player = None


CASES = [
    (media_controls.play_media, "play"),
    (media_controls.pause_media, "pause"),
    (media_controls.resume_media, "resume"),
]


@pytest.mark.parametrize("func, method", CASES)
def test_returns_true_on_success(func, method):
    fake = FakePlayer()
    media_controls._player = fake
    assert func() is True
    assert fake.calls == [method]


@pytest.mark.parametrize("func, method", CASES)
def test_returns_false_when_player_reports_failure(func, method):
    media_controls._player = FakePlayer(result=False)
    assert func() is False


@pytest.mark.parametrize("func, method", CASES)
def test_never_raises_when_player_raises(func, method):
    media_controls._player = FakePlayer(error=RuntimeError("no video"))
    assert func() is False


def test_get_player_opens_chrome_only_once(monkeypatch):
    opened = []

    class CountingPlayer:
        def open(self):
            opened.append(1)

    monkeypatch.setattr("voice_control.youtube_player.YouTubePlayer", CountingPlayer)
    assert media_controls.get_player() is media_controls.get_player()
    assert len(opened) == 1


def test_returns_false_when_chrome_cannot_start(monkeypatch):
    class BrokenPlayer:
        def open(self):
            raise RuntimeError("chrome missing")

    monkeypatch.setattr("voice_control.youtube_player.YouTubePlayer", BrokenPlayer)
    assert media_controls.play_media() is False
    assert media_controls._player is None