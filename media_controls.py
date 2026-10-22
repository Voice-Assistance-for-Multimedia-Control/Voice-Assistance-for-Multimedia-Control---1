import pyautogui
import pygetwindow as gw


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
