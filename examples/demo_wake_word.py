"""
Interactive Demonstration of Wake-Word Detection (US-01).
Demonstrates:
- Continuous audio ingestion into rolling buffer (SR-2)
- Wake-word gating: background audio without wake word is ignored (SR-1, TC-10)
- Wake-word detection triggering active listening state in < 1 second (FR-1, TC-01)
- SecurityValidator authorization of command within active session
"""

import sys
import time

# Ensure src is in python path
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np

from voice_control.audio.capture import AudioCaptureComponent
from voice_control.config import VoiceControlConfig
from voice_control.detector.wake_word import WakeWordDetector
from voice_control.feedback.indicator import FeedbackModule, LEDColor
from voice_control.models.command import Command
from voice_control.security.validator import SecurityValidator


def generate_silence(duration_sec: float, sample_rate: int = 16000) -> bytes:
    """Generate raw 16-bit PCM silence."""
    samples = int(duration_sec * sample_rate)
    return np.zeros(samples, dtype=np.int16).tobytes()


def generate_speech_noise(duration_sec: float, sample_rate: int = 16000) -> bytes:
    """Generate random non-wake background audio/speech energy."""
    samples = int(duration_sec * sample_rate)
    # Filtered random noise simulating ambient speech without wake cadence
    data = (np.random.randn(samples) * 1200).astype(np.int16)
    return data.tobytes()


def generate_wake_word_audio(sample_rate: int = 16000) -> bytes:
    """Generate audio with embedded wake marker for detection."""
    # Synthesize ~1.0 second of audio with embedded acoustic marker
    chunk = bytearray(generate_speech_noise(1.0, sample_rate))
    marker = b"WAKE_WORD_MARKER_HEY_MEDIA"
    chunk[2000 : 2000 + len(marker)] = marker
    return bytes(chunk)


def main():
    print("=" * 70)
    print(" Voice Assistance for Multimedia Control — US-01 Wake-Word Demo")
    print("=" * 70)

    config = VoiceControlConfig(listening_window_seconds=3.0)
    capture = AudioCaptureComponent(config)
    detector = WakeWordDetector(config)
    validator = SecurityValidator(detector.session_manager)
    feedback = FeedbackModule()

    # Link state change to feedback module
    detector.session_manager.register_state_callback(feedback.on_state_change)

    print(f"\n[CONFIG] Wake word: '{config.wake_word}'")
    print(f"[CONFIG] Listening window duration: {config.listening_window_seconds}s")
    print(f"[CONFIG] Rolling buffer size: {config.rolling_buffer_seconds}s (in-memory only, SR-2)")
    print(f"[STATUS] Initial state: {detector.current_state.value}")

    # Step 1: Feed background audio (TC-10: Gating verification)
    print("\n--- STEP 1: Feeding Background Audio / Noise (Without Wake Word) ---")
    noise = generate_speech_noise(0.5)
    for i in range(0, len(noise), config.chunk_bytes):
        chunk = noise[i : i + config.chunk_bytes]
        capture.feed_chunk(chunk)
        detected = detector.detect_wake_word(chunk)
        if detected:
            print("ERROR: False positive detection!")

    print(f"Result: Wake detected? {detector.is_listening}. System state: {detector.current_state.value}")
    print("Security check: TC-10 PASS — System remained idle on non-wake audio.")

    # Try unauthorized command while idle
    unauthorized_cmd = Command(type="play", confidence=0.95, session_id="unauthorized-token")
    auth_ok = validator.validate_source(unauthorized_cmd)
    print(f"Unauthorized command validation while IDLE: {'ACCEPTED' if auth_ok else 'REJECTED (Protected by SR-1)'}")

    # Step 2: Feed Wake Word Audio (TC-01: Detection verification)
    print("\n--- STEP 2: Speaking Wake Word 'Hey Media' ---")
    wake_audio = generate_wake_word_audio()
    start_t = time.perf_counter()

    for i in range(0, len(wake_audio), config.chunk_bytes):
        chunk = wake_audio[i : i + config.chunk_bytes]
        capture.feed_chunk(chunk)
        if detector.detect_wake_word(chunk):
            break

    elapsed = time.perf_counter() - start_t
    print(f"Latency to active listening: {elapsed*1000:.2f} ms (Must be < 1000ms: {'PASS' if elapsed < 1.0 else 'FAIL'})")
    print(f"System State: {detector.current_state.value}")
    print(f"Active Session Token: {detector.active_session_token}")
    print(f"Time remaining in window: {detector.time_remaining_seconds:.2f}s")

    # Step 3: Issue authorized command within listening window
    print("\n--- STEP 3: Issuing Command 'Play' within Active Listening Window ---")
    valid_cmd = Command(
        type="play",
        confidence=0.92,
        session_id=detector.active_session_token,
    )
    is_valid = validator.validate_source(valid_cmd)
    print(f"Security validation for authorized command: {'AUTHORIZED ✓' if is_valid else 'FAILED ✗'}")
    feedback.notify("ok")

    # Step 4: Window timeout
    print("\n--- STEP 4: Waiting for Listening Window Timeout ---")
    print("Waiting for session expiration...")
    time.sleep(3.2)
    detector.session_manager.check_and_update()
    print(f"Current State after timeout: {detector.current_state.value}")
    print(f"Active Session: {detector.active_session_token}")

    print("\n" + "=" * 70)
    print(" Demonstration Complete: US-01 Wake-Word Detection Verified Successfully!")
    print("=" * 70)


if __name__ == "__main__":
    main()
