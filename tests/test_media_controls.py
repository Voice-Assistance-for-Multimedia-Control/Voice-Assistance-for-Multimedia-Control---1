
import pytest
from unittest.mock import MagicMock

import media_controls


@pytest.fixture
def fake_player(monkeypatch):
    """Provide a fake shared Selenium player without opening Chrome."""
    player = MagicMock()
    player._driver = MagicMock()

    monkeypatch.setattr(media_controls, "get_player", lambda: player)
    return player

def test_next_track_success(fake_player):
    fake_player._driver.execute_script.return_value = True

    assert media_controls.next_track() is True
    fake_player._driver.execute_script.assert_called_once()
    assert ".ytp-next-button" in (
        fake_player._driver.execute_script.call_args.args[0]
    )


def test_next_track_failure(fake_player):
    fake_player._driver.execute_script.return_value = False

    assert media_controls.next_track() is False


def test_previous_track_success(fake_player):
    fake_player._driver.execute_script.return_value = True

    assert media_controls.previous_track() is True
    fake_player._driver.execute_script.assert_called_once()
    assert ".ytp-prev-button" in (
        fake_player._driver.execute_script.call_args.args[0]
    )


def test_previous_track_failure(fake_player):
    fake_player._driver.execute_script.return_value = False

    assert media_controls.previous_track() is False


@pytest.mark.parametrize(
    ("direction", "initial_volume", "expected_volume"),
    [
        ("up", 0.5, 0.6),
        ("down", 0.5, 0.4),
        ("up", 1.0, 1.0),
        ("down", 0.0, 0.0),
        ("up", 0.0, 0.1),
        ("down", 1.0, 0.9),
    ],
)
def test_adjust_volume(fake_player, direction, initial_volume, expected_volume):
    fake_player._driver.execute_script.return_value = True

    assert media_controls.adjust_volume(direction) is True

    script = fake_player._driver.execute_script.call_args.args[0]
    assert "video.volume" in script
    assert "Math.max" in script
    assert "Math.min" in script

    assert fake_player._driver.execute_script.call_args.args[1] == direction


def test_adjust_volume_invalid_direction(fake_player):
    assert media_controls.adjust_volume("sideways") is False

    fake_player._driver.execute_script.assert_not_called()


def test_adjust_volume_failure(fake_player):
    fake_player._driver.execute_script.side_effect = RuntimeError("no video")

    assert media_controls.adjust_volume("up") is False

@pytest.mark.parametrize(
    ("initial_volume", "direction", "expected"),
    [
        (0.5, "up", 0.6),
        (0.5, "down", 0.4),
        (0.9, "up", 1.0),
        (1.0, "up", 1.0),
        (0.1, "down", 0.0),
        (0.0, "down", 0.0),
    ],
)
def test_volume_calculation(initial_volume, direction, expected):
    change = 0.1 if direction == "up" else -0.1
    result = max(0, min(1, round((initial_volume + change) * 10) / 10))
    assert result == pytest.approx(expected)


def test_next_track_handles_disconnected_browser(fake_player, capsys):
    fake_player._driver.execute_script.side_effect = RuntimeError(
        "invalid session id"
    )

    assert media_controls.next_track() is False

    output = capsys.readouterr().out
    assert "Could not skip to the next track" in output
    assert "invalid session id" in output


def test_previous_track_handles_disconnected_browser(fake_player, capsys):
    fake_player._driver.execute_script.side_effect = RuntimeError(
        "invalid session id"
    )

    assert media_controls.previous_track() is False

    output = capsys.readouterr().out
    assert "Could not go to the previous track" in output
    assert "invalid session id" in output
