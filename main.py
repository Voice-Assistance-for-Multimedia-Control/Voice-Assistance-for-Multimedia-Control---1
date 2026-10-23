
import speech_recognition as sr
from media_controls import next_track, previous_track, adjust_volume


def main():
    recognizer = sr.Recognizer()
    microphone = sr.Microphone()

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

            if "next track" in command or "next song" in command:
                next_track()
            elif "previous track" in command or "previous song" in command:
                previous_track()
            elif "volume up" in command or "increase volume" in command:
                adjust_volume("up")
            elif "volume down" in command or "decrease volume" in command:
                adjust_volume("down")
            elif command in ("exit", "quit", "stop assistant"):
                print("Voice Assistant stopped.")
                break
            else:
                print("Command not supported in this version.")

        except sr.WaitTimeoutError:
            print("No speech detected. Please try again.")
        except sr.UnknownValueError:
            print("Sorry, I could not understand that command.")
        except sr.RequestError as error:
            print(f"Speech recognition service error: {error}")
        except Exception as error:
            print(f"An error occurred: {error}")


if __name__ == "__main__":
    main()
