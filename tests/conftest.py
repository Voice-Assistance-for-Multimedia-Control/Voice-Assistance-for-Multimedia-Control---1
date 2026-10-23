"""
Pytest configuration and audio fixtures for Voice Assistance for Multimedia Control.
"""

import sys
from pathlib import Path

# Add src to python path for all tests
ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import numpy as np
import pytest

from voice_control.config import VoiceControlConfig
from voice_control.detector.engine import AcousticPatternEngine, SimulatedEngine
from voice_control.detector.state import SessionManager
from voice_control.detector.wake_word import WakeWordDetector
from voice_control.security.validator import SecurityValidator


@pytest.fixture
def config():
    """Default test configuration with 2-second listening window."""
    return VoiceControlConfig(
        wake_word="hey media",
        listening_window_seconds=2.0,
        sample_rate=16000,
        chunk_size=1024,
    )


@pytest.fixture
def session_manager(config):
    """SessionManager instance for testing."""
    return SessionManager(window_duration_seconds=config.listening_window_seconds)


@pytest.fixture
def simulated_engine():
    """SimulatedEngine for deterministic test cases."""
    return SimulatedEngine()


@pytest.fixture
def acoustic_engine(config):
    """Real AcousticPatternEngine instance."""
    return AcousticPatternEngine(config)


@pytest.fixture
def wake_detector(config, simulated_engine, session_manager):
    """WakeWordDetector equipped with SimulatedEngine."""
    return WakeWordDetector(config=config, engine=simulated_engine, session_manager=session_manager)


@pytest.fixture
def live_pattern_detector(config, acoustic_engine, session_manager):
    """WakeWordDetector equipped with AcousticPatternEngine."""
    return WakeWordDetector(config=config, engine=acoustic_engine, session_manager=session_manager)


@pytest.fixture
def security_validator(session_manager):
    """SecurityValidator instance."""
    return SecurityValidator(session_manager)


@pytest.fixture
def sample_audio_chunk(config):
    """Generate a single frame of silence."""
    return np.zeros(config.chunk_size, dtype=np.int16).tobytes()


@pytest.fixture
def noise_audio_chunks(config):
    """Generate 20 chunks (~1.3s) of ambient background noise."""
    chunks = []
    for _ in range(20):
        data = (np.random.randn(config.chunk_size) * 800).astype(np.int16)
        chunks.append(data.tobytes())
    return chunks


@pytest.fixture
def wake_word_audio_chunk(config):
    """Generate an audio chunk containing the synthetic wake-word marker."""
    data = (np.random.randn(config.chunk_size) * 1500).astype(np.int16)
    b = bytearray(data.tobytes())
    marker = b"WAKE_WORD_MARKER_HEY_MEDIA"
    b[100 : 100 + len(marker)] = marker
    return bytes(b)
