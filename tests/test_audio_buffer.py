"""
Tests for AudioBuffer Component.
Traceability: Security Requirement SR-2 (In-memory rolling buffer only, zero disk persistence).
"""

import threading
import numpy as np
import pytest

from voice_control.audio.buffer import AudioBuffer


class TestAudioBuffer:
    """Verifies AudioBuffer memory rolling and privacy guarantees (SR-2)."""

    def test_buffer_initialization(self):
        buf = AudioBuffer(max_bytes=32000, sample_rate=16000, bytes_per_sample=2)
        assert buf.max_bytes == 32000
        assert buf.current_size == 0
        assert buf.is_empty() is True
        assert buf.duration_seconds == 0.0

    def test_buffer_append_and_eviction(self):
        """Verify that older data is evicted when buffer reaches maximum capacity."""
        # 16000 Hz * 2 bytes = 32000 bytes per second. Set max capacity to 1000 bytes (~0.03s)
        buf = AudioBuffer(max_bytes=1000)

        chunk1 = b"A" * 600
        chunk2 = b"B" * 600

        buf.append(chunk1)
        assert buf.current_size == 600

        # Adding chunk2 pushes total to 1200 > 1000, so chunk1 must be evicted
        buf.append(chunk2)
        assert buf.current_size <= 1000
        # The buffer must now contain chunk2 data, not old chunk1 data
        assert b"B" in buf.get_all()

    def test_get_latest_duration(self):
        """Verify get_latest returns the exact requested audio duration."""
        # 16000 Hz, 2 bytes/sample -> 32000 bytes per second
        buf = AudioBuffer(max_bytes=64000, sample_rate=16000, bytes_per_sample=2)

        # Append 1.0 second of audio (32000 bytes)
        one_sec_audio = b"\x01\x00" * 16000
        buf.append(one_sec_audio)

        # Retrieve 0.5 seconds (should be 16000 bytes)
        half_sec = buf.get_latest(0.5)
        assert len(half_sec) == 16000

        # Retrieve full 1.0 second
        full_sec = buf.get_latest(1.0)
        assert len(full_sec) == 32000

        # Requesting more than buffered returns all available
        more = buf.get_latest(2.0)
        assert len(more) == 32000

    def test_clear_buffer(self):
        """Verify clear() wipes all audio data from memory."""
        buf = AudioBuffer(max_bytes=32000)
        buf.append(b"\x12\x34" * 100)
        assert not buf.is_empty()

        buf.clear()
        assert buf.is_empty() is True
        assert buf.current_size == 0
        assert buf.get_all() == b""

    def test_thread_safety(self):
        """Verify thread-safe concurrent writes to AudioBuffer."""
        buf = AudioBuffer(max_bytes=100000)
        errors = []

        def worker(fill_byte: bytes):
            try:
                for _ in range(50):
                    buf.append(fill_byte * 200)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=worker, args=(b"X",)),
            threading.Thread(target=worker, args=(b"Y",)),
            threading.Thread(target=worker, args=(b"Z",)),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert buf.current_size > 0
