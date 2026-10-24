import sys
import speech_recognition as sr
from media_controls import next_track, previous_track, adjust_volume
from voice_control.audio.capture import AudioCaptureComponent
from voice_control.feedback.indicator import FeedbackModule

feedback = FeedbackModule()


def main():
    # US-13: Validate microphone availability before starting
    is_available, mic_status = AudioCaptureComponent.check_microphone_availability()
    print(f"[SYSTEM] Microphone Check: {mic_status}")

    try:
        microphone = sr.Microphone()
    except Exception as e:
        print(f"[ERROR] Failed to initialize microphone: {e}")
        feedback.notify("mic_error")
        return

    recognizer = sr.Recognizer()

    print(
        "Voice Assistant started. Say 'next track', 'previous track', "
        "'volume up', or 'volume down'."
    )

    while True:
        try:
            with microphone as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                print("Listening...")
                audio = recognizer.listen(source, timeout=5)

            command = recognizer.recognize_google(
                audio, language="en-IN"
            ).lower()
            print(f"You said: {command}")

            # Execute commands and provide visible/audible feedback (US-09, FR-10)
            if "next track" in command or "next song" in command:
                if next_track():
                    feedback.notify("ok")
                else:
                    feedback.notify("error")
            elif "previous track" in command or "previous song" in command:
                if previous_track():
                    feedback.notify("ok")
                else:
                    feedback.notify("error")
            elif "volume up" in command or "increase volume" in command:
                if adjust_volume("up"):
                    feedback.notify("ok")
                else:
                    feedback.notify("error")
            elif "volume down" in command or "decrease volume" in command:
                if adjust_volume("down"):
                    feedback.notify("ok")
                else:
                    feedback.notify("error")
            elif command in ("exit", "quit", "stop assistant"):
                print("Voice Assistant stopped.")
                feedback.notify("ok")
                break
            else:
                print("Command not supported in this version.")
                feedback.notify("error")

        except sr.WaitTimeoutError:
            print("No speech detected. Please try again.")
        except sr.UnknownValueError:
            print("Sorry, I could not understand that command.")
            feedback.notify("error")
        except sr.RequestError as error:
            print(f"Speech recognition service error: {error}")
            feedback.notify("mic_error")
        except Exception as error:
            print(f"An error occurred: {error}")
            feedback.notify("error")


if __name__ == "__main__":
    main()
