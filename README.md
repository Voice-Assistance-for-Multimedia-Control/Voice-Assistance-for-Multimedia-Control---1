# Voice Assistance for Multimedia Control

**Hardware-Based Voice Control System using Raspberry Pi / ESP32**  
*Course Mini-Project — Software Engineering (UE24CS242B)*

---

## Team & User Story Allocations (Sprint 1)

| Member | Role / GitHub | Assigned User Stories | Story Points | Status |
|---|---|---|:---:|:---:|
| **Abhay S** | Project Lead (`abhayS-pixel`) | **US-01 — Wake-Word Detection**<br>**US-09 — Command Feedback**<br>**US-13 — Microphone Error Handling** | 5 + 3 + 3 = 11 | **Completed** |
| **Aarohi Jaiswal** | Developer (`aarohijaiswal`) | **US-05** (Next), **US-06** (Previous), **US-07** (Volume Control) | 3 + 3 + 3 = 9 | **Completed (Merged)** |
| **Aaditya Vashisht** | Developer (`aadityaV-goat`) | **US-02** (Play), **US-03** (Pause), **US-04** (Resume) | 3 + 3 + 3 = 9 | In Progress |

---

## Architecture & Deliverables Overview

The codebase implements the layered architecture specified in the [Software Architecture Specification](architecture.miniproj.pdf) and [SRS](1_Software_Requirements_Specification.pdf):

- **Wake-Word Gating (US-01 / SR-1, SO-1)**: Audio input is monitored in an `IDLE` state. The system never executes downstream media commands unless the exact wake word (default: `"hey media"`) is detected.
- **Sub-Second Activation (US-01 / FR-1, TC-01)**: On wake-word detection, the system activates a short, authorized listening session window (default: 4.0s) within `< 1.0 second` (measured latency ~0.3ms).
- **In-Memory Privacy Buffer (US-01 / SR-2)**: The audio stream is buffered exclusively in volatile RAM (`AudioBuffer`) with automatic eviction of stale audio. Raw audio is never persisted to disk.
- **Command Feedback & Distinct Indications (US-09 / FR-10)**: `FeedbackModule` provides visible acknowledgements (`LEDColor.GREEN`) and audible chimes upon every successful command, plus distinct indications (`LEDColor.RED` and buzzing tone) upon command rejection or failure.
- **Microphone Error Handling & Gating (US-13 / Architecture 3.4)**: `AudioCaptureComponent.check_microphone_availability()` validates device access; on hardware disconnection or stream fault, listening is suspended, warning feedback is emitted (`FeedbackModule.notify("mic_error")`), and command execution without valid audio is strictly blocked until restored.
- **Central Error Handling (Architecture 3.3)**: `ErrorHandler.handle_error(error)` logs and categorizes all faults without crashing.

---

## Repository Structure

```
Voice-Assistance-for-Multimedia-Control---1/
├── src/
│   └── voice_control/
│       ├── __init__.py
│       ├── config.py                 # System parameters, audio rates, thresholds
│       ├── models/
│       │   ├── __init__.py
│       │   └── command.py            # Command, ExecutionResult, SystemState data models
│       ├── audio/
│       │   ├── __init__.py
│       │   ├── buffer.py             # Circular rolling in-memory buffer (SR-2)
│       │   └── capture.py            # Audio capture driver with mic diagnostics & fault suspension (US-13)
│       ├── detector/
│       │   ├── __init__.py
│       │   ├── engine.py             # AcousticPatternEngine, SimulatedEngine
│       │   ├── state.py              # SessionManager state machine (IDLE -> LISTENING)
│       │   └── wake_word.py          # WakeWordDetector: detect_wake_word(audio_chunk) (FR-1)
│       ├── security/
│       │   ├── __init__.py
│       │   ├── error_handler.py      # Central ErrorHandler funnels faults & triggers feedback (Architecture 3.4)
│       │   └── validator.py          # SecurityValidator: validate_source(command) (SR-1)
│       └── feedback/
│           ├── __init__.py
│           └── indicator.py          # FeedbackModule: notify(status), tone synthesis, LED states (FR-10, US-09)
├── tests/
│   ├── conftest.py                   # Pytest fixtures and synthetic audio generation
│   ├── test_tc01_wake_word.py        # IEEE TC-01: Wake-word detection latency (<1s) & state transition
│   ├── test_tc10_security_gating.py  # IEEE TC-10: Gating verification & non-wake rejection
│   ├── test_audio_buffer.py          # Buffer eviction, capacity limits, thread-safety (SR-2)
│   ├── test_security_validator.py    # Session authorization, token expiration, confidence safety
│   ├── test_us09_feedback.py         # US-09: Visible & audible feedback for success/rejection (FR-10)
│   └── test_us13_mic_error_handling.py # US-13: Mic initialization, fault indication, command gating
├── examples/
│   ├── demo_wake_word.py             # Interactive demonstration of wake word lifecycle (US-01)
│   └── demo_feedback_and_mic_errors.py # Interactive demo of feedback and mic error handling (US-09, US-13)
├── main.py                           # Voice assistant runtime
├── media_controls.py                 # Media player controls (next, previous, volume)
├── pyproject.toml                    # Package metadata and test configurations
└── README.md                         # Project documentation and integration guide
```

---

## Traceability to Requirements & Test Cases

| Req / Story ID | Description | Implementation Module | Test File | Status |
|---|---|---|---|:---:|
| **US-01 (FR-1)** | Wake / Listen within 1s | `WakeWordDetector.detect_wake_word()` | `test_tc01_wake_word.py` | **PASSED** |
| **US-01 (SR-1)** | Wake-Word Gating | `SessionManager`, `SecurityValidator` | `test_tc10_security_gating.py` | **PASSED** |
| **US-01 (SR-2)** | Local-Only Audio Processing | `AudioBuffer` (in-memory rolling deque) | `test_audio_buffer.py` | **PASSED** |
| **US-09 (FR-10)**| Visible & Audible Command Feedback | `FeedbackModule.notify()`, `synthesize_tone()` | `test_us09_feedback.py` | **PASSED** |
| **US-13 (NFR-3)**| Microphone Diagnostics & Fault Gating | `AudioCaptureComponent`, `ErrorHandler` | `test_us13_mic_error_handling.py` | **PASSED** |
| **US-05 (FR-5)** | Next Track Command | `media_controls.next_track()` | Integrated via PR #30 | **PASSED** |
| **US-06 (FR-6)** | Previous Track Command | `media_controls.previous_track()` | Integrated via PR #31 | **PASSED** |
| **US-07 (FR-7/8)**| Volume Control Command | `media_controls.adjust_volume()` | Integrated via PR #33 | **PASSED** |

---

## Automated Verification

Run the complete 33-test automated test suite:
```bash
python3 -m pytest tests/ -v
```
All 33 unit and IEEE test cases pass with 100% success rate.
