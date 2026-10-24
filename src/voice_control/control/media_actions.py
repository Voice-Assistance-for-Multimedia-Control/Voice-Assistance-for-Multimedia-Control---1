"""
Binds the seven command types to the agreed media_controls.py functions:

    US-02 play           -> play_media()
    US-03 pause          -> pause_media()
    US-04 resume         -> resume_media()
    US-05 next           -> next_track()
    US-06 previous       -> previous_track()
    US-07 volume up/down -> adjust_volume("up" | "down")

A function that is not in media_controls yet is bound to a stub that reports
failure, so the assistant still runs (and says which story is missing) while
teammates finish their parts.
"""

import logging
from types import ModuleType
from typing import Callable, Dict, Optional

from voice_control.control import command_mapper as cm

logger = logging.getLogger(__name__)

# command type -> (function name in media_controls, argument or None, story)
BINDINGS = {
    cm.PLAY: ("play_media", None, "US-02"),
    cm.PAUSE: ("pause_media", None, "US-03"),
    cm.RESUME: ("resume_media", None, "US-04"),
    cm.NEXT: ("next_track", None, "US-05"),
    cm.PREVIOUS: ("previous_track", None, "US-06"),
    cm.VOLUME_UP: ("adjust_volume", "up", "US-07"),
    cm.VOLUME_DOWN: ("adjust_volume", "down", "US-07"),
}


def _missing(name: str, story: str, reason: str) -> Callable[[], bool]:
    def stub() -> bool:
        logger.error("%s: media_controls.%s() is not available (%s)", story, name, reason)
        return False

    return stub


def bind_media_actions(
    module: Optional[ModuleType], import_error: Optional[str] = None
) -> Dict[str, Callable[[], bool]]:
    """Return {command type: zero-argument callable returning bool}."""
    actions: Dict[str, Callable[[], bool]] = {}
    for command_type, (name, arg, story) in BINDINGS.items():
        func = getattr(module, name, None) if module is not None else None
        if not callable(func):
            reason = import_error or "not implemented yet"
            actions[command_type] = _missing(name, story, reason)
        elif arg is None:
            actions[command_type] = func
        else:
            actions[command_type] = (lambda f=func, a=arg: f(a))
    return actions


def missing_functions(module: Optional[ModuleType]) -> list:
    """Names of agreed media_controls functions that do not exist yet."""
    names = sorted({name for name, _, _ in BINDINGS.values()})
    return [n for n in names if not callable(getattr(module, n, None))]
