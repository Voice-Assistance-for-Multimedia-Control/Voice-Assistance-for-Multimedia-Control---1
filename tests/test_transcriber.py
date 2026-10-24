"""Unit tests for the speech-recognizer backends, using a fake vosk module."""

import json
import sys
import types

import pytest

from voice_control.config import VoiceControlConfig
from voice_control.recognition.transcriber import (
    TranscriberUnavailableError,
    VoskTranscriber,
    create_transcriber,
)


def install_fake_vosk(monkeypatch, final_result):
    seen = {}

    class Model:
        def __init__(self, path):
            seen["model"] = path

    class KaldiRecognizer:
        def __init__(self, model, rate, grammar):
            seen["rate"] = rate
            seen["grammar"] = json.loads(grammar)

        def SetWords(self, flag):
            seen["words"] = flag

        def AcceptWaveform(self, data):
            seen["bytes"] = len(data)

        def FinalResult(self):
            return json.dumps(final_result)

    fake = types.SimpleNamespace(Model=Model, KaldiRecognizer=KaldiRecognizer, SetLogLevel=lambda n: None)
    monkeypatch.setitem(sys.modules, "vosk", fake)
    return seen


def test_vosk_returns_text_and_average_word_confidence(monkeypatch, tmp_path):
    seen = install_fake_vosk(monkeypatch, {
        "text": "volume up",
        "result": [{"word": "volume", "conf": 0.9}, {"word": "up", "conf": 0.7}],
    })
    t = VoskTranscriber(str(tmp_path), 16000, ["hey media", "volume up"])
    result = t.transcribe(b"\x00\x00" * 100)
    assert result.text == "volume up"
    assert result.confidence == pytest.approx(0.8)
    assert seen["grammar"] == ["hey media", "volume up", "[unk]"]
    assert seen["words"] is True
    assert t.is_local


def test_vosk_unknown_speech_returns_none(monkeypatch, tmp_path):
    install_fake_vosk(monkeypatch, {"text": "[unk]", "result": [{"word": "[unk]", "conf": 1.0}]})
    t = VoskTranscriber(str(tmp_path), 16000, ["play"])
    assert t.transcribe(b"\x00\x00" * 100) is None
    assert t.recognize_speech(b"\x00\x00" * 100) == ""


def test_vosk_missing_model_folder_is_a_clear_error(monkeypatch, tmp_path):
    install_fake_vosk(monkeypatch, {})
    with pytest.raises(TranscriberUnavailableError, match="model not found"):
        VoskTranscriber(str(tmp_path / "nope"), 16000, ["play"])


def test_unknown_backend_is_rejected():
    with pytest.raises(ValueError):
        create_transcriber(VoiceControlConfig(recognizer_backend="siri"), ["play"])
