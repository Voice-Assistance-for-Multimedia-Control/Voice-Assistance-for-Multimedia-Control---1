"""
Audio Capture Component (Hardware Layer).
Architecture 2.2: Continuously samples audio from the microphone into
a rolling buffer for the Wake-Word Detector.
Architecture 3.4: Handles hardware faults if audio stream disconnects.
"""

import logging
import threading
import time
from typing import Callable, Iterable, List, Optional

from voice_control.audio.buffer import AudioBuffer
from voice_control.config import VoiceControlConfig

logger = logging.getLogger(__name__)


class AudioCaptureComponent:
    """
    Manages live microphone audio capture or streaming input into a rolling AudioBuffer.
    Dispatches audio frames to registered frame callbacks (e.g. WakeWordDetector).
    """

    def __init__(self, config: Optional[VoiceControlConfig] = None):
        self.config = config or VoiceControlConfig()
        self.buffer = AudioBuffer(
            max_bytes=self.config.buffer_max_bytes,
            sample_rate=self.config.sample_rate,
            bytes_per_sample=self.config.bytes_per_sample,
        )

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callbacks: List[Callable[[bytes], None]] = []
        self._error_callbacks: List[Callable[[Exception], None]] = []
        self._lock = threading.Lock()

    def register_callback(self, callback: Callable[[bytes], None]) -> None:
        """Register a subscriber callback that receives each incoming audio chunk."""
        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable[[bytes], None]) -> None:
        """Unregister a subscriber callback."""
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

    def register_error_callback(self, callback: Callable[[Exception], None]) -> None:
        """Register an error subscriber for hardware / capture faults (Architecture 3.4)."""
        with self._lock:
            self._error_callbacks.append(callback)

    def feed_chunk(self, chunk: bytes) -> None:
        """
        Feed a raw audio chunk into the capture pipeline.
        Pushes to rolling buffer and dispatches to all registered callbacks.
        """
        if not chunk:
            return

        self.buffer.append(chunk)

        with self._lock:
            callbacks = list(self._callbacks)

        for cb in callbacks:
            try:
                cb(chunk)
            except Exception as e:
                logger.error(f"Error in audio frame callback: {e}", exc_info=True)

    def start_stream(self, stream_source: Optional[Iterable[bytes]] = None) -> None:
        """
        Start capturing audio in a background worker thread.
        If stream_source is provided (e.g. generator for testing), reads from it.
        Otherwise, attempts to bind to default microphone hardware.
        """
        if self._running:
            return

        self._running = True

        if stream_source is not None:
            self._thread = threading.Thread(
                target=self._run_stream_source, args=(stream_source,), daemon=True
            )
        else:
            self._thread = threading.Thread(target=self._run_hardware_mic, daemon=True)

        self._thread.start()
        logger.info("AudioCaptureComponent started.")

    def stop_stream(self) -> None:
        """Stop capturing audio and join the worker thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None
        logger.info("AudioCaptureComponent stopped.")

    def _run_stream_source(self, stream: Iterable[bytes]) -> None:
        """Worker loop reading from an iterable stream (files, test generators)."""
        try:
            for chunk in stream:
                if not self._running:
                    break
                self.feed_chunk(chunk)
        except Exception as e:
            logger.error(f"Hardware/Stream fault encountered: {e}")
            self._notify_error(e)
        finally:
            self._running = False

    def _run_hardware_mic(self) -> None:
        """Attempt live capture via sounddevice or pyaudio."""
        try:
            import sounddevice as sd

            def audio_callback(indata, frames, time_info, status):
                if status:
                    logger.warning(f"SoundDevice status warning: {status}")
                if self._running:
                    # Convert numpy int16 array to raw bytes
                    self.feed_chunk(bytes(indata))

            with sd.RawInputStream(
                samplerate=self.config.sample_rate,
                blocksize=self.config.chunk_size,
                channels=self.config.channels,
                dtype="int16",
                callback=audio_callback,
            ):
                while self._running:
                    time.sleep(0.05)

        except ImportError:
            logger.warning(
                "sounddevice not installed. Hardware capture unavailable without drivers. "
                "Use feed_chunk() or start_stream(generator) for simulated inputs."
            )
            # Sleep gracefully waiting for feed_chunk
            while self._running:
                time.sleep(0.05)
        except Exception as e:
            logger.error(f"Microphone hardware fault (Architecture 3.4, NFR-3): {e}")
            self._notify_error(e)
            self._running = False

    def _notify_error(self, err: Exception) -> None:
        with self._lock:
            handlers = list(self._error_callbacks)
        for h in handlers:
            try:
                h(err)
            except Exception:
                pass

    @property
    def is_running(self) -> bool:
        return self._running
