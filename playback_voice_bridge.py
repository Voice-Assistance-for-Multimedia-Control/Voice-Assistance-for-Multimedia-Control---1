"""Wake-word-gated voice control for YouTube Play, Pause and Resume."""

import logging
import threading


import speech_recognition as sr

from voice_control.config import VoiceControlConfig
from voice_control.audio.capture import AudioCaptureComponent
from voice_control.detector.wake_word import WakeWordDetector
from voice_control.models.command import Command
from voice_control.security.validator import SecurityValidator
from voice_control.feedback.indicator import FeedbackModule
from voice_control.youtube_player import YouTubePlayer
from voice_control.playback_command_service import PlaybackCommandService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
LOG = logging.getLogger(__name__)

ACTIONS = {"play", "pause", "resume"}


def normalize_command(text):
    """Accept only a clear playback command or an exit request."""
    words = (
        text.lower()
        .replace(".", " ")
        .replace(",", " ")
        .replace("!", " ")
        .replace("?", " ")
        .split()
    )

    if words in (["exit"], ["quit"], ["stop", "assistant"]):
        return "exit"

    ignored = {"please", "the", "video", "youtube", "media", "music"}
    words = [word for word in words if word not in ignored]

    if len(words) == 1 and words[0] in ACTIONS:
        return words[0]

    return None


def main():
    config = VoiceControlConfig()
    capture = AudioCaptureComponent(config)
    detector = WakeWordDetector(config)
    sessions = detector.session_manager
    validator = SecurityValidator(sessions)
    feedback = FeedbackModule()
    sessions.register_state_callback(feedback.on_state_change)

    player = YouTubePlayer()
    service = PlaybackCommandService(validator, player, feedback)

    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = False
    recognizer.pause_threshold = 0.6
    recognizer.operation_timeout = 8

    wake_event = threading.Event()
    wake_info = {}
    wake_lock = threading.Lock()

    def on_wake(session_token, confidence):
        with wake_lock:
            wake_info["token"] = session_token
            wake_info["confidence"] = confidence
            wake_event.set()

    def on_audio_chunk(chunk):
        # The existing detector processes the continuous microphone stream.
        detector.detect_wake_word(chunk)

    detector.register_wake_callback(on_wake)
    capture.register_callback(on_audio_chunk)

    print("\nWAKE-WORD VOICE CONTROL")
    print(f"Configured wake word: {config.wake_word}")
    print("Say the wake word first, then say Play, Pause or Resume.")
    print("The command is only accepted inside the active listening session.")
    print("Say 'Exit' after the wake word to close the program.")
    print("Chrome opens in a dedicated controlled window.\n")

    try:
        player.open()
        print("Open a YouTube video in the new Chrome window.")

        # Calibrate the command recognizer before starting the streaming mic.
        with sr.Microphone() as source:
            print("Calibrating microphone; stay quiet briefly...")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            recognizer.energy_threshold = min(max(recognizer.energy_threshold, 300), 1000)

        print("Wake-word detector is listening for live microphone audio.")
        capture.start_stream()

        while True:
            wake_event.wait(timeout=0.2)
            sessions.check_and_update()

            if not wake_event.is_set():
                continue

            wake_event.clear()

            with wake_lock:
                token = wake_info.get("token")
                confidence = wake_info.get("confidence", 0.0)

            # Stop the streaming capture before SpeechRecognition uses the mic.
            capture.stop_stream()

            try:
                if not sessions.is_session_valid(token):
                    print("Wake session expired. Waiting for the wake word again.")
                    continue

                print(
                    f"Wake word detected (confidence {confidence:.2f}). "
                    "Say Play, Pause or Resume now."
                )

                try:
                    with sr.Microphone() as source:
                        audio = recognizer.listen(
                            source, timeout=5, phrase_time_limit=3
                        )


                    transcript = recognizer.recognize_google(
                        audio, language="en-IN"
                    ).lower().strip()
                    print(f"Heard command: {transcript}")

                    action = normalize_command(transcript)

                    if action == "exit":
                        break

                    if action is None:
                        print("Unsupported command. Use Play, Pause or Resume.")
                        continue

                    command = Command(
                        type=action,
                        confidence=0.90,
                        session_id=token,
                    )
                    print(f"Executing action: {action}")
                    result = service.execute(command)
                    print(f"Command execution result: {result}")

                except sr.WaitTimeoutError:
                    print("No command heard. Waiting for the wake word again.")
                except sr.UnknownValueError:
                    print("Command wasn't clear. Waiting for the wake word again.")
                except sr.RequestError as exc:
                    print(f"Speech recognition service error: {exc}")
                except (TimeoutError, OSError) as exc:
                    print(f"Speech service timed out or failed: {exc}. Waiting for the wake word again.")

            finally:
                sessions.close_session()
                detector.reset()

                with wake_lock:
                    wake_info.clear()

                wake_event.clear()

                # Restart continuous wake-word listening for the next command.
                capture.start_stream()
                print("Waiting for the wake word again.")

    except KeyboardInterrupt:
        print("\nStopping voice control...")
    except Exception:
        LOG.exception("Voice control encountered an error")
    finally:
        capture.stop_stream()
        sessions.close_session()
        try:
            player.close()
        except Exception:
            LOG.exception("Could not close the browser cleanly")
        print("Voice control stopped.")


if __name__ == "__main__":
    main()
