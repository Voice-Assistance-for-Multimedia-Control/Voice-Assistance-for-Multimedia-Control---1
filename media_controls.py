
"""Shared Selenium controls for YouTube media playback."""


_player = None


def get_player():
    """Open Chrome once and reuse the same YouTube player."""
    global _player

    if _player is None:
        from voice_control.youtube_player import YouTubePlayer

        player = YouTubePlayer()
        player.open()
        _player = player

    return _player


def _run(action):
    """Run a player action and return False if it fails."""
    try:
        return bool(getattr(get_player(), action)())
    except Exception as error:
        print(f"Could not {action}: {error}")
        return False


# US-02 / US-03 / US-04
def play_media():
    return _run("play")


def pause_media():
    return _run("pause")


def resume_media():
    return _run("resume")


# US-05
def next_track():
    """Skip to the next YouTube track."""
    try:
        player = get_player()
        player._driver.find_element(
            "css selector", ".ytp-next-button"
        ).click()
        return True
    except Exception as error:
        print(f"Could not skip to the next track: {error}")
        return False


# US-06
def previous_track():
    """Skip to the previous track in a YouTube playlist."""
    try:
        player = get_player()
        player._driver.find_element(
            "css selector", ".ytp-prev-button"
        ).click()
        return True
    except Exception as error:
        print(f"Could not go to the previous track: {error}")
        return False


# US-07
def adjust_volume(direction):
    """Adjust YouTube volume by exactly 10 percentage points."""
    if direction not in ("up", "down"):
        print("Invalid volume direction. Use 'up' or 'down'.")
        return False

    try:
        player = get_player()
        driver = player._driver

        result = driver.execute_script("""
            const video = document.querySelector('video');
            if (!video) return false;

            const change = arguments[0] === 'up' ? 0.1 : -0.1;
            video.volume = Math.max(
                0,
                Math.min(1, Math.round((video.volume + change) * 10) / 10)
            );

            return true;
        """, direction)

        return bool(result)

    except Exception as error:
        print(f"Could not adjust volume: {error}")
        return False
