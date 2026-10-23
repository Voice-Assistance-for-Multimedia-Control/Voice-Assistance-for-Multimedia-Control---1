"""
Data Models for Voice Assistance for Multimedia Control.
Implements the Command object and ExecutionResult from Architecture Specification 3.5.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
import uuid


class SystemState(str, Enum):
    """System state machine states."""
    IDLE = "IDLE"                    # Awaiting wake word
    LISTENING = "LISTENING"          # Wake word detected; active listening window open
    PROCESSING = "PROCESSING"        # Transcribing and validating command
    COOLDOWN = "COOLDOWN"            # Window closed; transitioning back to idle


@dataclass
class Command:
    """
    Structured command object.
    Architecture 3.5: {type: string, confidence: float, timestamp: datetime}.
    Includes session_id to enable security validator gating (SO-1, SR-1).
    """
    type: str
    confidence: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    session_id: Optional[str] = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id,
        }


@dataclass
class ExecutionResult:
    """Result of command execution on the media player."""
    success: bool
    message: str
    command_type: Optional[str] = None
    executed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
