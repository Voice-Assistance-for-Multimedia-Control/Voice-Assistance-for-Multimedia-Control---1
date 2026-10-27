# Sprint 2 Test Log

**Project:** Voice Assistance for Multimedia Control
**Date:** 26 October 2026 (updated 27 October 2026)
**Tester:** Aarohi

## 1. Test Environment

- **Operating system:** Windows
- **Microphone:** Built-in laptop microphone
- **Browser:** Google Chrome 155.0.8059.85 (64-bit)
- **Application:** Python application running in the `.venv` virtual environment
- **Speech recognition:** Vosk offline backend by default
- **Vosk model:** `models/vosk-model-small-en-in-0.4`
- **Media player:** YouTube in the browser

## 2. Summary of Results

| Test / Requirement | Current status | Evidence / Remaining work |
|---|---|---|
| Full automated test suite | PASS | 190 passed, 0 failed; 11 warnings (27 October, after merging main) |
| US-08: Unsupported commands | Verified | First live test 5/5 rejected; re-test with 5 new phrases 5/5 rejected, no media action (27 October) |
| US-12: Unclear commands | Verified for observed test | Unclear speech rejected, no media action observed, application returned to IDLE |
| US-14: Media player error handling | Verified | Automated tests passed; failure path and all seven successful actions confirmed live (27 October) |
| US-20: Duplicate execution prevention | Verified | Automated one-command-per-wake-word and identical-audio replay tests pass; live microphone check passed on 27 October |
| SR-2: Local audio processing | Configuration and runtime support verified; network verification pending | Record a network-traffic check |
| TC-09 / NFR-1: Performance | Preliminary evidence available | Complete the planned performance test |
| NFR-2: Recognition reliability | PASS based on recorded results | 45 of 50 valid-command utterances succeeded (90%) |
| NFR-3: Availability | PENDING — 8-hour run by Aaditya (US-10); 15-minute preliminary run passed | SRS requires the application to run at least 8 hours without restarting |
| NFR-4: First-time-user usability | PENDING | Test with two first-time users on 28 October |
| US-09: Command feedback (Abhay) | Automated tests pass | `test_us09_feedback.py` passes (PR #34); live feedback tones seen in the live sessions above |
| US-13: Microphone error handling (Abhay) | Automated tests pass | `test_us13_mic_error_handling.py` passes (PR #34) |
| US-16: Microphone privacy / mute (Abhay) | Automated tests pass; live check pending | `test_us16_mute_and_timing.py` passes (23 tests) |
| US-19: Listening status indicator (Abhay) | Automated tests pass | `test_us19_status_and_us17_local.py` passes (18 tests) |
| US-15: Recover from recognition errors (Aaditya) | Automated tests pass; live check reported done (PR #41) | `test_us15_recovery.py` passes (18 tests); add Aaditya's live-check details when he sends them |
| US-17 / SR-2: Local voice processing (Abhay) | AWAITING EVIDENCE | Automated local-processing checks pass; waiting for Abhay's network-check result (10 commands) |
| US-11 / NFR-1 / NFR-2: Accuracy and speed (Aaditya) | AWAITING EVIDENCE | Waiting for Aaditya's formal results (50 utterances; 7 commands × 5). Preliminary figures are in sections 9 and 11 |
| US-10 / NFR-3: Continuous availability (Aaditya) | PENDING — 8-hour run by Aaditya (US-10); 15-minute preliminary run passed | See NFR-3 row above |
| US-18: Startup system check (Aaditya) | NOT STARTED | Due Wednesday 28 October |
| Deprecation warnings | Not blocking tests | 11 warnings related to NumPy 2.5 and `sounddevice.py` |

## 3. Automated Test Results

**Full test suite**

- Command: `python -m pytest tests/ -v`
- Result: **190 passed, 0 failed** (27 October, after merging `main`)
- Recorded duration: 12.44 seconds
- Warnings: 11 deprecation warnings originating from `sounddevice.py` related to NumPy 2.5.

**Targeted test results**

| Test selection | Result |
|---|---|
| Unclear, unrecognized and invalid commands | 6 passed, 161 deselected |
| Duplicate, replay and wake-word tests | 30 passed, 137 deselected |
| Media controls: `python -m pytest tests/test_media_controls.py -v` | 20 passed |
| Mute and timing test file | 23 passed |

These results establish that the recorded automated tests passed. They do not prove that every possible real-world audio input or browser state has been tested.

## 4. Live Voice-Command Tests

### 4.1 Wake-word detection

- **Command:** `hey media`
- **Expected result:** Application detects the wake word and enters the listening state.
- **Observed result:** Wake word detected with confidence 1.00; application entered `LISTENING`.
- **Status:** PASS for the observed test.

### 4.2 Supported commands

The earlier recorded live checks reported successful recognition and execution for the following commands:

| Command | Previously recorded response time | Observed result |
|---|---:|---|
| Play | 634 ms | Reported executed successfully |
| Pause | 620 ms | Reported executed successfully |
| Resume | 652 ms | Reported executed successfully |
| Next | 653 ms | Reported executed successfully |
| Previous | 626 ms | Reported executed successfully |
| Volume up | 613–657 ms | Reported executed successfully |
| Volume down | 619–645 ms | Reported executed successfully |

The measurements above are from earlier recorded attempts. They should not be treated as a complete performance test.

### 4.3 Additional live verification — 26 October

The following additional results were recorded during the live application session:

| Test | Observed result | Response time | Status |
|---|---|---:|---|
| Volume up | Recognized with confidence 1.00; security validation passed; command reported executed successfully | 688 ms | PASS for observed execution |
| Pause | Recognized with confidence 1.00; security validation passed; command reported executed successfully | 719 ms | PASS for observed execution |
| Unclear speech | Recognition error handled, rejection feedback emitted, and application returned to IDLE | Not recorded | PASS for observed error handling |

For volume up and pause, the application logged the response time from the end of speech to the action. Both were within their respective logged timing targets.

**Interpretation:** A successful execution message in the logs does not by itself establish that the visible YouTube playback state or volume changed. The visible results were checked separately; see the live verification in Section 7 (27 October).

## 5. US-08 — Reject Unsupported Commands

**Date:** 26 October 2026
**Method:** Live microphone test after activating the wake word `hey media`.

| Test phrase | Observed result | Status |
|---|---|---|
| Open Instagram | Recognized and rejected as unsupported | PASS |
| Take a screenshot | Recognized and rejected as unsupported | PASS |
| Send an email | Recognized and rejected as unsupported | PASS |
| Turn on the lights | Recognized as `turn on lights` and rejected as unsupported | PASS |
| Check the weather | Recognized and rejected as unsupported | PASS |

**Result:** 5/5 confirmed attempts passed. No unsupported action was executed during these attempts.

Some additional attempts returned `Speech was not understood`. These were inconclusive and were not counted as confirmed unsupported-command passes.

**Status of the first test:** Passed for the five listed live attempts. The phrases had been temporarily added to the recognizer's vocabulary for that test, so a re-test with new phrases was carried out (below).

### 5.1 Re-test with five new phrases — 27 October 2026

**Method:** Live microphone test after saying "hey media". The five phrases below were not used in the first test, and no phrase was taught to the recognizer.

| # | Phrase spoken | Observed result | Media action? | Status |
|---|---|---|---|---|
| 1 | open facebook | Rejected: "Speech was not understood"; error feedback logged; returned to IDLE | None | PASS |
| 2 | set an alarm | Same | None | PASS |
| 3 | what time is it | Same | None | PASS |
| 4 | call my mother | Same | None | PASS |
| 5 | open Netflix | Same | None | PASS |

**Note:** The Vosk grammar is closed, so out-of-vocabulary speech is rejected by the recognizer before the command mapper runs. All five attempts were rejected, logged, and caused no media action. Mapper-level rejection of recognized-but-unsupported text (for example "open netflix" and "send an email") is covered by the automated tests `test_unsupported_or_unclear_command_is_rejected` and `test_map_command_rejects_everything_else`.

**Result:** 5/5 passed. No unsupported phrase caused a media action.

**Status:** Verified.

## 6. US-12 — Handle Unclear Voice Commands

**Date:** 26 October 2026

| Test scenario | Observed result | Status |
|---|---|---|
| Unrecognized speech after wake word | Assistant displayed “Didn't catch that, please repeat” | PASS |
| Recognition error handling | `UnrecognizedCommandError` was handled and rejection/failure feedback was emitted | PASS |
| Session recovery | Application returned to `IDLE` | PASS |
| No unintended media action | No media action was observed during the live unclear-speech test | PASS for the observed test |

**Live test evidence:**

- The application detected `hey media` with confidence 1.00.
- The application prompted the user to repeat the unclear speech.
- The error handler processed `UnrecognizedCommandError`.
- Rejection/failure feedback was emitted.
- The application returned to `IDLE`.
- The user confirmed that no media action was taken during this test.

**Conclusion:** US-12 passed for the observed live scenario. Broader testing with different unclear phrases may still be useful.

## 7. US-14 — Media Player Error Handling

### Automated tests

- Command: `python -m pytest tests/test_media_controls.py -v`
- Result: **20 passed**
- The tests cover media-control success and failure behavior, including simulated disconnected browser sessions and volume limits.

### Error-handling evidence

- `next_track()` handles a simulated disconnected Selenium session, returns `False`, and displays a friendly error message.
- `previous_track()` handles a simulated disconnected Selenium session in the same way.
- Tests verify that technical exception details are not unnecessarily printed as user-facing error messages.
- A live disconnected-session path was previously exercised: the command failed safely, failure feedback appeared, and the system returned to `IDLE`.

### Live verification of successful actions — 27 October 2026

**Method:** Live microphone test with a YouTube playlist open in the Chrome window controlled by the application. Each command was spoken after "hey media", and the visible result in the browser was checked.

| Command | Expected visible result | Observed | Status |
|---|---|---|---|
| Play | Video starts playing | Video started playing | PASS |
| Pause | Video pauses | Video paused | PASS |
| Resume | Video continues | Video continued | PASS |
| Next | Switches to the next video | Switched to the next video | PASS |
| Previous | Returns to the previous video | Returned to the previous video | PASS |
| Volume up | Volume increases one step | Volume increased | PASS |
| Volume down | Volume decreases one step | Volume decreased | PASS |

**Conclusion:** All three US-14 criteria are covered. A failed operation is detected and gives an error indication (automated tests and the earlier live failure check). Success is never reported when an operation fails (the media functions verify the result before returning True). All seven successful actions were confirmed visibly.

**Status:** Verified: automated error-handling tests passed, and visible success behavior was confirmed live on 27 October.

## 8. US-20 — Prevent Duplicate Command Execution

**Automated evidence:**

- `test_one_command_per_wake_word` passed.
- `test_one_command_executes_only_once_per_wake_word` passed.
- `test_replayed_command_without_new_wake_word_is_ignored` passed.
- The selected duplicate, replay and wake-word test group passed: 30 passed, 137 deselected.
- The full project test suite passed: 190 passed, 0 failed, with 11 non-blocking deprecation warnings (27 October, after merging main).
- `test_new_wake_word_allows_next_command_after_session_ends` passed, confirming that a new wake word allows a separate command after the previous session ends.

| Scenario | Status |
|---|---|
| One command per wake-word session | PASS in automated tests |
| Command without a new wake word is ignored | PASS in automated tests |
| Session returns to IDLE after processing | PASS in recorded integration tests |
| Identical raw-audio replay cannot execute the same action twice | PASS in automated test (`test_identical_command_audio_replay_without_new_wake_word_is_ignored`) |

**Conclusion:** One-command-per-wake-word behavior and identical-audio replay protection pass in automated tests. See the 27 October live microphone verification at the end of this log.

**Additional regression test — identical command audio replay**

- Test: `test_identical_command_audio_replay_without_new_wake_word_is_ignored`
- Result: PASS
- Verification: The same command audio bytes were replayed after the first command completed, without a new wake word.
- Assertions: The media action executed only once, exactly one result was recorded, and the session remained in `IDLE`.
- Integration suite: 62 passed (at the time this test was added).
- Full test suite at that time: 171 passed, 0 failed, 11 deprecation warnings. The latest full-suite result is 190 passed (Section 3).
- Limitation: This is a synthetic-audio integration test using a scripted transcriber; it does not replay recorded audio through the microphone.

**Conclusion:** Automated replay protection is verified for the tested scenario. Do not claim all possible duplicate replay scenarios are covered.

## 9. TC-09 / NFR-1 — Response-Time Performance

**Requirement:** Valid voice commands should execute within the specified 2,000 ms target. The application also logs tighter targets for particular commands.

### Recorded evidence

- Earlier live command measurements ranged from 613–673 ms.
- Additional live measurements were 688 ms for volume up and 719 ms for pause.
- The two additional measurements were within their respective logged targets.
- Timing-related automated tests passed.

Five earlier manual measurements were also recorded:

| Trial | Response time |
|---|---:|
| 1 | 1.84 seconds |
| 2 | 1.89 seconds |
| 3 | 2.00 seconds |
| 4 | 1.88 seconds |
| 5 | 1.68 seconds |

**Average:** 1.858 seconds (approximately 1.86 seconds).

Four of these five measurements were strictly below 2 seconds; one was exactly 2.00 seconds.

**Conclusion:** The preliminary results are encouraging, but the complete performance requirement remains pending until the planned measurement procedure is completed and its acceptance criteria are confirmed.

## 10. SR-2 — Local Audio Processing

**Requirement:** Raw audio is processed locally and is not transmitted off-device during normal operation.

### Evidence collected

- `src/voice_control/config.py` sets `recognizer_backend` to `vosk` by default.
- The configured model path is `models/vosk-model-small-en-in-0.4`.
- `Test-Path "models/vosk-model-small-en-in-0.4"` returned `True`.
- `main.py` defaults the command-line `--backend` argument to `vosk`.
- `main.py` calls `create_transcriber()` using the selected backend.
- The application started successfully with `python main.py`, and live wake-word and command recognition worked.

### Remaining verification

The configuration and successful runtime behavior support the use of Vosk for local speech recognition. However, a network-traffic check has not conclusively established that raw audio is never transmitted off-device during normal operation.

**Status:** Local backend configuration and runtime startup verified; network-traffic verification pending.

## 11. NFR-2 — Recognition Reliability

**Requirement:** Correctly recognize at least 90% of 50 valid-command utterances in a quiet room.

- Recorded successful utterances: 45 out of 50.
- Recorded success rate: 90%.
- Recorded unsuccessful utterances: 5.

**Status:** PASS based on the recorded 50-utterance test results.

## 12. NFR-3 — Availability

**Requirement:** Application remains running continuously for at least 8 hours without restarting (SRS).

- Preliminary result: Application remained running and responsive for 15 continuous minutes without restart. This is only a preliminary run and does not satisfy the 8-hour requirement.

**Status:** PENDING — 8-hour run by Aaditya (US-10); 15-minute preliminary run passed

## 13. NFR-4 — First-Time-User Usability

**Requirement:** A first-time user can use the application successfully without a manual, according to the approved Test Plan.

- The planned usability test with two first-time users has not yet been recorded.
- Planned test date: 28 October 2026.

**Status:** PENDING.

## 14. Warnings and Issues

- The full test run reported 11 `DeprecationWarning` messages from `sounddevice.py` related to NumPy 2.5.
- These warnings did not cause test failures.
- The full automated test suite completed successfully.
- Investigate the deprecation warnings separately; do not treat them as test failures.

## 15. Remaining Work

| Item | Current status | Next action |
|---|---|---|
| Automated project tests | PASS | Rerun before final merge or release |
| US-08 unsupported commands | Verified | None; retain both live test results |
| US-12 unclear commands | Passed for the observed live scenario | Test additional phrases if required |
| US-14 media error handling | Verified | None; retain the automated and live evidence |
| US-20 duplicate execution | Verified | None; retain the automated and live evidence |
| TC-09 / NFR-1 performance | Preliminary measurements available | Complete the planned performance test |
| NFR-2 recognition reliability | PASS in recorded test | Retain the 45/50 evidence |
| NFR-3 availability | PENDING — 8-hour run by Aaditya (US-10); 15-minute preliminary run passed | Aaditya completes the 8-hour run; record the result here |
| NFR-4 usability | PENDING | Test two first-time users on 28 October |
| SR-2 local audio processing | Configuration and runtime startup verified | Complete and record network-traffic verification |
| Deprecation warnings | Non-blocking warnings | Investigate separately if time permits |

## 16. Final Summary — 27 October 2026

- The latest full automated test run passed: **190 passed, 0 failed, with 11 deprecation warnings** (27 October, after merging `main`).
- Live Vosk startup, wake-word detection, and all seven commands were observed working at runtime.
- The live unclear-speech test handled the recognition error, returned to `IDLE`, and did not trigger a media action.
- US-08 is verified: the first live test passed 5/5, and the re-test with five new phrases passed 5/5 with no media action.
- US-14 is verified: automated error-handling tests passed and all seven successful actions were confirmed visibly on 27 October.
- US-20 is verified: automated regression tests pass (including identical-audio replay and acceptance of a new wake word), and the live microphone check passed on 27 October.
- Performance results are promising, but the full performance test remains pending.
- SR-2 configuration and runtime startup are verified; network-traffic verification remains pending.
- NFR-3 remains PENDING until Aaditya completes the 8-hour run.
- NFR-4 usability testing with two first-time users is planned for 28 October.
- The 11 deprecation warnings did not cause test failures.

**Overall assessment:** The automated test suite and the recorded live checks are encouraging. Do not mark any remaining item fully complete until its required evidence has been collected and documented.

### US-20 — Live Microphone Verification

**Date:** 27 October 2026

- Started the application using `python main.py`.
- Spoke the wake word followed by `play`; the command executed successfully.
- Repeated a command without saying the wake word again; no additional action occurred.
- Spoke the wake word again followed by `pause`; the command executed successfully.
- Confirmed that the application returned to IDLE after each executed command.

**Result:** Live microphone verification passed for one-command-per-wake-word behavior and normal processing of a new command.

**Limitation:** This test repeated a spoken command; it did not replay the exact same recorded audio.