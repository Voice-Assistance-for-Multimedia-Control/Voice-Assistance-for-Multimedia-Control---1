"""
Speech-to-text backends (ASR / Speech-to-Text Engine, Architecture 2.2).

Implements Architecture 3.3 ``recognize_speech(audio_stream) -> text`` behind one
interface so the rest of the system does not care which recognizer is used:

* ``VoskTranscriber``  - offline, runs on Raspberry Pi, audio never leaves the
  device (SR-2). Uses a grammar restricted to the wake phrase and the command
  vocabulary, and returns real per-word confidence.
* ``GoogleTranscriber`` - the free Google Web Speech API via SpeechRecognition.
  Sends the utterance over the network, so it is a documented SR-2 deviation and
  must be chosen explicitly.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import Iterable, List, Optional

from voice_control.config import VoiceControlConfig

logger = logging.getLogger(__name__)


class TranscriberUnavailableError(RuntimeError):
    """The selected speech recognizer cannot be started (missing library or model)."""


@dataclass
class Transcript:
    text: str
    confidence: float


class BaseTranscriber(ABC):
    """Turns one complete utterance (16-bit mono PCM) into text."""

    #: True when audio is processed on the device only (SR-2).
    is_local: bool = True

    @abstractmethod
    def transcribe(self, pcm: bytes) -> Optional[Transcript]:
        """Return the transcript, or None if nothing intelligible was heard."""

    def recognize_speech(self, audio_stream: bytes) -> str:
        """Architecture 3.3 API name: returns plain text ('' when nothing heard)."""
        result = self.transcribe(audio_stream)
        return result.text if result else ""


class VoskTranscriber(BaseTranscriber):
    """Offline recognizer using a Vosk/Kaldi model and a closed grammar."""

    is_local = True

    def __init__(self, model_path: str, sample_rate: int, phrases: Iterable[str]):
        try:
            from vosk import KaldiRecognizer, Model, SetLogLevel
        except ImportError as exc:
            raise TranscriberUnavailableError(
                "Vosk is not installed. Run: pip install vosk"
            ) from exc

        if not Path(model_path).is_dir():
            raise TranscriberUnavailableError(
                f"Vosk model not found at '{model_path}'. Download "
                "vosk-model-small-en-in-0.4 from https://alphacephei.com/vosk/models "
                "and unzip it there, or pass --model PATH."
            )

        SetLogLevel(-1)
        self._recognizer_cls = KaldiRecognizer
        self._model = Model(model_path)
        self._sample_rate = sample_rate
        # "[unk]" lets Vosk say "none of these" instead of forcing a match.
        self._grammar = json.dumps(sorted(set(p.lower() for p in phrases)) + ["[unk]"])

    def transcribe(self, pcm: bytes) -> Optional[Transcript]:
        rec = self._recognizer_cls(self._model, self._sample_rate, self._grammar)
        rec.SetWords(True)
        rec.AcceptWaveform(pcm)
        result = json.loads(rec.FinalResult())

        words: List[dict] = [w for w in result.get("result", []) if w.get("word") != "[unk]"]
        text = " ".join(w["word"] for w in words).strip()
        if not text:
            return None
        confidence = sum(float(w.get("conf", 0.0)) for w in words) / len(words)
        return Transcript(text=text, confidence=confidence)


class GoogleTranscriber(BaseTranscriber):
    """Cloud recognizer (Google Web Speech API). Not SR-2 compliant."""

    is_local = False

    def __init__(self, sample_rate: int, sample_width: int, language: str = "en-IN"):
        try:
            import speech_recognition as sr
        except ImportError as exc:
            raise TranscriberUnavailableError(
                "SpeechRecognition is not installed. Run: pip install SpeechRecognition"
            ) from exc
        self._sr = sr
        self._recognizer = sr.Recognizer()
        self._recognizer.operation_timeout = 3
        self._sample_rate = sample_rate
        self._sample_width = sample_width
        self._language = language
        logger.warning(
            "Using Google cloud speech recognition: utterances are sent off-device "
            "(SR-2 deviation)."
        )

    def transcribe(self, pcm: bytes) -> Optional[Transcript]:
        audio = self._sr.AudioData(pcm, self._sample_rate, self._sample_width)
        try:
            response = self._recognizer.recognize_google(
                audio, language=self._language, show_all=True
            )
        except self._sr.RequestError as exc:
            raise ConnectionError(f"Google speech service unavailable: {exc}") from exc

        if not response or not response.get("alternative"):
            return None
        best = response["alternative"][0]
        text = best.get("transcript", "").strip().lower()
        if not text:
            return None
        # Google returns confidence for the top alternative of a final result.
        # When it is absent we cannot vouch for the result, so report 0.5 (borderline).
        confidence = float(best.get("confidence", 0.5))
        return Transcript(text=text, confidence=confidence)


def create_transcriber(config: VoiceControlConfig, phrases: Iterable[str]) -> BaseTranscriber:
    """Build the recognizer selected in config.recognizer_backend."""
    backend = config.recognizer_backend.lower()
    if backend == "vosk":
        return VoskTranscriber(config.vosk_model_path, config.sample_rate, phrases)
    if backend == "google":
        return GoogleTranscriber(config.sample_rate, config.sample_width, config.google_language)
    raise ValueError(f"Unknown recognizer backend: {config.recognizer_backend!r}")
