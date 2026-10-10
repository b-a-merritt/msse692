## A Human Cyber-Physical System Architecture for Supporting Moral Self-Regulation

# Quality Assurance Report

Last updated: Oct 10, 2026

# **Team: *Individual Track*** {#team:-individual-track}

* Ben Merritt

[Team: Individual Track](#team:-individual-track)

[Summary](#summary)

[Testing Strategy & Results](#testing-strategy-&-results)

[Approach](#approach)

[Strategy](#strategy)

[Coverage](#coverage)

[Results](#results)

[User acceptance testing](#user-acceptance-testing)

[Bug Report & Resolution](#bug-report-&-resolution)

[Severity scale](#severity-scale)

[Bugs fixed](#bugs-fixed)

[Open bugs](#open-bugs)

[Limitations by design](#limitations-by-design)

[Quality Metrics](#quality-metrics)

[Code quality](#code-quality)

[Performance](#performance)

[Security](#security)

[Accessibility](#accessibility)

[System Readiness Assessment](#system-readiness-assessment)

[Production readiness](#production-readiness)

[Risks and mitigations](#risks-and-mitigations)

[Week 8 readiness](#week-8-readiness)

#

# **Summary** {#summary}

The prototype receives mocked conversation observations, assesses one target speaker against SQL-defined normative models, waits for a repair, and records interventions. All 543 automated tests pass. The unit suite alone (excluding integration tests) covers 100% of statements and branches. Lint, formatting, and strict type checks report no issues.

Testing found 10 open defects. Four are P2, and most of those are related to losing queued work or interventions when a storage write fails, the server stops, or the process crashes. Normal operation and the stress run did not trigger them. Eleven defects found earlier are fixed, including a P1 in which the loud-and-fast rule flagged short, calm lines.

The system is ready for research demonstration on one machine. It is not ready for production. It has no authentication, it loses work under failure, and it has not been tested at the case length its performance requirement names.

# **Testing Strategy & Results** {#testing-strategy-&-results}

## **Approach** {#approach}

The tests are split into two suites that run separately.

The unit suite (231 tests) checks decisions in isolation. It checks things like request validation, status selection, deadline arithmetic, window timing, error translation, and worker orchestration. It uses in-memory input and output. It never opens a database, a file, a network connection, or a worker thread. They complete in about two seconds.

The integration suite (312 tests) runs the same code against real dependencies. It checks SQL rules against stored observations, transaction rollback, concurrent ingestion, queue coalescing, startup validation, and shutdown. It runs in about fourteen seconds.

End-to-end testing was done manually using the running server. I replayed ten film scenes through the HTTP API and compared the interventions to predictions. The stress test replayed 9,966 observations through the same path.

The following were not tested:

* More than one server process. The scheduler keeps coordination state in memory and assumes a single process.
* A forced crash during assessment followed by restart. Restart behavior is tested at the component level only.
* Live audio, speech recognition, and speaker diarization. These are out of scope, and all input is mocked.
* Accessibility, because the system has no user interface.

## **Strategy** {#strategy}

I wrote most of the tests with an AI coding assistant. Integration suites usually cover only the main workflows because integration tests are slow to write and maintain. Near full coverage is usually left to unit tests. With AI writing the tests, an extra integration test costs little, so I also covered failure paths against real dependencies, such as storage rollback, queue failure after commit, and shutdown with tasks waiting.

The risk with AI-written tests is that they pass without actually testing anything, or, worse, that they confirm the wrong behavior. Every test has to be reviewed. To keep review fast, the tests must avoid [mystery guests](https://thoughtbot.com/blog/mystery-guest): each test spells out its own scenario data in the test body, and fixtures only create and clean up things like a temporary database. I need to be able to check a test by reading one function, matching the inputs to the assertions, without tracing fixture chains or opening data files.

## **Coverage** {#coverage}

Coverage is measured with coverage.py through pytest-cov, with branch measurement on. CI enforces the 95% minimum against the unit suite alone, starting from empty coverage data, so integration tests cannot satisfy it. The integration suite then appends to a separate combined report.

| Suite | Statements | Missed | Branches | Partial | Coverage |
| :---- | :---- | :---- | :---- | :---- | :---- |
| Unit only | 1,421 | 0 | 160 | 0 | 100% |
| Unit and integration | 1,421 | 0 | 160 | 0 | 100% |

*Unit tests showing 100% coverage.*![][image1]

*Integration tests showing 99.24% coverage.*![][image2]The integration run prints one warning from a third-party library (Starlette deprecating its use of `httpx` in the test client). It does not affect the application.

## **Results** {#results}

| Suite | Tests | Passed | Failed | Skipped | Time |
| :---- | :---- | :---- | :---- | :---- | :---- |
| Unit | 231 | 231 | 0 | 0 | 1.7 s |
| Integration | 312 | 312 | 0 | 0 | 14 s |
| Total | 543 | 543 | 0 | 0 |  |

## **User acceptance testing** {#user-acceptance-testing}

I did not test with people. The system measures undesired behavior in a person's speech, and running it on participants would have required ethics review that this practicum does not include.

Instead, I ran a scenario-based acceptance test. I converted twelve scenes from films and television into mocked observation files, with generic speaker identifiers and no source audio or video. For each scene, I wrote down which interventions the target speaker (`speaker-2`) should receive, then replayed the scene through the HTTP API at its original pacing and compared the result. Cases 1 and 2 were used to tune the models and are not scored. The scored run used the same detection code that is in the repository now.

| Case | Predicted | Actual interventions | Result |
| :---- | :---- | :---- | :---- |
| 3 | None | None. A loud "Wait" was repaired by "I apologize, okay?" | Match |
| 4 | One or two, for intensity and language | Three: vulgar language, loud and fast, extended turn | One extra |
| 5 | Loud only, if any | Two: loud and fast ("Silence\!"), repeated interruption | Interruption not predicted |
| 6 | Two: absolutist phrase and shouting | Three: extended turn, loud and fast, absolutist phrase ("You always talking") | One extra |
| 7 | None | One: loud and fast ("Such as?") | One false positive |
| 8 | None | None | Match |
| 9 | At least two: language and interruption | Three: vulgar language, repeated interruption, loud and fast | Match |
| 10 | Interruption and the "crazy" label | Three: loud and fast, vulgar language ("damn dishes"), repeated interruption | Label missed, loud false positive |
| 11 | Vulgar language only, not "tough kid" | One: vulgar language | Match |
| 12 | None | One: loud and fast ("I got your letter.") | Mismatch: false positive |

Four cases matched, two matched with one extra intervention, and four did not match. The ten cases produced 17 interventions. Three of them (cases 7, 10, and 12\) are false positives from the loud-and-fast rule, and one predicted intervention (the label in case 10\) was missed. The other unpredicted interventions (extended turns, the case 5 interruption, and "damn") follow the rules as written, so they show gaps in my predictions, not detector errors.

In case 10, Brooke's insult produced no intervention because she is not the target speaker, as expected.

![][image3]

# **Bug Report & Resolution** {#bug-report-&-resolution}

| Severity scale |  |
| :---- | :---- |
| **Sev** | **Meaning** |
| **P0** | The system cannot run, or stored records are corrupted. No workaround. |
| **P1** | The core workflow gives a wrong result in normal use. |
| **P2** | Work or results are lost or wrong under a failure, but workarounds exist. |
| **P3** | Low impact: rare, cosmetic, or not reachable with the current code. |

| Bugs fixed |  |  |
| :---- | :---- | :---- |
| **Sev** | **Problem** | **Fix** |
| **P1** | The loud-and-fast rule computed speech rate per chunk, so short chunks inflated it ("Such as?" is 2 words in 0.32 s, or 375 words per minute), and calm lines just above −18 dBFS matched. | Required chunks of at least 1.5 seconds and raised the volume threshold to −17 dBFS. Both are model parameters. |
| **P2** | `POST /api/v1/interventions/deliver` marked every pending intervention as sent, across all cases, so one client could receive another case's interventions. | Delivery moved to `POST /api/v1/cases/{case_id}/interventions/deliver` and marks only that case's pending interventions. |
| **P2** | "You're acting crazy" matched neither the descriptor list ("crazy" was not in it) nor the address patterns ("acting" was not in them), so the predicted label in case 10 was missed. | Expanded the insult terms that match only when addressed to the listener, including "crazy". Added "acting" to the address patterns, and matched bare labels such as "you're crazy". |
| **P2** | The loud-and-fast model also required the phrases "you are wrong" or "you are ridiculous" in the same chunk, so it rarely matched. The interruption model required three overlaps of 300 ms, which missed the interruptions in the tuning cases. | Split loudness and insulting address into separate rules. Lowered the interruption rule to two overlaps of 150 ms. |
| **P2** | Vulgar language was part of the character-label model, so swearing produced a message about describing the person. | Created a separate vulgar-language model with its own message. |
| **P2** | The replay script timed each observation from its start time. Overlapping speech was sent immediately, so replays did not reproduce the scene's timing. | The script now waits until each chunk's end time and tracks the latest end time across overlapping chunks. |
| **P2** | The interruption rule joined each subject chunk against every other chunk and ran a nested subquery per pair. Its cost grew faster than the case length. | Rewrote the rule with window functions that make one ordered pass over the case. |
| **P2** | Nothing checked stored models before the worker used them. A model with invalid SQL or no intervention message failed only when a case reached it. | Startup now validates every model's schema, runs each rule against an empty case, and checks for a message. An invalid model stops startup. |
| **P3** | Text normalization did not treat dashes as a word boundary, so phrases joined by one were missed. | Added dashes to the normalization table. |
| **P3** | Assessment lookups by case and model, and pending-intervention lookups, had no indexes. | Added three indexes. |

| Open bugs |  |  |  |
| :---- | :---- | :---- | :---- |
| **Sev** | **Problem** | **Impact** | **Workaround** |
| None |  |  |  |

## **Limitations by design** {#limitations-by-design}

These follow from decisions in the requirements and architecture. They are not defects, but they affect results.

* After a match is confirmed, the same model does not flag that speaker again until a repair occurs. A second offense without a repair produces no new intervention.
* The phrase lists are fixed. Case 8 contains a threat that uses no listed phrase, so it was not detected, as predicted.
* The target speaker is fixed when the database is first initialized and cannot change per case.
* The system has no authentication and no limit on transcript size. The requirements accept this risk for a local research prototype.

| The system intentionally ignores some retries. For example, if SQLite stays locked past its 5-second timeout and an operation fails, it is marked failed and never retried, even after restart. This is acceptable because we are dealing with time-sensitive, human-in-the-loop conditions. There is likely a small window in which intervention is possible. It is not enough to intervene–an individual must have a chance to correct their behavior. |
| :---- |

# **Quality Metrics** {#quality-metrics}

| Code quality |  |  |
| :---- | :---- | :---- |
| **Check** | **Tool** | **Result** |
| Lint | Ruff | No issues |
| Formatting | Ruff format | 197 files already formatted |
| Types | mypy, strict mode | No issues in 78 source files |
| Cyclomatic complexity | Ruff (McCabe) | No function above 8\. Four functions exceed 5: `evaluate_case` (8), `validate_models` (7), `assess_model` (6), `resolve_pending` (6) |
| Size |  | 3,282 lines of Python, excluding migrations |

Pre-commit runs Ruff, the formatter, mypy, and a lockfile check before each commit. GitHub Actions runs the same checks on every push and pull request, then enforces unit coverage, runs the integration suite, and uploads both coverage reports.

![][image4]

## **Performance** {#performance}

The requirement is a p95 assessment time of at most 250 ms. All timings come from the structured log timestamps, so they include logging cost. Both runs used one machine (WSL2 Linux, 12 cores, Python 3.13, SQLite 3.53) and one worker.

The baseline replayed the twelve film cases at their original pacing.

| Metric | p50 | p95 | Max |
| :---- | :---- | :---- | :---- |
| Observation saved to evaluation saved | 16.5 ms | 32.0 ms | 67.8 ms |
| Assessment task | 12.1 ms | 23.9 ms | 36.5 ms |
| Repair check task | 15.2 ms | 32.2 ms | 52.5 ms |
| Deadline lateness (n=25) | 46.0 ms | 95.9 ms | 99.5 ms |
| Intervention lateness (n=26) | 46.2 ms | 87.8 ms | 113.9 ms |

The stress test sent 9,966 observations over about 14 minutes in six phases of increasing load, rotating through ten scripted scenarios of about 30 observations each.

| Phase | Offered | Achieved | Worker busy | Observation to evaluation p50 / p95 / max |
| :---- | :---- | :---- | :---- | :---- |
| 1 | 3.7/s | 3.5/s | 5% | 13.9 / 19.8 / 48 ms |
| 2 | 7.2/s | 6.6/s | 9% | 13.7 / 21.3 / 45 ms |
| 3 | 10.6/s | 9.4/s | 13% | 14.2 / 25.8 / 69 ms |
| 4 | 20.9/s | 16.5/s | 23% | 15.0 / 30.6 / 72 ms |
| 5 | 31.6/s | 22.2/s | 32% | 15.4 / 35.2 / 90 ms |
| 6 | 40.9/s | 25.5/s | 40% | 16.7 / 48.6 / 237 ms |

The p95 stayed under 50 ms in every phase, well under the 250 ms target. The worst single result was 337 ms: 237 ms of evaluation plus up to 100 ms of deadline lateness. That is 3.4% of the shortest repair allowance (10 s).

Achieved throughput fell behind the offered rate from phase 4 on, while the worker was busy at most 40% of the time. The slowest phase 6 evaluations spent 90 to 150 ms between saving the observation and queueing its task, so the limit is in ingestion, not assessment. I did not find the system's maximum rate.

## **Security** {#security}

The requirements accept the risk of having no application security in this prototype. The system has no authentication, authorization, user isolation, or secrets, and should only listen on localhost. The following measures are implemented:

* Pydantic validates every request body and path parameter in strict mode. Unknown fields are rejected, identifiers cannot contain `/`, timestamps must include a time zone, and signal levels and times must be ordered.
* Error responses carry a fixed message, a closed error code, and a request ID. They never include driver messages, SQL, file paths, or input values.
* Logs record exception types but not exception messages, which can contain SQL parameters or transcripts. Validation failures log the field location and error type, not the submitted value.
* The case data contains no source audio, video, names, or copied transcripts. Speakers are generic identifiers.

## **Accessibility** {#accessibility}

Not applicable. The system is an HTTP API with no user interface. FastAPI generates the OpenAPI page at `/docs`.

# **System Readiness Assessment** {#system-readiness-assessment}

## **Production readiness** {#production-readiness}

The system is not deployable to production. It runs reliably as a single local process for research replay. A production deployment would need:

1. Authentication and authorization, a request size limit, and TLS.
2. A decision on scaling. SQLite and in-memory scheduling limit the system to one process.
3. An ethics review before the system processes the speech of real people.

| Risks and mitigations |  |
| :---- | :---- |
| **Risk** | **Mitigation** |
| Continue to have false interventions undermine the demonstration | Fix the false positives by correcting the identification behavior. |
| Interventions leak between concurrent cases. | While only one case would be running at a time for the prototype, this is still an easy bug to fix to avoid unexpected behavior. The fix is to scope the request to a single case ID. |

## **Week 8 readiness** {#week-8-readiness}

Remaining work before the final presentation:

1. Fix the three outstanding bugs mentioned above, specifically the loud-fast false-positive bug, scoping interventions to a particular case, and broader lexicographical identification of insults.
2. Prepare the presentation and demonstration.
