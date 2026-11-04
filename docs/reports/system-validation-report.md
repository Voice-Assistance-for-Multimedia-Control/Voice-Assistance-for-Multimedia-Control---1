# System Validation Report

Voice Assistance for Multimedia Control: final results of the system test cases TC-01 to TC-16 in the [Software Test Plan (Sprint 2)](../Software_Test_Plan_Sprint2.docx), run live on the test laptops (microphone, offline Vosk recognizer, YouTube in Chrome). Requirements refer to [SRS v1.1](../../1_Software_Requirements_Specification_v1.1.pdf). Detailed records, dates and evidence are in [`docs/test-log.md`](../test-log.md) and [`docs/evidence/`](../evidence/).

## Summary

| Result | Test cases |
|---|---|
| PASS | 15 (TC-01 to TC-05, TC-07 to TC-16) |
| PASS with documented limitation | 1 (TC-06 Previous, deviation D-6) |
| FAIL | 0 |
| Not tested | NFR-5 ESP32 portability (out of scope, deviation D-1) |

All 210 automated unit and integration tests also pass: see [`unit-test-report.md`](unit-test-report.md), [`code-coverage-report.md`](code-coverage-report.md) and [`branch-coverage-report.md`](branch-coverage-report.md).

## Results per test case

| Test case | Requirement | Expected result | Observed result (live) | Result | Evidence |
|---|---|---|---|---|---|
| TC-01 Wake-word detection | FR-1 | Enters LISTENING within 1 s of "hey media" | Wake word detected with confidence 1.00; LISTENING entered. Wake-word latency 40–52 ms in the 2-hour run | PASS | Test log 4.1, 17.5 |
| TC-02 Play | FR-2 | Playback starts within 2 s | Video started; 8 of 8 plays succeeded, average 653 ms | PASS | Test log 7, 17.4 |
| TC-03 Pause | FR-3 | Playback pauses within 2 s | Video paused; 7 of 7 succeeded, average 663 ms | PASS | Test log 7, 17.4 |
| TC-04 Resume | FR-4 | Playback resumes within 2 s | Video continued; 7 of 7 succeeded, average 667 ms | PASS | Test log 7, 17.4 |
| TC-05 Next | FR-5 | Next video within 2 s | Switched to the next video; 5 of 5 succeeded, average 1,069 ms | PASS | Test log 7, 17.4 |
| TC-06 Previous | FR-6 | Previous video within 2 s | Returns to the previous video when said within about 4 s of a video starting (live check 27 Oct, Sprint 2 video). Later in a video YouTube restarts the current video instead, and the assistant reports the failure (7 of 7 in the US-11 run) | PASS with limitation | Test log 7, 17.4; README D-6 |
| TC-07 Volume up | FR-7 | Volume +10% within 1 s | Volume increased; 6 of 6 succeeded, average 665 ms | PASS | Test log 7, 17.4 |
| TC-08 Volume down | FR-8 | Volume −10% within 1 s | Volume decreased; 7 of 7 succeeded, average 662 ms | PASS | Test log 7, 17.4 |
| TC-09 Response time | NFR-1 | Command executed within 2 s of end of speech (volume within 1 s) | 40 successful actions: average 712 ms, slowest 1,160 ms; slowest volume action 686 ms. All within target | PASS | Test log 17.4; `evidence/us11-run-v2.log` |
| TC-10 Wake-word gating | SR-1 | No action without the wake word | Commands spoken without "hey media" did nothing; no false triggers during the 2-hour run | PASS | Test log 17.5; Sprint 2 video |
| TC-11 Unsupported commands | FR-9 | Unknown phrases rejected, no media action | 10 of 10 unsupported phrases rejected with the error tone, in two tests of 5 phrases | PASS | Test log 5, 5.1 |
| TC-12 Feedback | FR-10 | Acknowledgement for every executed or rejected command | Success and rejection tones and console messages seen in every live session | PASS | Test log 4.3, 6 |
| TC-13 Recognition reliability | NFR-2 | At least 90% of valid commands recognized correctly | 46 of 51 attempts correct (90.2%) | PASS | Test log 17.4; `evidence/us11-run-v2.log` |
| TC-14 Continuous availability | NFR-3 (2 h, D-5) | Listening-ready for 2 hours without restart | One process for more than 2 hours; 5 of 5 periodic commands passed; memory flat; no errors | PASS | Test log 17.5; `evidence/us10-*` |
| TC-15 First-time-user usability | NFR-4 | A new user issues a working command without a manual | 2 of 2 first-time users succeeded; one needed a hint about the wake word | PASS | Test log 13 |
| TC-16 Local processing | SR-2 | No audio sent off the device | Offline Vosk recognizer; network check during 10 commands showed no outside connections from the assistant | PASS | Test log 10; `evidence/us17-network-check.md` |

## Additional user-story checks

| Story | Check | Result | Evidence |
|---|---|---|---|
| US-12 Unclear commands | Unclear speech gives "Didn't catch that, please repeat" and no action | PASS | Test log 6 |
| US-13 Microphone errors | Missing microphone reported; listening resumes when it returns | PASS (unit tested; simulated microphone fault at start-up checked live in US-18) | Unit test report; test log 17.6 |
| US-14 Media player errors | Failures detected and reported; success only when the player really changed | PASS | Test log 7 |
| US-15 Recognition-error recovery | Recovers without restart after a recognition error | PASS | Test log 17.3 |
| US-16 Microphone privacy | `m` + Enter turns listening off and on | PASS | Test log 17.2 |
| US-18 Startup check | Components checked; failures named and start-up stopped | PASS | Test log 17.6; `evidence/us18-*` |
| US-19 Status indicator | READY / LISTENING / MUTED shown | PASS | Unit test report; Sprint 2 video |
| US-20 Duplicate commands | One command per wake word | PASS | Test log 17.1 |

## Deviations affecting validation

The test environment differs from the original documents as recorded in the README: a laptop instead of a Raspberry Pi / ESP32 (D-1), YouTube in Chrome as the player (D-2), the offline Vosk recognizer (D-3), a 2-hour instead of 8-hour availability target approved by the instructor (D-5), and the Previous limitation (D-6).
