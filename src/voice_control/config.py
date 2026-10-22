"""
System Configuration for Voice Assistance for Multimedia Control.
Defines audio parameters, wake-word definitions, timeouts, and thresholds.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class VoiceControlConfig:
    """Configuration settings for voice capture, wake-word detection, and gating."""

    # Wake-word settings (SRS FR-1, SR-1)
    wake_word: str = "hey media"
    wake_word_aliases: List[str] = field(default_factory=lambda: ["hey media", "assistant", "computer"])
    detection_threshold: float = 0.65  # Confidence threshold for detection

    # Audio format settings (16 kHz, 16-bit PCM Mono - standard for embedded ASR)
    sample_rate: int = 16000
    channels: int = 1
    sample_width: int = 2  # 16-bit PCM = 2 bytes per sample
    chunk_size: int = 1024  # Samples per chunk (~64 ms per frame at 16kHz)

    # Buffer settings (SRS SR-2: In-memory rolling buffer only, never written to disk)
    rolling_buffer_seconds: float = 3.0

    # Listening window duration (Architecture 2.5: short fixed duration after wake word)
    listening_window_seconds: float = 4.0

    # Timing constraints (SRS FR-1: enter listening within 1.0s)
    max_wake_latency_seconds: float = 1.0

    # Command vocabulary (SRS 1.2: Play, Pause, Resume, Next, Previous, Volume Up, Volume Down)
    command_vocabulary: List[str] = field(
        default_factory=lambda: [
            "play",
            "pause",
            "resume",
            "next",
            "previous",
            "volume up",
            "volume down",
        ]
    )

    @property
    def bytes_per_sample(self) -> int:
        return self.sample_width * self.channels

    @property
    def chunk_bytes(self) -> int:
        return self.chunk_size * self.bytes_per_sample

    @property
    def buffer_max_bytes(self) -> int:
        return int(self.sample_rate * self.rolling_buffer_seconds * self.bytes_per_sample)
