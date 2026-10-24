try:
    import pyautogui
    import pygetwindow as gw
except Exception:  # PyGetWindow does not support macOS
    pyautogui = None
    gw = None


# US-02 / US-03 / US-04: Play, Pause, Resume on one shared Selenium player
_player = None


def get_player():
    """Open Chrome once and return the same player on every call."""
    global _player
    if _player is None:
        from voice_control.youtube_player import YouTubePlayer

        player = YouTubePlayer()
        player.open()
        _player = player
    return _player


def _run(action):
    try:
        return bool(getattr(get_player(), action)())
    except Exception as error:
        print(f"Could not {action}: {error}")
        return False


def play_media():
    return _run("play")


def pause_media():
    return _run("pause")


def resume_media():
    return _run("resume")

def next_track():
    """Skip to the next track in a YouTube browser window."""
    try:
        windows = gw.getWindowsWithTitle("YouTube")
        if not windows:
            print("YouTube window not found.")
            return False

        window = windows[0]
        if window.isMinimized:
            window.restore()
        window.activate()
        pyautogui.hotkey("shift", "n")
        return True

    except Exception as error:
        print(f"Could not skip to the next track: {error}")
        return False


def previous_track():
    """Go to the previous track in a YouTube browser window."""
    try:
        windows = gw.getWindowsWithTitle("YouTube")
        if not windows:
            print("YouTube window not found.")
            return False

        window = windows[0]
        if window.isMinimized:
            window.restore()
        window.activate()
        pyautogui.hotkey("shift", "p")
        return True

    except Exception as error:
        print(f"Could not go to the previous track: {error}")
        return False


def adjust_volume(direction):
    """Increase or decrease YouTube volume."""
    try:
        windows = gw.getWindowsWithTitle("YouTube")
        if not windows:
            print("YouTube window not found.")
            return False

        window = windows[0]
        if window.isMinimized:
            window.restore()
        window.activate()

        if direction == "up":
            pyautogui.press("up")
        elif direction == "down":
            pyautogui.press("down")
        else:
            print("Invalid volume direction. Use 'up' or 'down'.")
            return False

        return True

    except Exception as error:
        print(f"Could not adjust volume: {error}")
        return False
