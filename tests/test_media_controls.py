
import pytest
from unittest.mock import MagicMock, patch

from media_controls import next_track, previous_track, adjust_volume


@pytest.fixture
def youtube_window():
    window = MagicMock()
    window.isMinimized = False
    return window


@patch("media_controls.pyautogui.hotkey")
@patch("media_controls.gw.getWindowsWithTitle")
def test_next_track_success(mock_get_windows, mock_hotkey, youtube_window):
    mock_get_windows.return_value = [youtube_window]

    assert next_track() is True

    mock_get_windows.assert_called_once_with("YouTube")
    youtube_window.activate.assert_called_once()
    mock_hotkey.assert_called_once_with("shift", "n")


@patch("media_controls.gw.getWindowsWithTitle", return_value=[])
def test_next_track_no_youtube_window(mock_get_windows):
    assert next_track() is False

    mock_get_windows.assert_called_once_with("YouTube")


@patch("media_controls.pyautogui.hotkey")
@patch("media_controls.gw.getWindowsWithTitle")
def test_previous_track_success(mock_get_windows, mock_hotkey, youtube_window):
    mock_get_windows.return_value = [youtube_window]

    assert previous_track() is True

    mock_get_windows.assert_called_once_with("YouTube")
    youtube_window.activate.assert_called_once()
    mock_hotkey.assert_called_once_with("shift", "p")


@patch("media_controls.gw.getWindowsWithTitle", return_value=[])
def test_previous_track_no_youtube_window(mock_get_windows):
    assert previous_track() is False

    mock_get_windows.assert_called_once_with("YouTube")


@pytest.mark.parametrize(
    ("direction", "expected_key"),
    [
        ("up", "up"),
        ("down", "down"),
    ],
)
@patch("media_controls.pyautogui.press")
@patch("media_controls.gw.getWindowsWithTitle")
def test_adjust_volume_success(
    mock_get_windows,
    mock_press,
    direction,
    expected_key,
    youtube_window,
):
    mock_get_windows.return_value = [youtube_window]

    assert adjust_volume(direction) is True

    mock_get_windows.assert_called_once_with("YouTube")
    youtube_window.activate.assert_called_once()
    mock_press.assert_called_once_with(expected_key)


@patch("media_controls.gw.getWindowsWithTitle")
def test_adjust_volume_invalid_direction(mock_get_windows, youtube_window):
    mock_get_windows.return_value = [youtube_window]

    assert adjust_volume("sideways") is False

    mock_get_windows.assert_called_once_with("YouTube")
    youtube_window.activate.assert_called_once()


@patch("media_controls.gw.getWindowsWithTitle", return_value=[])
def test_adjust_volume_no_youtube_window(mock_get_windows):
    assert adjust_volume("up") is False

    mock_get_windows.assert_called_once_with("YouTube")
