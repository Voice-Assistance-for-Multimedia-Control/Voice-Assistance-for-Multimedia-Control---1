"""
Command Mapper (Architecture 2.2 / 3.3).

``map_command(text)`` turns recognized text into exactly one of the seven
Sprint 1 commands, or ``None`` (FR-9). The whole utterance must match a known
phrase after filler words are removed, so "pause and play" or "play the next
one" are rejected instead of guessed.
"""

import re
from typing import Dict, List, Optional

from voice_control.models.command import Command

# Canonical command types (SRS 1.2), in Sprint 1 story order US-02..US-07.
PLAY = "play"
PAUSE = "pause"
RESUME = "resume"
NEXT = "next"
PREVIOUS = "previous"
VOLUME_UP = "volume up"
VOLUME_DOWN = "volume down"

COMMAND_TYPES: List[str] = [PLAY, PAUSE, RESUME, NEXT, PREVIOUS, VOLUME_UP, VOLUME_DOWN]

# Accepted spoken phrases -> command type. The SRS words themselves come first.
PHRASES: Dict[str, str] = {
    "play": PLAY,
    "pause": PAUSE,
    "stop": PAUSE,
    "resume": RESUME,
    "continue": RESUME,
    "next": NEXT,
    "next track": NEXT,
    "next song": NEXT,
    "skip": NEXT,
    "previous": PREVIOUS,
    "previous track": PREVIOUS,
    "previous song": PREVIOUS,
    "volume up": VOLUME_UP,
    "increase volume": VOLUME_UP,
    "louder": VOLUME_UP,
    "volume down": VOLUME_DOWN,
    "decrease volume": VOLUME_DOWN,
    "quieter": VOLUME_DOWN,
}

# Words that may surround a command without changing it.
FILLER_WORDS = {"please", "the", "a", "media", "music", "video", "youtube", "now"}


def normalize(text: str) -> str:
    words = re.sub(r"[^a-z\s]", " ", (text or "").lower()).split()
    return " ".join(w for w in words if w not in FILLER_WORDS)


def map_command(
    text: str, confidence: float = 1.0, session_id: Optional[str] = None
) -> Optional[Command]:
    """
    Architecture 3.3: map_command(text) -> Command {type, confidence} or None.

    ``session_id`` should be the active wake-word session token; it is passed
    through so the SecurityValidator can authorize the command.
    """
    phrase = normalize(text)
    command_type = PHRASES.get(phrase)
    if command_type is None:
        return None
    return Command(type=command_type, confidence=confidence, session_id=session_id)
def recognizer_phrases(wake_word: str) -> List[str]:
    """Phrases needed for wake-word, command, and rejection testing."""
    unsupported_test_phrases = [
        "open instagram",
        "take a screenshot",
        "send an email",
        "turn on the lights",
        "check the weather",
    ]

    return (
        [wake_word.lower()]
        + list(PHRASES)
        + sorted(FILLER_WORDS)
        + unsupported_test_phrases
    )
