"""
Energy-based utterance segmenter (voice-activity detection).

Splits a continuous stream of 16-bit PCM chunks into complete utterances:
an utterance starts when frame energy rises above a threshold and ends after a
configurable stretch of silence (or when it reaches a maximum length).

Used by both the wake-word engine and the command listener so that the speech
recognizer is only ever given one short, complete utterance at a time.
Audio stays in memory only (SR-2).
"""

from typing import Optional

import numpy as np

from voice_control.config import VoiceControlConfig


def frame_rms(chunk: bytes) -> float:
    """Root-mean-square energy of a 16-bit PCM chunk, normalised to 0..1."""
    usable = len(chunk) - (len(chunk) % 2)
    if usable <= 0:
        return 0.0
    samples = np.frombuffer(chunk[:usable], dtype=np.int16).astype(np.float32) / 32768.0
    return float(np.sqrt(np.mean(samples ** 2)))


class UtteranceSegmenter:
    """Collects chunks into utterances using frame energy."""

    def __init__(self, config: Optional[VoiceControlConfig] = None):
        self.config = config or VoiceControlConfig()
        self._bytes_per_second = self.config.sample_rate * self.config.bytes_per_sample
        self._buffer = bytearray()
        self._in_speech = False
        self._silence_bytes = 0
        self._speech_bytes = 0
        # Silence (seconds) that ended the most recent utterance. The speaker
        # actually stopped this long before feed() returned it (NFR-1 timing).
        self.last_trailing_silence_seconds = 0.0

    def reset(self) -> None:
        self._buffer.clear()
        self._in_speech = False
        self._silence_bytes = 0
        self._speech_bytes = 0

    @property
    def in_speech(self) -> bool:
        return self._in_speech

    def feed(self, chunk: bytes) -> Optional[bytes]:
        """
        Add one chunk. Returns the complete utterance (raw PCM bytes) when one
        has just ended, otherwise None.
        """
        if not chunk:
            return None

        is_speech = frame_rms(chunk) >= self.config.vad_energy_threshold

        if not self._in_speech:
            if not is_speech:
                return None
            self._in_speech = True
            self._buffer.clear()
            self._silence_bytes = 0
            self._speech_bytes = 0

        self._buffer.extend(chunk)
        if is_speech:
            self._speech_bytes += len(chunk)
            self._silence_bytes = 0
        else:
            self._silence_bytes += len(chunk)

        seconds = len(self._buffer) / self._bytes_per_second
        silence = self._silence_bytes / self._bytes_per_second
        ended = (
            silence >= self.config.vad_end_silence_seconds
            or seconds >= self.config.vad_max_utterance_seconds
        )
        if not ended:
            return None

        utterance = bytes(self._buffer)
        speech_seconds = self._speech_bytes / self._bytes_per_second
        self.last_trailing_silence_seconds = silence
        self.reset()
        if speech_seconds < self.config.vad_min_utterance_seconds:
            return None  # a click or a cough, not an utterance
        return utterance
