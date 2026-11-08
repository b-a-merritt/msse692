## Online Normative Conformance of Conversational Observations

# Quality Assurance Report

Last updated: Nov 8, 2026

# **Team: *Individual Track***

* Ben Merritt

# **Summary**

The prototype transcribes live speech, stores it as observations, and asks a decision model fixed questions about each batch of speech. It stores the scores and action, and creates an intervention when the action is `intervene`.

All 570 automated tests pass. Unit tests alone cover 98.40% of statements and branches, above the required 95%. Lint, formatting, type checks, and the dependency audit report no issues.

Twelve film scenes were each replayed three times, and the intervention result never changed. On the 10 scenes also run with the earlier keyword rules, the decision model matched 8 and the rules matched 6. The main open defects are two false positives and missed cruelty, which recur across replays.

The system is ready for research demonstration on one machine. It is not ready for production: it has no authentication and has not been studied with real couples.

# **Testing Strategy & Results**

## **Approach**

The tests are split into suites that run separately.

The unit suite (350 Python tests) checks decisions in isolation, such as request validation, batch boundaries, error translation, and worker orchestration. It never opens a database, file, network connection, or worker thread. The JavaScript suite (38 tests) covers the capture page's client code.

The integration suite (182 tests) runs the code against SQLite, HTTP, the worker, and restarts. The decision-model provider is replaced by a mock HTTP transport, so its errors, timeouts, and malformed responses are tested without network calls.

End-to-end testing used the running server. Film scenes and control dialogue were replayed through the HTTP API and scored against written predictions. A stress input measured capacity.

The following were not tested:

* More than one server process.
* A real provider outage or a server process killed during a model call. Integration tests simulate both with the mock provider and a restart on the same database file.
* Use by real couples.
* Accessibility of the capture page.

## **Strategy**

I wrote most of the tests with an AI coding assistant. Integration tests are slow to write and maintain, so projects usually keep them to the main workflows and leave near full coverage to unit tests. With AI writing the tests, an extra integration test costs little, so I also covered failure paths against real dependencies, such as rejected hosts and restarts.

The risk with AI-written tests is that they pass without testing anything, or confirm the wrong behavior. Every test has to be reviewed. To keep review fast, tests must avoid [mystery guests](https://thoughtbot.com/blog/mystery-guest). Each test spells out its own scenario data, and fixtures only create and clean up things like a temporary database. I need to be able to check a test by reading one function and matching its inputs to its assertions.

## **Coverage**

Coverage is measured with coverage.py through pytest-cov, with branch measurement on. CI requires 95% from the unit suite alone, starting from empty coverage data, so integration tests cannot help meet it. The integration suite then adds to a separate combined report.

| Suite | Statements | Missed | Branches | Partial | Coverage |
| :---- | :---- | :---- | :---- | :---- | :---- |
| Unit only | 2,216 | 33 | 226 | 0 | 98.40% |
| Unit and integration | 2,216 | 0 | 226 | 0 | 100% |

## **Results**

| Suite | Tests | Passed | Failed | Time |
| :---- | :---- | :---- | :---- | :---- |
| Unit (Python) | 350 | 350 | 0 | About 4 s |
| Unit (JavaScript) | 38 | 38 | 0 | Not recorded |
| Integration | 182 | 182 | 0 | About 11 s |
| Total | 570 | 570 | 0 | |

## **Scenario acceptance testing**

I did not test with people. The system measures undesired behavior in a person's speech, and running it on participants would require ethics review.

Instead, I wrote down the expected outcome for each scenario and replayed it through the HTTP API at its original pacing. [`scripts/cases/predictions.md`](../scripts/cases/predictions.md) has the predictions, per-case results, and scoring rules.

**Film scenes.** Twelve scenes, three replays each.

| Result | Outcome |
| :---- | :---- |
| Intervention result across replays | Unchanged for all 12 cases |
| Cases matched in every replay | 10 of 12 |
| Cases 3–12, decision model | 8 of 10 |
| Cases 3–12, query-based rules | 6 of 10 |
| False positives | Cases 6 and 11, in every replay |

Intervention counts varied between replays, most in case 1 (4, 5, 3), case 11 (4, 2, 2), and case 5 (24, 24, 22). Some expected behaviors appeared in only some replays, such as stonewalling in case 10 (2 of 3) and cruelty in case 8 (1 of 3).

**Control dialogue.** AI-written conversations with a planted topic pattern: 8 for discovery and 6 held out. Each held-out conversation was replayed three times with discovered evidence and three times without.

| Criterion | Outcome |
| :---- | :---- |
| First intervention earlier in conversations 01 and 02 | Earlier in 01 (turn 16 against turns 18, 20, 20). Unchanged in 02 (turn 12) |
| Conversations 03–06 unchanged | Held |
| Behavior scores do not differ | Held: mean difference 0.0057 between conditions, 0.0055 within |
| Whether to intervene | Matched the prediction in all 36 runs |

# **Bug Report & Resolution**

| Severity scale | |
| :---- | :---- |
| **Sev** | **Meaning** |
| **P0** | The system cannot run, or stored records are corrupted. No workaround. |
| **P1** | The core workflow gives a wrong result in normal use. |
| **P2** | Work or results are lost or wrong under a failure, but workarounds exist. |
| **P3** | Low impact: rare, cosmetic, or not reachable with the current code. |

| Open defects | | |
| :---- | :---- | :---- |
| **Sev** | **Problem** | **Evidence** |
| **P1** | The model intervenes when the target is being harmed, which the definition of undesired behavior does not cover. | Case 6, every replay: interventions at "Troy, you're hurting me!" and "Troy." with no behavior at 0.5 or above. |
| **P1** | The model reads a confrontational but caring monologue as an attack. | Case 11, every replay: contempt and criticism up to 0.93. |
| **P1** | Threats and cruelty often score below the threshold, even though the prompt asks about them. | Never found in cases 5 and 9. Found in 1 of 3 replays of case 8. |
| **P3** | Above about 2.1 assessments per second, decision time keeps growing. Nothing limits the load. | 20 simultaneous conversations gave a median of 23.27 s, and 30 gave 51.02 s. One conversation is well within capacity. |
| **P3** | Discovery can require topics unrelated to the planted pattern, so a calm conversation can receive evidence. | The model required five generic topics beyond the two planted ones. `control-test-05` received evidence in 1 of 3 runs and stayed silent. |

## **Limitations by design**

These come from recorded decisions. They are not defects, but they affect results. [Known limitations](known_issues.md) lists the rest.

* A target's turn closes when the next speaker's speech arrives, so decision time includes that speech. A conversation's last batch waits 20 s.
* Decisions use the first speaker labels, so labeling errors stay in decisions ([ADR 011](adrs/011-decisions-use-first-speaker-labels.md)).
* Evidence goes only to the action question and requires every topic in the model ([ADR 016](adrs/016-declare-discovery-and-pattern-evidence.md)).
* The worker is one sequential loop in one server process ([ADR 014](adrs/014-polling-worker.md)).

# **Quality Metrics**

| Code quality | | |
| :---- | :---- | :---- |
| **Check** | **Tool** | **Result** |
| Lint | Ruff | No issues |
| Formatting | Ruff format | 250 files already formatted |
| Types | mypy, strict mode | No issues in 107 source files |
| Dependency audit | pip-audit, PyPI and OSV | No known vulnerabilities in 83 pinned packages |
| Cyclomatic complexity | Ruff (McCabe) | No function above 11. Eight exceed 5: `capture_audio` (11), `forward_audio` (11), `record_transcripts` (8), `body_limit` (7), `limited` (6), `events` (6), `batch_end` (6), `run_worker` (6) |
| Size | | 4,962 lines of Python, excluding migrations |

Pre-commit runs the formatter, lint, type, and lockfile checks before each commit. On every push and pull request, GitHub Actions audits the locked dependencies, runs the pre-commit checks and JavaScript tests, enforces unit coverage, runs the integration suite, and uploads both coverage reports.

## **Performance**

[Quality Attribute Evaluation](quality_attribute_evaluation.md) has the method and full results.

| Seconds, end of speech to stored decision, mid-conversation | n | p50 | p95 | Max |
| :---- | :---- | :---- | :---- | :---- |
| Film replays | 348 | 3.37 | 11.82 | 21.52 |
| Live capture | 15 | 8.35 | 15.01 | 15.01 |

One worker handles about 2.1 assessments per second. It kept up with 10 simultaneous conversations but not 20. Under that load, the server used at most 17% of one core and 237 MB of memory.

## **Security**

The server has no authentication or per-case access control and should listen only on localhost. Audio goes to the transcription provider, and transcripts go to the decision-model provider. The system has these protections:

* Requests must name an allowed host (`ALLOWED_HOSTS`, localhost by default), and a browser's origin must match it.
* Request bodies are limited to 128 KiB. Live capture is limited in length and in simultaneous connections.
* Pydantic validates request bodies and path parameters. Unknown fields are rejected, and identifiers are limited to 128 characters from `A–Z a–z 0–9 . _ : -`.
* Logs record exception types but not exception messages, which can contain SQL parameters or transcripts.

## **Accessibility**

The capture page has not been audited. The rest of the system is an HTTP API, and FastAPI generates its OpenAPI page at `/docs`.

# **System Readiness Assessment**

## **Production readiness**

The system cannot be deployed to production. It runs reliably as a single local process for research use. A production deployment would need:

1. Authentication, authorization, and TLS.
2. Encrypted storage, a retention limit, and a way to delete speech.
3. A decision on scaling. SQLite and one sequential worker limit the system to one process and about 2.1 assessments per second.
4. An ethics review before the system processes the speech of real people.

| Risks and mitigations | |
| :---- | :---- |
| **Risk** | **Mitigation** |
| False interventions undermine the demonstration. | Report cases 6 and 11 as known failures. Both recur in every replay and have identified causes. |
| Answers vary between runs. | Replay each case at least three times and report the variation. |
| Provider response times or outages change results. | Failed calls retry on the next poll, and requests the provider rejects are skipped. Report measured times with their limits. |
