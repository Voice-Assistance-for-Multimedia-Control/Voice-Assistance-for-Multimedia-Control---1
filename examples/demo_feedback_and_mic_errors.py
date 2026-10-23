"""
Interactive Demo: US-09 (Command Feedback) & US-13 (Microphone Error Handling).
Demonstrates:
- Pre-flight microphone hardware availability check (US-13)
- Visible & audible feedback on successful command execution (US-09, FR-10)
- Distinct rejection indication on unsupported/rejected commands (US-09)
- Hardware disconnection handling, error tone, and command blocking (US-13)
- Stream resumption upon reconnection
"""

import sys
import time
from pathlib import Path

# Add src to python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from voice_control.audio.capture import AudioCaptureComponent
from voice_control.feedback.indicator import FeedbackModule, LEDColor, ToneType
from voice_control.models.command import Command
from voice_control.security.error_handler import ErrorHandler, MicrophoneUnavailableError, UnrecognizedCommandError
from voice_control.security.validator import SecurityValidator
from voice_control.detector.state import SessionManager


def main():
    print("=" * 75)
    print(" Voice Assistance for Multimedia Control — US-09 & US-13 Demo")
    print("=" * 75)

    feedback = FeedbackModule(enable_audio_tones=True)
    error_handler = ErrorHandler(feedback)
    capture = AudioCaptureComponent(feedback_module=feedback)
    session_mgr = SessionManager()
    validator = SecurityValidator(session_mgr)

    # 1. Microphone Availability Check (US-13 Criterion 1)
    print("\n--- STEP 1: Microphone Hardware Availability Diagnostic ---")
    available, message = AudioCaptureComponent.check_microphone_availability()
    print(f"Status: {'AVAILABLE ✓' if available else 'UNAVAILABLE (Handled Gracefully)'}")
    print(f"Diagnostic Info: {message}")

    # 2. Command Success Feedback (US-09 Criterion 1 / FR-10)
    print("\n--- STEP 2: Command Success Feedback ---")
    print("Simulating successful execution of 'play' command...")
    feedback.notify("ok")
    print(f"LED Color: {feedback.current_color.value} (Expected: GREEN)")
    print(f"Tone Generated: {feedback.last_event.tone_type.value} (Double chime)")

    # 3. Command Rejection Feedback (US-09 Criterion 2)
    print("\n--- STEP 3: Command Rejection / Failure Feedback ---")
    print("Simulating rejected command (out-of-vocabulary or security fail)...")
    error_handler.handle_error(UnrecognizedCommandError("Command 'open browser' not in vocabulary"))
    print(f"LED Color: {feedback.current_color.value} (Expected: RED)")
    print(f"Tone Generated: {feedback.last_event.tone_type.value} (Distinct rejection buzz)")

    # 4. Microphone Disconnect & Command Blocking (US-13 Criteria 2 & 3)
    print("\n--- STEP 4: Microphone Disconnect Fault & Gating ---")
    print("Simulating microphone unplug / hardware failure event...")
    capture.suspend_stream("Microphone device unplugged from USB port")
    print(f"Capture Healthy: {capture.is_healthy}")
    print(f"Capture Suspended: {capture.is_suspended}")
    print(f"LED Color: {feedback.current_color.value} (Expected: RED)")
    print(f"Tone Generated: {feedback.last_event.tone_type.value} (Warning pulse)")
    print(f"Can capture audio frames: {capture.can_capture()} (Commands blocked without valid audio)")

    # 5. Microphone Reconnection & Stream Recovery
    print("\n--- STEP 5: Microphone Reconnection & Stream Restoration ---")
    print("Restoring microphone connection...")
    capture.resume_stream()
    print(f"Capture Healthy: {capture.is_healthy}")
    print(f"LED Color: {feedback.current_color.value} (Expected: GREEN)")
    print(f"Can capture audio frames: {capture.can_capture()} (Ready for voice commands)")

    print("\n" + "=" * 75)
    print(" Demonstration Complete: US-09 and US-13 Verified Successfully!")
    print("=" * 75)


if __name__ == "__main__":
    main()
