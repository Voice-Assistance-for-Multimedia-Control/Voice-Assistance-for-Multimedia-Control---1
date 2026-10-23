"""Secure dispatch for the Play/Pause/Resume user stories."""
from __future__ import annotations

from voice_control.models.command import Command
from voice_control.security.validator import SecurityValidator
from voice_control.feedback.indicator import FeedbackModule
from voice_control.youtube_player import YouTubePlayer


class PlaybackCommandService:
    """Validate commands, call the player, and report success/error."""

    ALLOWED_COMMANDS = {"play", "pause", "resume"}

    def __init__(
        self,
        validator: SecurityValidator,
        media_player: YouTubePlayer,
        feedback: FeedbackModule,
    ):
        self.validator = validator
        self.media_player = media_player
        self.feedback = feedback

    def execute(self, command: Command) -> bool:
        if command.type not in self.ALLOWED_COMMANDS:
            self.feedback.notify("error")
            return False

        if not self.validator.validate_source(command):
            self.feedback.notify("error")
            return False

        try:
            success = getattr(self.media_player, command.type)()
        except Exception:
            self.feedback.notify("error")
            return False

        self.feedback.notify("ok" if success else "error")
        return bool(success)
