"""
Voice Assistance for Multimedia Control - application entry point (Sprint 1).

This is the ONLY entry point. Flow (Architecture 2.3):

    microphone -> wake word "hey media" -> one command inside the 4 s window
    -> map_command -> SecurityValidator (shared session) -> media_controls
    -> FeedbackModule

Startup (US-18): the required components are checked and the result is printed
before the assistant starts listening.

Usage:
    python main.py                          # local Vosk recognizer (SR-2)
    python main.py --model PATH             # custom Vosk model folder
    python main.py --backend google         # cloud recognizer (SR-2 deviation)
"""

import argparse
import logging
import sys
from pathlib import Path

# Allow running from a fresh checkout without `pip install -e .`
SRC = Path(__file__).resolve().parent / "src"
if SRC.is_dir() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from voice_control.config import VoiceControlConfig  # noqa: E402
from voice_control.control.command_mapper import recognizer_phrases  # noqa: E402
from voice_control.control.media_actions import bind_media_actions  # noqa: E402
from voice_control.recognition.transcriber import create_transcriber  # noqa: E402
from voice_control.runtime import VoiceAssistant  # noqa: E402
from voice_control.startup_check import (  # noqa: E402
    MEDIA_PLAYER,
    RECOGNIZER,
    report_init_failure,
    run_startup_checks,
)


def load_media_controls():
    """Import media_controls.py without letting a broken import stop the assistant."""
    try:
        import media_controls
        return media_controls, None
    except Exception as exc:  # e.g. a desktop-only library on the Raspberry Pi
        return None, f"media_controls failed to import: {type(exc).__name__}: {exc}"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Voice-controlled media assistant")
    parser.add_argument("--backend", choices=["vosk", "google"], default="vosk",
                        help="speech recognizer (default: vosk, runs offline)")
    parser.add_argument("--model", help="path to the Vosk model folder")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = VoiceControlConfig(recognizer_backend=args.backend)
    if args.model:
        config.vosk_model_path = args.model

    # US-18: check the required components before anything starts.
    module, import_error = load_media_controls()
    report = run_startup_checks(config, module, import_error)
    report.show()
    if not report.ok:
        print(report.summary(), flush=True)
        return 2

    try:
        transcriber = create_transcriber(config, recognizer_phrases(config.wake_word))
    except Exception as exc:  # Vosk missing, or a model folder that will not load
        report_init_failure(RECOGNIZER, exc)
        return 2

    # Open the shared media player now, so the first command does not have to.
    get_player = getattr(module, "get_player", None)
    if callable(get_player):
        try:
            get_player()
        except Exception as exc:
            report_init_failure(MEDIA_PLAYER, exc)
            return 2
        print("[STARTUP] OK     Media player: Chrome window opened", flush=True)
        print("Media player opened. Start a YouTube video in that window, then speak.")

    print("[STARTUP] All required components are ready.", flush=True)
    assistant = VoiceAssistant(transcriber, bind_media_actions(module, import_error), config)
    return assistant.run()


if __name__ == "__main__":
    sys.exit(main())
