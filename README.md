# Voice Assistance for Multimedia Control

**Hardware-Based Voice Control System using Raspberry Pi / ESP32**  
*Course Mini-Project — Software Engineering (UE24CS242B)*

---

## Team & User Story Allocations (Sprint 1)

| Member | Role / GitHub | Assigned User Stories | Story Points | Status |
|---|---|---|:---:|:---:|
| **Abhay S** | Project Lead (`abhayS-pixel`) | **US-01 — Wake-Word Detection** | 5 | **Completed** |
| **Aaditya Vashisht** | Developer (`aadityaV-goat`) | **US-02** (Play), **US-03** (Pause), **US-04** (Resume) | 3 + 3 + 3 = 9 | In Progress |
| **Aarohi Jaiswal** | Developer (`aarohijaiswal`) | **US-05** (Next), **US-06** (Previous), **US-07** (Volume Control) | 3 + 3 + 3 = 9 | In Progress |

---

## US-01: Wake-Word Detection Implementation Overview

US-01 establishes the foundational **Hardware Layer** and **Recognition Layer** defined in the [Software Architecture Specification](architecture.miniproj.pdf) and [SRS](1_Software_Requirements_Specification.pdf):

- **Wake-Word Gating (SR-1, SO-1)**: Audio input is continuously analyzed in an `IDLE` state. The system never executes downstream media commands unless the exact wake word (default: `"hey media"`) is detected.
- **Sub-Second Activation (FR-1, TC-01)**: On wake-word detection, the system activates a short, authorized listening session window (default: 4.0s) within `< 1.0 second` (measured latency ~0.3ms).
- **Privacy & Local In-Memory Buffer (SR-2)**: The audio stream is buffered exclusively in volatile RAM (`AudioBuffer`) with automatic eviction of stale audio. Raw audio is never persisted to disk.
- **Security Validation Gate (Architecture 3.3)**: `SecurityValidator.validate_source(command)` validates that every received command carries a valid session token issued during an active listening window.

---

## Repository Architecture

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
│       │   └── capture.py            # Audio capture driver (hardware mic or test streams)
│       ├── detector/
│       │   ├── __init__.py
│       │   ├── engine.py             # AcousticPatternEngine, SimulatedEngine
│       │   ├── state.py              # SessionManager state machine (IDLE -> LISTENING)
│       │   └── wake_word.py          # WakeWordDetector: detect_wake_word(audio_chunk) (FR-1)
│       ├── security/
│       │   ├── __init__.py
│       │   └── validator.py          # SecurityValidator: validate_source(command) (SR-1)
│       └── feedback/
│           ├── __init__.py
│           └── indicator.py          # FeedbackModule: notify(status) and LED state indicator (FR-10)
├── tests/
│   ├── conftest.py                   # Pytest fixtures and synthetic audio generation
│   ├── test_tc01_wake_word.py        # IEEE TC-01: Wake-word detection latency (<1s) & state transition
│   ├── test_tc10_security_gating.py  # IEEE TC-10: Gating verification & non-wake rejection
│   ├── test_audio_buffer.py          # Buffer eviction, capacity limits, thread-safety (SR-2)
│   └── test_security_validator.py    # Session authorization, token expiration, confidence safety
├── examples/
│   └── demo_wake_word.py             # Interactive demonstration of wake word lifecycle
├── pyproject.toml                    # Package metadata and test configurations
└── README.md                         # Project documentation and integration guide
```

---

## Traceability to Requirements & IEEE Test Cases

| Req ID | Requirement Description | Implementation Module | IEEE Test Case | Test Status |
|---|---|---|---|:---:|
| **FR-1** | Wake / Listen within 1s | `WakeWordDetector.detect_wake_word()` | **TC-01** (`test_tc01_wake_word.py`) | **PASSED** |
| **SR-1** | Wake-Word Gating | `SessionManager`, `SecurityValidator` | **TC-10** (`test_tc10_security_gating.py`) | **PASSED** |
| **SR-2** | Local-Only Audio Processing | `AudioBuffer` (in-memory rolling deque) | `test_audio_buffer.py` | **PASSED** |
| **SO-1** | Command Source Integrity | `SecurityValidator.validate_source()` | `test_security_validator.py` | **PASSED** |
| **FR-10**| User Feedback / LED | `FeedbackModule.notify()`, `on_state_change()` | `test_tc01_wake_word.py` | **PASSED** |

---

## Quick Start & Verification

### 1. Run Automated Unit & IEEE Test Suite
```bash
python3 -m pytest tests/ -v
```
All 22 unit tests verify:
- Sub-second wake detection (FR-1, TC-01)
- Strict rejection of audio lacking the wake word (SR-1, TC-10)
- In-memory rolling buffer constraints (SR-2)
- Session token authorization and security validation (SO-1, SR-1)

### 2. Run the Interactive Wake-Word Demo
```bash
python3 examples/demo_wake_word.py
```

---

## Integration Guide for Teammates

### For Aaditya (`aadityaV-goat`) — US-02 (Play), US-03 (Pause), US-04 (Resume)
1. Hook your `CommandMapper` into `AudioCaptureComponent.register_callback()`:
   When `wake_detector.is_listening` is `True`, feed captured audio to your ASR engine to recognize `"play"`, `"pause"`, or `"resume"`.
2. Wrap your recognized command in a `Command` object:
   ```python
   cmd = Command(type="play", confidence=0.92, session_id=detector.active_session_token)
   ```
3. Pass through the security validator before executing on `MediaPlayerInterface`:
   ```python
   if validator.validate_source(cmd):
       media_player.play()
       feedback.notify("ok")
   else:
       feedback.notify("error")
   ```

### For Aarohi (`aarohijaiswal`) — US-05 (Next), US-06 (Previous), US-07 (Volume)
1. Map recognized speech for `"next"`, `"previous"`, `"volume up"`, `"volume down"`.
2. Construct the corresponding `Command(type="next", ..., session_id=detector.active_session_token)`.
3. Dispatch via `CommandExecutor` to `media_player.next()`, `previous()`, `volume_up()`, `volume_down()`.
