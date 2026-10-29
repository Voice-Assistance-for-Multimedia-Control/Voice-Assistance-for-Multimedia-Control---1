"""
Startup System Check (US-18).

Before the assistant starts listening, check that every required component is
available and tell the user the result:

* Microphone          - an audio input device exists (reuses the US-13 check)
* Speech recognizer   - Vosk and its model folder (or SpeechRecognition for --backend google)
* Media controls      - media_controls.py imports and has all seven media functions
* Browser automation  - Selenium is installed (Chrome is opened later by main.py)

Each check returns a plain pass/fail with a message. A check that crashes is
reported as a failure; it never stops the other checks from running.
"""

from dataclasses import dataclass, field
import importlib.util
import logging
from pathlib import Path
from types import ModuleType
from typing import Callable, List, Optional, Tuple

from voice_control.audio.capture import AudioCaptureComponent
from voice_control.config import VoiceControlConfig
from voice_control.control.media_actions import missing_functions

logger = logging.getLogger(__name__)

MIC = "Microphone"
RECOGNIZER = "Speech recognizer"
MEDIA_CONTROLS = "Media controls"
BROWSER = "Browser automation"
MEDIA_PLAYER = "Media player"


@dataclass
class ComponentCheck:
    """Result of checking one required component."""
    name: str
    ok: bool
    message: str

    def line(self) -> str:
        status = "OK    " if self.ok else "FAILED"
        return f"[STARTUP] {status} {self.name}: {self.message}"


@dataclass
class StartupReport:
    """All component checks, in the order they were run."""
    checks: List[ComponentCheck] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)

    @property
    def failed(self) -> List[ComponentCheck]:
        return [check for check in self.checks if not check.ok]

    def summary(self) -> str:
        if self.ok:
            return "[STARTUP] All required components are ready."
        names = ", ".join(check.name for check in self.failed)
        return f"[STARTUP] NOT READY: {names} failed. Fix the problem above and start again."

    def show(self) -> None:
        """Print one line per component (and log it)."""
        print("[STARTUP] Checking required components...", flush=True)
        for check in self.checks:
            line = check.line()
            (logger.info if check.ok else logger.error)(line)
            print(line, flush=True)


def _is_installed(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def check_microphone() -> Tuple[bool, str]:
    """An audio input device is present (same check the capture component uses, US-13)."""
    return AudioCaptureComponent.check_microphone_availability()


def check_recognizer(config: VoiceControlConfig) -> Tuple[bool, str]:
    """The selected speech recognizer has its library and (for Vosk) its model folder."""
    backend = config.recognizer_backend.lower()
    if backend == "vosk":
        if not _is_installed("vosk"):
            return False, "Vosk is not installed. Run: pip install vosk"
        if not Path(config.vosk_model_path).is_dir():
            return False, (
                f"Vosk model not found at '{config.vosk_model_path}'. Download "
                "vosk-model-small-en-in-0.4 from https://alphacephei.com/vosk/models "
                "and unzip it there, or pass --model PATH."
            )
        return True, f"Vosk (offline) with model '{config.vosk_model_path}'"
    if backend == "google":
        if not _is_installed("speech_recognition"):
            return False, "SpeechRecognition is not installed. Run: pip install SpeechRecognition"
        return True, "Google cloud recognizer (audio leaves the device: SR-2 deviation)"
    return False, f"Unknown recognizer backend: {config.recognizer_backend!r}"


def check_media_controls(
    module: Optional[ModuleType], import_error: Optional[str] = None
) -> Tuple[bool, str]:
    """media_controls.py imported and every agreed media function exists."""
    if module is None:
        return False, import_error or "media_controls.py could not be imported"
    missing = missing_functions(module)
    if missing:
        return False, f"missing functions: {', '.join(missing)}"
    return True, "all media control functions are available"


def check_browser_automation() -> Tuple[bool, str]:
    """Selenium is installed (it drives the YouTube player in Chrome)."""
    if not _is_installed("selenium"):
        return False, "Selenium is not installed. Run: python -m pip install selenium"
    return True, "Selenium is installed (Chrome opens when the assistant starts)"


def _run_check(name: str, func: Callable[[], Tuple[bool, str]]) -> ComponentCheck:
    """Run one check; a check that crashes counts as a failure, never as a crash."""
    try:
        ok, message = func()
    except Exception as exc:
        return ComponentCheck(name, False, f"check could not run: {type(exc).__name__}: {exc}")
    return ComponentCheck(name, bool(ok), message)


def run_startup_checks(
    config: Optional[VoiceControlConfig] = None,
    media_module: Optional[ModuleType] = None,
    media_import_error: Optional[str] = None,
    mic_check: Optional[Callable[[], Tuple[bool, str]]] = None,
) -> StartupReport:
    """Check every required component and return the report (nothing is printed)."""
    config = config or VoiceControlConfig()
    mic_check = mic_check or check_microphone
    return StartupReport(
        checks=[
            _run_check(MIC, mic_check),
            _run_check(RECOGNIZER, lambda: check_recognizer(config)),
            _run_check(MEDIA_CONTROLS, lambda: check_media_controls(media_module, media_import_error)),
            _run_check(BROWSER, check_browser_automation),
        ]
    )


def report_init_failure(name: str, error: Exception) -> None:
    """Report a component that passed its check but failed to initialize (US-18, criterion 3)."""
    lines = [
        f"[STARTUP] FAILED {name}: {error}",
        f"[STARTUP] NOT READY: {name} failed to initialize. Fix the problem above and start again.",
    ]
    for line in lines:
        logger.error(line)
        print(line, flush=True)
