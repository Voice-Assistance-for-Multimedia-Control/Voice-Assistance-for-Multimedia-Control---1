"""Cross-platform YouTube player controlled through Selenium and Chrome.

This adapter starts a dedicated Chrome automation window. It does not attach
to or manipulate a teammate's existing browser session. Install Selenium with:
    python -m pip install selenium

The first run may require internet access so Selenium Manager can obtain a
compatible ChromeDriver. You must sign in / navigate to YouTube in the
automation window as needed.
"""
from __future__ import annotations

from typing import Optional


class YouTubePlayerError(RuntimeError):
    """Raised when the browser or YouTube player cannot perform an action."""


class YouTubePlayer:
    """State-aware YouTube controls using Selenium, on Windows/macOS/Linux."""

    def __init__(self, driver=None, start_url: str = "https://www.youtube.com"):
        # driver injection allows unit tests to use a fake without opening Chrome.
        self._driver = driver
        self._owns_driver = driver is None
        self._start_url = start_url

    def open(self) -> None:
        """Open a dedicated Chrome window if one is not already attached."""
        if self._driver is not None:
            return
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            options = Options()
            options.add_argument("--disable-notifications")
            self._driver = webdriver.Chrome(options=options)
            self._driver.get(self._start_url)
        except Exception as exc:
            raise YouTubePlayerError(
                "Could not start Chrome automation. Install selenium "
                "(`python -m pip install selenium`) and ensure Google Chrome is installed."
            ) from exc

    def _execute(self, action: str) -> bool:
        if action not in {"play", "pause", "resume"}:
            raise ValueError(f"Unsupported media action: {action}")
        if self._driver is None:
            raise YouTubePlayerError(
                "Chrome automation is not open. Call player.open() first."
            )
        try:
            result = self._driver.execute_script("""
                const action = arguments[0];
                const video = document.querySelector('video');
                if (!video) return 'no-video';
                if (action === 'pause') {
                    if (!video.paused) video.pause();
                    return video.paused ? 'ok' : 'failed';
                }
                if (action === 'play' || action === 'resume') {
                    if (video.paused || video.ended) {
                        const p = video.play();
                        if (p && p.catch) p.catch(() => {});
                    }
                    return 'requested';
                }
                return 'unsupported';
            """, action)
            if result == "no-video":
                raise YouTubePlayerError(
                    "No YouTube video is available in the controlled Chrome tab. "
                    "Open a video in the automation window first."
                )
            if result == "failed":
                return False
            if result in {"ok", "requested"}:
                return True
            return False
        except YouTubePlayerError:
            raise
        except Exception as exc:
            raise YouTubePlayerError(f"YouTube {action} failed: {exc}") from exc

    def play(self) -> bool:
        """Start playback if paused; leave an already-playing video alone."""
        return self._execute("play")

    def pause(self) -> bool:
        """Pause playback if playing; leave an already-paused video alone."""
        return self._execute("pause")

    def resume(self) -> bool:
        """Resume playback if paused; leave an already-playing video alone."""
        return self._execute("resume")

    def close(self) -> None:
        """Close only the Chrome window created by this player."""
        if self._driver is not None and self._owns_driver:
            self._driver.quit()
        self._driver = None
