"""
Audio Buffer Component.
Implements the rolling in-memory audio buffer specified in Architecture 3.5.
Strictly satisfies SR-2 (Local-only processing, zero disk persistence).
"""

from collections import deque
import threading
from typing import Optional


class AudioBuffer:
    """
    Thread-safe circular in-memory buffer storing raw PCM audio chunks.
    Oldest chunks are continuously evicted when capacity is reached.
    """

    def __init__(self, max_bytes: int, sample_rate: int = 16000, bytes_per_sample: int = 2):
        if max_bytes <= 0:
            raise ValueError("max_bytes must be strictly positive")
        self.max_bytes = max_bytes
        self.sample_rate = sample_rate
        self.bytes_per_sample = bytes_per_sample

        self._lock = threading.Lock()
        self._chunks: deque = deque()
        self._current_size = 0

    def append(self, chunk: bytes) -> None:
        """
        Append a raw PCM audio chunk to the buffer.
        Evicts oldest chunks when total size exceeds max_bytes.
        """
        if not chunk:
            return

        with self._lock:
            self._chunks.append(chunk)
            self._current_size += len(chunk)

            while self._current_size > self.max_bytes and len(self._chunks) > 1:
                dropped = self._chunks.popleft()
                self._current_size -= len(dropped)

    def get_latest(self, seconds: Optional[float] = None) -> bytes:
        """
        Retrieve up to `seconds` of the most recent audio samples as contiguous bytes.
        If seconds is None, returns the entire buffer content.
        """
        with self._lock:
            if not self._chunks:
                return b""

            full_data = b"".join(self._chunks)
            if seconds is None:
                return full_data

            desired_bytes = int(seconds * self.sample_rate * self.bytes_per_sample)
            if desired_bytes >= len(full_data):
                return full_data
            return full_data[-desired_bytes:]

    def get_all(self) -> bytes:
        """Retrieve all currently buffered audio bytes."""
        return self.get_latest(None)

    def clear(self) -> None:
        """Completely flush the buffer in memory."""
        with self._lock:
            self._chunks.clear()
            self._current_size = 0

    @property
    def current_size(self) -> int:
        """Current size in bytes."""
        with self._lock:
            return self._current_size

    @property
    def duration_seconds(self) -> float:
        """Current buffered duration in seconds."""
        with self._lock:
            return self._current_size / (self.sample_rate * self.bytes_per_sample)

    def is_empty(self) -> bool:
        """Return True if the buffer contains no audio."""
        with self._lock:
            return self._current_size == 0
