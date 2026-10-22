import pyautogui
import pygetwindow as gw


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
