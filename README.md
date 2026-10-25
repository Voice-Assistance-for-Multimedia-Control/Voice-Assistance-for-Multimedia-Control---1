# Voice Assistance for Multimedia Control

**Hardware-Based Voice Control System using Raspberry Pi / ESP32**  
*Course Mini-Project — Software Engineering (UE24CS242B)*

Say **"Hey Media"**, then one command within 4 seconds: *play, pause, resume, next, previous, volume up, volume down*.

---

## Sprint Allocations & Status

Statuses describe what is verified, not just what is merged. "Unit tested" means automated tests pass with fake audio and a fake player; "Verified" means TC-01..TC-10 were run on the test laptop with results logged (see [Deviations](#deviations-from-the-submitted-documents)).

### Sprint 1 (Core Multimedia Control Pipeline)
| User Story | Assignee | Story Points | Status |
|---|---|:---:|---|
| **US-01 — Wake-Word Detection** | Abhay S (`abhayS-pixel`) | 5 | Merged (PR #36, #38); unit tested; live wake word confirmed on laptop |
| **Integration — `main.py` entry point** | Abhay S | — | Merged (PR #36, #38); unit tested end-to-end for all 7 commands |
| **US-02 — Play Media** | Aaditya Vashisht (`aadityaV-goat`) | 3 | Merged (PR #35); unit tested; laptop verification pending |
| **US-03 — Pause Media** | Aaditya Vashisht | 3 | Merged (PR #35); unit tested; laptop verification pending |
| **US-04 — Resume Media** | Aaditya Vashisht | 3 | Merged (PR #35); unit tested; laptop verification pending |
| **US-05 — Next Track** | Aarohi Jaiswal (`aarohijaiswal`) | 3 | Merged (PR #37); unit tested; laptop verification pending |
| **US-06 — Previous Track** | Aarohi Jaiswal | 3 | Merged (PR #37); unit tested; laptop verification pending |
| **US-07 — Volume Control** | Aarohi Jaiswal | 3 | Merged (PR #37); unit tested (exact 10% step); laptop verification pending |

### Sprint 2 (Robustness, Feedback & System Diagnostics)
| User Story | Assignee | Story Points | Status |
|---|---|:---:|---|
| **US-09 — Command Feedback** | Abhay S | 3 | Merged (PR #34), unit tested |
| **US-13 — Microphone Error Handling** | Abhay S | 3 | Merged (PR #34), unit tested |

No further Sprint 2 work until Sprint 1 is hardware verified.

---

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[vosk,dev]"          # add ,google to use the cloud recognizer
```

Requires Python 3.9+ and Google Chrome. On Linux (or a Raspberry Pi) the microphone also needs PortAudio: `sudo apt install libportaudio2`.

Download the offline speech model (about 36 MB) once:

```bash
mkdir -p models && cd models
wget https://alphacephei.com/vosk/models/vosk-model-small-en-in-0.4.zip
unzip vosk-model-small-en-in-0.4.zip && cd ..
```

## Run

```bash
python main.py                    # offline Vosk recognizer (default, SR-2 compliant)
python main.py --model PATH       # a different Vosk model folder
python main.py --backend google   # Google cloud recognizer (sends audio off-device)
python main.py -v                 # debug logging
```

`main.py` is the only entry point. On start it reports any agreed `media_controls.py` function that is missing or fails to import; those commands are rejected with an error tone instead of crashing the assistant.

## How a command flows

```
microphone ─► AudioCaptureComponent ─► UtteranceSegmenter ─► TranscriptWakeWordEngine
                                                                   │ "hey media" heard
                                                                   ▼
                       SessionManager.open_session()  ── token ──► (4 s window)
                                                                   │
              next utterance ─► Transcriber ─► map_command(text, confidence, token)
                                                                   │
                     CommandExecutor ─► SecurityValidator ─► media_controls ─► FeedbackModule
```

- **Wake-word gating (SR-1, SO-1).** Each utterance is transcribed and the exact phrase "hey media" must appear as whole words. Command words without the wake word do nothing.
- **One shared `SessionManager`.** `WakeWordDetector` and `SecurityValidator` use the same instance. Every `Command` carries the active session token as `session_id`; `Command.session_id` defaults to `None`, so a command built without a token is always rejected.
- **The 4-second window is enforced.** The validator re-checks the session after recognition, so a command that finishes after the window closes is not executed. One command per wake word.
- **Local processing (SR-2).** The default Vosk recognizer runs on the device with a grammar limited to the wake word and command phrases. `--backend google` is a documented SR-2 deviation.
- **Confidence.** Commands below `min_command_confidence` (default 0.5) are rejected by the validator.
- **Errors (FR-9, Architecture 3.4).** Unknown words, unclear speech, recognizer failures and media failures all give the error tone and never crash the loop.

### Media function contract (`media_controls.py`)

| Story | Function | Returns |
|---|---|---|
| US-02 | `play_media()` | `True` on success, `False` on failure |
| US-03 | `pause_media()` | same |
| US-04 | `resume_media()` | same |
| US-05 | `next_track()` | same |
| US-06 | `previous_track()` | same |
| US-07 | `adjust_volume("up" \| "down")` | same |

The binding lives in `src/voice_control/control/media_actions.py`.

---

## Deviations from the Submitted Documents

The SRS, Software Architecture & Design Specification (SAD) and Test Plan were followed, with the four deviations below. None changes the seven Sprint 1 commands or their acceptance criteria.

| ID | Submitted documents said | What we did instead | Why | Impact |
|---|---|---|---|---|
| **D-1** | Runs on embedded hardware, a Raspberry Pi / ESP32 board (SRS 1.1, 1.2; SAD 2.6), and is tested on that target hardware (Test Plan, Section 9 Test Environment) | Developed and tested on a laptop (macOS) with its built-in microphone | No Raspberry Pi or ESP32 was available to the team | No change in behaviour. The code is plain Python with no board-specific parts, so it can move to a Raspberry Pi unchanged (plus `sudo apt install libportaudio2` and Chromium). Response times (NFR-1, TC-09) are measured on the laptop, not the board |
| **D-2** | Controls a local audio/video player on the same device (SRS 1.1, 1.2), with no mandatory network dependency (SAD 2.6) | Controls YouTube in a Chrome window driven by Selenium | One shared player that behaves the same on Windows, macOS and Linux for all seven commands, through a controllable interface as SRS 2.5 allows | Video playback needs an internet connection. Speech recognition still runs on the device (D-3, SR-2). Previous track (US-06) needs a YouTube playlist |
| **D-3** | Speech processing with a library such as MediaPipe or SpeechRecognition (SRS 1.2), lightweight offline models preferred (SRS 2.4) | Vosk offline recognizer with a grammar limited to "hey media" and the seven commands; Google recognition only with `--backend google` | Keeps all audio on the device (SR-2) and gives a real confidence score for the security check | A ~36 MB model is downloaded once (see Setup). Google mode sends audio off-device and is not used for testing or the demo |
| **D-4** | US-09 (command feedback) and US-13 (microphone error handling) planned for Sprint 2 | Delivered during Sprint 1 (PR #34) | Sprint 1's command flow depends on them: feedback after every command (FR-10) and an error tone for rejected commands (FR-9) | Sprint 2 has two fewer stories; no other Sprint 2 work was started during Sprint 1 |

---

## Repository Structure

```
├── main.py                           # Single application entry point
├── media_controls.py                 # Media functions (US-02..US-07 owners)
├── src/voice_control/
│   ├── config.py                     # Wake word, 4 s window, VAD, recognizer, confidence settings
│   ├── runtime.py                    # VoiceAssistant: the integrated pipeline
│   ├── models/command.py             # Command, ExecutionResult, SystemState
│   ├── audio/
│   │   ├── buffer.py                 # In-memory rolling buffer (SR-2)
│   │   ├── capture.py                # Microphone capture + fault suspension (US-13)
│   │   └── segmenter.py              # Energy-based utterance segmentation
│   ├── recognition/transcriber.py    # Vosk (local) and Google (cloud) recognizers
│   ├── detector/
│   │   ├── engine.py                 # TranscriptWakeWordEngine (+ legacy acoustic/simulated engines)
│   │   ├── state.py                  # SessionManager (IDLE -> LISTENING)
│   │   └── wake_word.py              # WakeWordDetector.detect_wake_word()
│   ├── control/
│   │   ├── command_mapper.py         # map_command(text) -> Command | None
│   │   ├── executor.py               # CommandExecutor: validate -> act -> feedback
│   │   └── media_actions.py          # Command type -> media_controls function
│   ├── security/                     # SecurityValidator, ErrorHandler
│   └── feedback/indicator.py         # FeedbackModule (US-09)
├── tests/
└── examples/
```

---

## Traceability to Requirements & Test Cases

| Req / Test case | Implementation | Automated test | Status |
|---|---|---|---|
| FR-1 / TC-01 | `WakeWordDetector`, `TranscriptWakeWordEngine` | `test_tc01_wake_word.py` | Unit tested |
| FR-2..FR-8 / TC-02..TC-08 | `map_command`, `CommandExecutor`, `media_controls` | `test_sprint1_integration.py`, `test_player_controls.py`, `test_media_controls.py` | Unit tested; laptop verification pending |
| FR-9 | `map_command`, `ErrorHandler` | `test_sprint1_integration.py` | Unit tested |
| FR-10 | `FeedbackModule` | `test_us09_feedback.py`, `test_sprint1_integration.py` | Unit tested |
| NFR-1 / TC-09 | Whole pipeline | — | Needs hardware measurement |
| SR-1 / TC-10 | `TranscriptWakeWordEngine`, `SecurityValidator` | `test_tc10_security_gating.py`, `test_sprint1_integration.py` | Unit tested |
| SR-2 | `VoskTranscriber`, `AudioBuffer` | `test_audio_buffer.py`, `test_transcriber.py` | Unit tested; speech stays on the device (D-3) |
| US-13 | `AudioCaptureComponent` | `test_us13_mic_error_handling.py` | Unit tested |

---

## Automated Verification

```bash
python -m pytest tests/ -v
```

122 tests, run automatically by GitHub Actions on every push and pull request (`.github/workflows/tests.yml`, Python 3.9 and 3.12). They use synthetic audio and fake recognizers/players, so they verify the logic of the pipeline, not microphone accuracy or real playback; those are checked on the test laptop with the Test Plan (TC-01..TC-10).
