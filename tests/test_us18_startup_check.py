"""
Tests for User Story US-18: Startup System Check.

Acceptance Criteria:
- The system checks the availability of the microphone and required software components.
- The system indicates successful initialization.
- An error is reported if a required component fails to initialize.

No real microphone, Vosk model or Chrome is used: the microphone check, the
installed-package check and the media module are all replaced with fakes.
"""

from types import SimpleNamespace

import pytest

import main as app
from voice_control import startup_check
from voice_control.config import VoiceControlConfig
from voice_control.startup_check import (
    BROWSER,
    MEDIA_CONTROLS,
    MIC,
    RECOGNIZER,
    ComponentCheck,
    StartupReport,
    run_startup_checks,
)

MIC_OK = lambda: (True, "Default microphone available: Test Mic")  # noqa: E731
MIC_MISSING = lambda: (False, "No microphone or audio input device detected on the system.")  # noqa: E731


@pytest.fixture
def media_module():
    """A media_controls stand-in with every agreed function."""
    names = ["play_media", "pause_media", "resume_media", "next_track",
             "previous_track", "adjust_volume"]
    return SimpleNamespace(**{name: (lambda *a, **k: True) for name in names})


@pytest.fixture
def installed(monkeypatch):
    """Pretend these packages are installed (default: vosk and selenium)."""
    packages = {"vosk", "selenium"}
    monkeypatch.setattr(startup_check, "_is_installed", lambda name: name in packages)
    return packages


@pytest.fixture
def config(tmp_path):
    """Config whose Vosk model folder exists."""
    return VoiceControlConfig(vosk_model_path=str(tmp_path))


def run(config, media_module, mic_check=MIC_OK, import_error=None):
    return run_startup_checks(config, media_module, import_error, mic_check=mic_check)


# ------------------------------------------- criterion 1: components are checked
def test_every_required_component_is_checked(config, media_module, installed):
    report = run(config, media_module)
    assert [c.name for c in report.checks] == [MIC, RECOGNIZER, MEDIA_CONTROLS, BROWSER]


def test_microphone_result_comes_from_the_microphone_check(config, media_module, installed):
    report = run(config, media_module)
    assert "Test Mic" in report.checks[0].message


# ------------------------------------------ criterion 2: success is indicated
def test_all_components_ok_means_ready(config, media_module, installed):
    report = run(config, media_module)
    assert report.ok
    assert report.failed == []
    assert report.summary() == "[STARTUP] All required components are ready."


def test_success_is_printed_for_each_component(config, media_module, installed, capsys):
    run(config, media_module).show()
    out = capsys.readouterr().out
    assert "Checking required components" in out
    assert out.count("[STARTUP] OK") == 4
    assert "FAILED" not in out


# ------------------------------------------ criterion 3: failures are reported
def test_missing_microphone_is_reported(config, media_module, installed):
    report = run(config, media_module, mic_check=MIC_MISSING)
    assert not report.ok
    assert [c.name for c in report.failed] == [MIC]
    assert "No microphone" in report.failed[0].message
    assert "NOT READY" in report.summary()
    assert MIC in report.summary()


def test_missing_vosk_model_is_reported(media_module, installed, tmp_path):
    config = VoiceControlConfig(vosk_model_path=str(tmp_path / "no-such-model"))
    report = run(config, media_module)
    assert [c.name for c in report.failed] == [RECOGNIZER]
    assert "Vosk model not found" in report.failed[0].message


def test_missing_vosk_package_is_reported(config, media_module, installed):
    installed.discard("vosk")
    report = run(config, media_module)
    assert [c.name for c in report.failed] == [RECOGNIZER]
    assert "pip install vosk" in report.failed[0].message


def test_google_backend_needs_speech_recognition(tmp_path, media_module, installed):
    config = VoiceControlConfig(recognizer_backend="google")
    report = run(config, media_module)
    assert [c.name for c in report.failed] == [RECOGNIZER]
    installed.add("speech_recognition")
    assert run(config, media_module).ok


def test_unknown_backend_is_reported(media_module, installed):
    report = run(VoiceControlConfig(recognizer_backend="bogus"), media_module)
    assert [c.name for c in report.failed] == [RECOGNIZER]
    assert "Unknown recognizer backend" in report.failed[0].message


def test_missing_media_function_is_reported(config, media_module, installed):
    del media_module.next_track
    report = run(config, media_module)
    assert [c.name for c in report.failed] == [MEDIA_CONTROLS]
    assert "next_track" in report.failed[0].message


def test_media_controls_import_failure_is_reported(config, installed):
    error = "media_controls failed to import: ImportError: boom"
    report = run(config, None, import_error=error)
    assert [c.name for c in report.failed] == [MEDIA_CONTROLS]
    assert "boom" in report.failed[0].message


def test_missing_selenium_is_reported(config, media_module, installed):
    installed.discard("selenium")
    report = run(config, media_module)
    assert [c.name for c in report.failed] == [BROWSER]
    assert "Selenium" in report.failed[0].message


def test_every_failure_is_listed_not_just_the_first(tmp_path, installed):
    config = VoiceControlConfig(vosk_model_path=str(tmp_path / "missing"))
    installed.clear()
    report = run(config, None, mic_check=MIC_MISSING, import_error="no media")
    assert [c.name for c in report.failed] == [MIC, RECOGNIZER, MEDIA_CONTROLS, BROWSER]


def test_a_check_that_crashes_is_reported_as_failed(config, media_module, installed):
    def broken():
        raise RuntimeError("audio driver exploded")

    report = run(config, media_module, mic_check=broken)
    assert [c.name for c in report.failed] == [MIC]
    assert "audio driver exploded" in report.failed[0].message
    assert len(report.checks) == 4  # the other checks still ran


def test_failure_is_printed(config, media_module, installed, capsys):
    run(config, media_module, mic_check=MIC_MISSING).show()
    out = capsys.readouterr().out
    assert "[STARTUP] FAILED Microphone" in out
    assert out.count("[STARTUP] OK") == 3


def test_failure_line_names_the_component():
    check = ComponentCheck("Media player", False, "Chrome not found")
    assert check.line() == "[STARTUP] FAILED Media player: Chrome not found"
    assert StartupReport([check]).ok is False


# ------------------------------------------------ main.py wiring (no real hardware)
def failed_report():
    return StartupReport([ComponentCheck(MIC, False, "No microphone detected")])


def ok_report():
    return StartupReport([ComponentCheck(MIC, True, "fine")])


def test_main_stops_before_listening_when_a_check_fails(monkeypatch, capsys):
    monkeypatch.setattr(app, "load_media_controls", lambda: (SimpleNamespace(), None))
    monkeypatch.setattr(app, "run_startup_checks", lambda *a, **k: failed_report())

    def must_not_run(*a, **k):
        raise AssertionError("assistant started although a required component failed")

    monkeypatch.setattr(app, "create_transcriber", must_not_run)
    monkeypatch.setattr(app, "VoiceAssistant", must_not_run)

    assert app.main([]) == 2
    out = capsys.readouterr().out
    assert "[STARTUP] FAILED Microphone" in out
    assert "NOT READY" in out
    assert "All required components are ready" not in out


def test_main_reports_a_recognizer_that_fails_to_initialize(monkeypatch, capsys):
    monkeypatch.setattr(app, "load_media_controls", lambda: (SimpleNamespace(), None))
    monkeypatch.setattr(app, "run_startup_checks", lambda *a, **k: ok_report())

    def broken(*a, **k):
        raise RuntimeError("model files are corrupt")

    monkeypatch.setattr(app, "create_transcriber", broken)

    assert app.main([]) == 2
    out = capsys.readouterr().out
    assert "[STARTUP] FAILED Speech recognizer: model files are corrupt" in out
    assert "NOT READY" in out
    assert "All required components are ready" not in out


def test_main_reports_a_media_player_that_fails_to_open(monkeypatch, capsys):
    def no_chrome():
        raise RuntimeError("Chrome is not installed")

    monkeypatch.setattr(app, "load_media_controls",
                        lambda: (SimpleNamespace(get_player=no_chrome), None))
    monkeypatch.setattr(app, "run_startup_checks", lambda *a, **k: ok_report())
    monkeypatch.setattr(app, "create_transcriber", lambda *a, **k: object())
    monkeypatch.setattr(app, "VoiceAssistant", lambda *a, **k: pytest.fail("assistant started"))

    assert app.main([]) == 2
    out = capsys.readouterr().out
    assert "[STARTUP] FAILED Media player: Chrome is not installed" in out
    assert "All required components are ready" not in out


def test_main_says_ready_only_after_everything_initialized(monkeypatch, capsys):
    events = []
    monkeypatch.setattr(app, "load_media_controls",
                        lambda: (SimpleNamespace(get_player=lambda: events.append("player")), None))
    monkeypatch.setattr(app, "run_startup_checks", lambda *a, **k: ok_report())
    monkeypatch.setattr(app, "create_transcriber",
                        lambda *a, **k: events.append("recognizer") or object())
    monkeypatch.setattr(app, "bind_media_actions", lambda *a, **k: {})

    def fake_assistant(*a, **k):
        events.append("assistant created")
        return SimpleNamespace(run=lambda: 0)

    monkeypatch.setattr(app, "VoiceAssistant", fake_assistant)

    assert app.main([]) == 0
    out = capsys.readouterr().out
    assert events == ["recognizer", "player", "assistant created"]
    assert "[STARTUP] All required components are ready." in out
