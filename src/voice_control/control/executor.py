"""
Command Executor (Architecture 2.2 / 3.3).

``execute(command) -> ExecutionResult`` is the only path from a recognized
command to a media action:

1. reject unknown command types (FR-9),
2. ask the SecurityValidator (final gate, Architecture 2.5),
3. call the registered media function,
4. report success or failure through the FeedbackModule (FR-10).

Media functions are registered in a table, so adding a command means adding
one entry, not editing this logic (NFR-6). Every failure is handled here;
nothing is raised to the caller.
"""

import logging
from typing import Callable, Dict, Optional

from voice_control.feedback.indicator import FeedbackModule
from voice_control.models.command import Command, ExecutionResult
from voice_control.security.error_handler import (
    ErrorHandler,
    SecurityGatingError,
    UnrecognizedCommandError,
)
from voice_control.security.validator import SecurityValidator

logger = logging.getLogger(__name__)

MediaAction = Callable[[], bool]


class CommandExecutor:
    def __init__(
        self,
        validator: SecurityValidator,
        actions: Dict[str, MediaAction],
        feedback: Optional[FeedbackModule] = None,
        error_handler: Optional[ErrorHandler] = None,
    ):
        self.validator = validator
        self.actions = dict(actions)
        self.feedback = feedback or FeedbackModule()
        self.error_handler = error_handler or ErrorHandler(self.feedback)

    def execute(self, command: Command) -> ExecutionResult:
        if command is None or command.type not in self.actions:
            kind = getattr(command, "type", None)
            self.error_handler.handle_error(
                UnrecognizedCommandError(f"No media action registered for {kind!r}")
            )
            return ExecutionResult(False, "unsupported command", kind)

        if not self.validator.validate_source(command):
            # Security failure: the media function is never called (Architecture 3.4).
            self.error_handler.handle_error(
                SecurityGatingError(f"Command '{command.type}' rejected by security validator")
            )
            return ExecutionResult(False, "rejected by security validator", command.type)

        try:
            ok = bool(self.actions[command.type]())
        except Exception as exc:  # a media failure must not crash the assistant
            self.error_handler.handle_error(exc)
            return ExecutionResult(False, f"media action failed: {exc}", command.type)

        if ok:
            self.feedback.notify("ok")
            logger.info("Executed '%s'", command.type)
            return ExecutionResult(True, "executed", command.type)

        self.feedback.notify("error")
        logger.warning("Media action '%s' reported failure", command.type)
        return ExecutionResult(False, "media action reported failure", command.type)
