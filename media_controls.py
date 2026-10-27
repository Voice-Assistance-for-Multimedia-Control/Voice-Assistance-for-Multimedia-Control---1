"""Shared Selenium controls for YouTube media playback."""

_player = None


def _error_summary(error):
    """Return a concise error message without the full stack trace."""
    lines = str(error).splitlines()
    return lines[0] if lines else type(error).__name__

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
        print(f"Could not {action}: {_error_summary(error)}")
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
    """Skip to the next YouTube track and verify that it changed."""
    try:
        player = get_player()
        result = player._driver.execute_async_script("""
            const done = arguments[arguments.length - 1];
            const video = document.querySelector('video');
            const button = document.querySelector('.ytp-next-button');

            if (!video || !button || button.disabled) {
                done(false);
                return;
            }

            const oldVideo = video.currentSrc;
            button.click();

            const start = Date.now();
            const check = () => {
                const current = document.querySelector('video');
                if (current && current.currentSrc &&
                    current.currentSrc !== oldVideo) {
                    done(true);
                } else if (Date.now() - start >= 3000) {
                    done(false);
                } else {
                    setTimeout(check, 100);
                }
            };
            check();
        """)
        return result is True
    except Exception as error:
        print(f"Could not skip to the next track: {_error_summary(error)}")
        return False


# US-06
def previous_track():
    """Go to the previous YouTube track and verify that it changed."""
    try:
        player = get_player()
        result = player._driver.execute_async_script("""
            const done = arguments[arguments.length - 1];
            const video = document.querySelector('video');
            const button = document.querySelector('.ytp-prev-button');

            if (!video || !button || button.disabled) {
                done(false);
                return;
            }

            const oldVideo = video.currentSrc;
            button.click();

            const start = Date.now();
            const check = () => {
                const current = document.querySelector('video');
                if (current && current.currentSrc &&
                    current.currentSrc !== oldVideo) {
                    done(true);
                } else if (Date.now() - start >= 3000) {
                    done(false);
                } else {
                    setTimeout(check, 100);
                }
            };
            check();
        """)
        return result is True
    except Exception as error:
        print(f"Could not go to the previous track: {_error_summary(error)}")
        return False


# US-07
def adjust_volume(direction):
    """Adjust volume by 10 percentage points and verify the result."""
    if direction not in ("up", "down"):
        print("Invalid volume direction. Use 'up' or 'down'.")
        return False

    try:
        player = get_player()
        result = player._driver.execute_script("""
            const video = document.querySelector('video');
            if (!video) return false;

            const before = video.volume;
            const change = arguments[0] === 'up' ? 0.1 : -0.1;
            const expected = Math.max(
                0,
                Math.min(1, Math.round((before + change) * 10) / 10)
            );

            video.volume = expected;
            return Math.abs(video.volume - expected) < 0.001;
        """, direction)

        return result is True
    except Exception as error:
        print(f"Could not adjust volume: {_error_summary(error)}")
        return False

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
        print(f"Could not {action}: {_error_summary(error)}")
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
    """Skip to the next YouTube track and verify that it changed."""
    try:
        player = get_player()
        result = player._driver.execute_async_script("""
            const done = arguments[arguments.length - 1];
            const video = document.querySelector('video');
            const button = document.querySelector('.ytp-next-button');

            if (!video || !button || button.disabled) {
                done(false);
                return;
            }

            const oldVideo = video.currentSrc;
            button.click();

            const start = Date.now();
            const check = () => {
                const current = document.querySelector('video');
                if (current && current.currentSrc &&
                    current.currentSrc !== oldVideo) {
                    done(true);
                } else if (Date.now() - start >= 3000) {
                    done(false);
                } else {
                    setTimeout(check, 100);
                }
            };
            check();
        """)
        return result is True
    except Exception as error:
        print(f"Could not skip to the next track: {_error_summary(error)}")
        return False


# US-06
def previous_track():
    """Go to the previous YouTube track and verify that it changed."""
    try:
        player = get_player()
        result = player._driver.execute_async_script("""
            const done = arguments[arguments.length - 1];
            const video = document.querySelector('video');
            const button = document.querySelector('.ytp-prev-button');

            if (!video || !button || button.disabled) {
                done(false);
                return;
            }

            const oldVideo = video.currentSrc;
            button.click();

            const start = Date.now();
            const check = () => {
                const current = document.querySelector('video');
                if (current && current.currentSrc &&
                    current.currentSrc !== oldVideo) {
                    done(true);
                } else if (Date.now() - start >= 3000) {
                    done(false);
                } else {
                    setTimeout(check, 100);
                }
            };
            check();
        """)
        return result is True
    except Exception as error:
        print(f"Could not go to the previous track: {_error_summary(error)}")
        return False


# US-07
def adjust_volume(direction):
    """Adjust volume by 10 percentage points and verify the result."""
    if direction not in ("up", "down"):
        print("Invalid volume direction. Use 'up' or 'down'.")
        return False

    try:
        player = get_player()
        result = player._driver.execute_script("""
            const video = document.querySelector('video');
            if (!video) return false;

            const before = video.volume;
            const change = arguments[0] === 'up' ? 0.1 : -0.1;
            const expected = Math.max(
                0,
                Math.min(1, Math.round((before + change) * 10) / 10)
            );

            video.volume = expected;
            return Math.abs(video.volume - expected) < 0.001;
        """, direction)

        return result is True
    except Exception as error:
        print(f"Could not adjust volume: {_error_summary(error)}")
        return False
