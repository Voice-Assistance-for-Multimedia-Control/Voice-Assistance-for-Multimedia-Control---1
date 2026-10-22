import speech_recognition as sr
from media_controls import next_track


def main():
    recognizer = sr.Recognizer()
    microphone = sr.Microphone()

    print("Voice Assistant started. Say 'next track' or 'next song'.")

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
            elif command in ("exit", "quit", "stop assistant"):
                print("Voice Assistant stopped.")
                break
            else:
                print("Command not supported in this version.")

        except sr.WaitTimeoutError:
            print("No speech detected. Try again.")
        except sr.UnknownValueError:
            print("Sorry, I could not understand.")
        except sr.RequestError as error:
            print(f"Speech recognition error: {error}")


if __name__ == "__main__":
    main()
