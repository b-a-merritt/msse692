# Design Document

Last updated: Sep 20, 2026

# **Team: *Individual Track***

* Ben Merritt

&nbsp;

[API Specifications](#api-specifications)

[Endpoint Inventory](#endpoint-inventory)

[Submitting observations](#submitting-observations)

[Queue message](#queue-message)

[Data Model and Schema](#data-model-and-schema)

[Entities](#entities)

[Tables and constraints](#tables-and-constraints)

[Indexes and queries](#indexes-and-queries)

[Transaction boundaries and migrations](#transaction-boundaries-and-migrations)

[Technology Stack](?tab=t.0#heading=h.170ckyvqo7s9)

[Component Internal Design](#component-internal-design)

[Structure and interfaces](#structure-and-interfaces)

[Assessment and declarative models](#assessment-and-declarative-models)

[Scheduling and worker](#scheduling-and-worker)

[Quality Attribute Design](#quality-attribute-design)

[Performance](#performance)

[Reliability](#reliability)

[Auditability and logging](#auditability-and-logging)

[Implementation Guidance](#implementation-guidance)

[Coding and review](#coding-and-review)

[Another subtitle](?tab=t.0#heading=h.4u539z3ylijg)

[Example table](?tab=t.0#heading=h.7jbe203g7c7g)

[Checklist](?tab=t.0#heading=h.jltys38rhgql)

&nbsp;

#

This document defines a prototype that applies query-based normative conformance checking against simulated conversation observations to detect and interrupt undesirable behavior. In this prototype, a **positive** result (`conformant`) means the observations match an undesirable pattern. The **subject** is the speaker being assessed. An **activation** starts a model's repair period, and a **repair** is a qualifying phrase received during that period. An assessment's **extent** (or **case prefix**) is all observations committed for that case through the captured sequence number.

# **API Specifications** {#api-specifications}

One process runs at `http://127.0.0.1:8000`. Product endpoints use `/api/v1`. Health endpoints are unversioned. Requests and responses use JSON. No authentication, authorization, TLS, or rate limiting is implemented for this local prototype.

A UUID request ID is generated for each response to be used for logging and tracing requests. API timestamps require a timezone and are returned in UTC, for example `2026-09-20T12:00:00.000000Z`. Database timestamps use integer Unix microseconds, identified by `_us`. Unknown request fields and query parameters are rejected. Responses generated UUID in `X-Request-ID`. Every application error uses `ErrorEnvelope`:

| {   "error": {    "code": "VALIDATION\_ERROR",    "message": "The observation fields are invalid.",    "request\_id": "ea65e629-082b-4c8b-a6c2-bd387878e7af",    "details": \[      {         "location": "/end\_at",          "message": "Must exceed start\_at."       }     \],    "committed\_observation": null  }} |
| :---- |

The following status codes are used.

| HTTP | Stable&nbsp; | Meaning |
| :---- | :---- | :---- |
| 400 | `INVALID_JSON` | Malformed JSON |
| 404 | `NOT_FOUND` | Named resource or route does not exist |
| 405 | `METHOD_NOT_ALLOWED` | Unsupported method |
| 409 | `OBSERVATION_EXISTS` | Observation identity already committed |
| 415 | `UNSUPPORTED_MEDIA_TYPE` | Observation submission is not JSON |
| 422 | `VALIDATION_ERROR` | Invalid type, bounds, chunk fields, extra field, or parameter |
| 503 | `NOT_READY` | A required runtime component is unavailable |
| 503 | `STORAGE_UNAVAILABLE` | Database operation could not complete |
| 503 | `ENQUEUE_FAILED` | Observation committed, but the separate scheduling operation failed |
| 500 | `INTERNAL_ERROR` | Unexpected application failure |

&nbsp;

| Endpoint Inventory Paths below are relative to /api/v1 except the two health paths. |  |  |
| :---- | :---- | :---- |
| **Method and path** | **Input** | **Status and Response** |
| `POST /observations` | `ObservationInput` | 202 `ObservationAccepted`&nbsp; |
| `GET/cases/{case_id}/observations` | Case ID | 200 `ObservationRecordList` |
| `GET/cases/{case_id}/observations/{observation_id}` | Case and observation IDs | 200 `ObservationRecord` |
| `GET /models` | None | 200 `ModelList` |
| `GET /models/{model_version_id}` | Model-version ID | 200 `ModelVersion` |
| `GET /cases/{case_id}/assessments` | Case ID | 200 `AssessmentList` |
| `GET /assessments/{assessment_id}` | Assessment ID | 200 `Assessment` |
| `GET /interventions` | `case_id`, `status` | 200`InterventionList` |
| `POST /interventions/deliver` | None | 200 `DeliveryResult` |
| `GET /health/live` | None | 200 `Liveness` (HTTP process is responsive) |
| `GET /health/ready` | None | 200 `Readiness` (models validated, database/queue usable, scheduler/worker running) |
| `POST /observations` | `ObservationInput` | 202 `ObservationAccepted`&nbsp; |

Every list has the shape `{"items": [...]}` and returns all matching records.

## **Submitting observations** {#submitting-observations}

`POST /api/v1/observations` submits one speaker's measured speech chunk. The provider aims for a target duration, adjusts boundaries to sentences or long pauses, and trims leading and trailing silence. Small internal pauses can remain. Chunking and measurement are mocked because this project does not process audio.

| Field | Required content | Notes |
| :---- | :---- | :---- |
| `case_id`, `observation_id`, `speaker_id` | Case, observation, and speaker identifiers | `SUBJECT_SPEAKER_ID` identifies the assessed speaker |
| `start_at`, `end_at` | Provider UTC speech boundaries; nonempty half-open interval `[start_at, end_at)` |  |
| `transcript` | Transcript with 1–4,000 characters |  |
| `signal_level_min`, `signal_level_avg`, `signal_level_max` | Finite dBFS summaries in \[−120, 0\], with min ≤ avg ≤ max | The same per-speaker frame-level measurements where `avg` is the arithmetic mean of the dBFS levels&nbsp; |

Assessment runs asynchronously and may combine requests. The 202 status response does not promise one assessment per observation or completion. Only the stored representation includes receipt time and sequence. A duplicate `(case_id, observation_id)` returns **409**, regardless of content. It creates no observation or work request and leaves the original receipt time unchanged.

It is required that `start_at < end_at`, transcript is nonblank, and signal levels satisfy `-120 ≤ min ≤ avg ≤ max ≤ 0`. Levels use dBFS. The average is the arithmetic mean of the chunk's frame-level dBFS measurements. Fixtures use comparable measurement and gain conventions. Numbers must be JSON numbers, not numeric strings or booleans. Store the original transcript unchanged.

Source intervals measure duration and overlap. They may arrive out of order. The server assigns `received_at` and a per-case `sequence` when committing each observation. Receipt time controls repair deadlines. Sequence records insertion order. Clients cannot supply either field or advance the server clock.

`ObservationRecord` contains all input fields plus:

| sequence: positive integerreceived\_at: timestamp |
| :---- |

`ObservationAccepted` is:

| observation: ObservationRecordassessment\_requested: true |
| :---- |

## **Queue message** {#queue-message}

The queue contains ready-to-run case references:

| {  "kind": "assess\_case",  "evaluation\_id": "d4e9cfa0-bf7b-4fdf-a84d-d95641577bd7",  "case\_id": "case-1"} |
| :---- |

All three fields are required. Extras are rejected. The evaluation UUID is generated when enqueuing. The worker captures observations and evaluation time when processing begins. Queue receipt and acknowledgment state belong to persist-queue, not the message or an application work table.

# **Data Model and Schema** {#data-model-and-schema}

## **Entities** {#entities}

## **![][image1]**

&nbsp;

| Note that the queue has it’s own SQLite database as part of the persist-queue package. |
| :---- |

The configuration is a singleton for the whole database. It fixes the assessed speaker without repeating an experiment ID on every case. Observation sequence is unique within its case. An assessment's `(case_id, last_observation_sequence)` references that case's last included observation.

## **Tables and constraints** {#tables-and-constraints}

The tables use SQLite `STRICT`. Unless marked nullable, every column is `NOT NULL`. `INTEGER` timestamps are nonnegative UTC microseconds suffixed with `_us`.&nbsp;

| Table | Columns |
| :---- | :---- |
| `experiment_config` | `experiment_id INTEGER PK``subject_speaker_id TEXT``created_at_us INTEGER` |
| `case_log` | `case_id TEXT PK``created_at_us INTEGER` |
| `observation` | `case_id TEXT PK``observation_id TEXT PK``sequence INTEGER``received_at_us INTEGER``speaker_id TEXT``start_at_us INTEGER``end_at_us INTEGER``transcript TEXT``signal_level_min REAL``signal_level_avg REAL``signal_level_max REAL` |
| `normative_model_version` | `model_id TEXT PK``version TEXT PK``name TEXT``orientation TEXT``rules_json TEXT``parameters_json TEXT` |
| `assessment` | `assessment_id INTEGER PK``evaluation_id TEXT``case_id TEXT``model_id TEXT``model_version TEXT``evaluated_at_us INTEGER``last_observation_sequence INTEGER``status TEXT``explanation_json TEXT``next_due_at_us INTEGER nullable` |
| `intervention` | `intervention_id INTEGER PK``assessment_id INTEGER``message TEXT``created_at_us INTEGER``sent_at_us INTEGER nullable` |

### Constraints

1. **Observations:** `(case_id, observation_id)` is the primary key and link `case_id` to `case_log`. Require a unique `(case_id, sequence)`, positive sequence, nonempty IDs and transcript, and `end_at_us > start_at_us`.&nbsp;
2. **Models:** Use `(model_id, version)` as the primary key and require both fields to be nonempty. Set orientation to `undesirable_pattern`. Rules must be a nonempty JSON array and parameters a JSON object.&nbsp;
3. **Assessments:** foreign keys to the case, `(model_id, model_version)` to the model key, and `(case_id, last_observation_sequence)` to observation sequence. Unique `(evaluation_id, model_id, model_version)`. Status uses the four defined values.&nbsp;
4. **Interventions:** unique `assessment_id` with a foreign key to assessment. An insert trigger requires a conformant source.&nbsp;

## **Indexes and queries** {#indexes-and-queries}

Every model query begins with the same case history:

| WITH history AS (    SELECT \* FROM observation    WHERE case\_id \= :case\_id      AND sequence \<= :last\_observation\_sequence)\-- Derive this model's conditions from history. |
| :---- |

Historical extent retrieval uses the same predicate and `ORDER BY sequence`. The model's time rules are additional SQL conditions, never a server-imposed history window. Use bound parameters for values supplied to queries.

## **Transaction boundaries and migrations** {#transaction-boundaries-and-migrations}

The database will use `foreign_keys=ON`, WAL, `synchronous=FULL`, and `busy_timeout=5000`. It will use the writer lock with `BEGIN IMMEDIATE` before allocating sequence numbers or selecting interventions for delivery.&nbsp;

Intervention creation follows the assessment commit and cannot roll that back. For a repeated positive, it will usea targeted `ON CONFLICT ... WHERE status = 'conformant' DO NOTHING`, then retrieve the existing assessment. Do not hide other constraint failures.

| Technology Stack |  |  |
| :---- | :---- | :---- |
| **Technology** | **Why it was chosen** | **Tradeoffs** |
| FastAPI and Uvicorn | Provide HTTP routing, generated API documentation, dependency injection, and the server process. | Blocking database and queue work must stay off the async event loop. |
| Pydantic and pydantic-settings | Validate request data and load typed configuration from environment variables or `.env`. | Relationships between fields, such as signal-level ordering, still need application checks. |
| SQLite | Stores records and executes conformance queries without a separate database service. Transactions and foreign keys protect related records. | Only one writer can run at a time, so write transactions must be short. |
| SQLModel | Maps tables to typed Python records and handles ordinary database access. | Conformance queries, triggers, and some constraints still need SQL. |
| Numbered SQL migrations | Keep schema changes visible and easy to review for this small database. | The project must maintain and test the migration sequence. |
| persist-queue | Provides a local persistent queue with acknowledgments, so ingestion can return before assessment finishes. | The application must schedule deadlines and combine duplicate requests. Queue and application writes commit separately. |
| Ruff and mypy | Apply consistent formatting and catch common code and type errors before execution. | Runtime behavior still needs tests. |
| pre-commit and GitHub Actions | Run checks locally and on pushes and pull requests. | CI must run the same tests and checks used during development. |

# **Component Internal Design** {#component-internal-design}

## **Structure and interfaces** {#structure-and-interfaces}

The system will use module-level functions for observation, model, assessment, scheduler, and intervention services. Pydantic models and dataclasses will carry values, and SQLModel classes will map tables.&nbsp;

![][image2]

## **Assessment and declarative models** {#assessment-and-declarative-models}

The assessment component captures one case history and evaluation time, runs each fixed model, and stores its result. Queries determine conformance. Python binds values and formats the returned evidence.

![][image3]

&nbsp;

| Model ID | Activation condition |
| :---- | :---- |
| `unrepaired_interruption` | A subject overlap louder than both of that speaker's preceding two chunks, followed by two more distinct subject overlaps |
| `unrepaired_high_intensity_address` | One subject chunk has average level above −18 dBFS, derived rate above 180 words/minute, and a configured address phrase |
| `unrepaired_extended_turn` | A subject speaking turn exceeds 30 seconds |

An activation is a complete match for a model's pattern. SQL will derive it from observations without storing another event. The models will follow these rules:

* **Order and overlap:** Source order is `(start_at_us, end_at_us, sequence)`. An interruption candidate starts strictly inside another speaker's interval and overlaps it by at least 300 ms (configurable in the future from the parameters below). Simultaneous starts do not qualify. The subject's entry must start after all earlier subject chunks have ended, so splitting continuous speech cannot manufacture interruptions. If several context chunks qualify, the query will choose the latest start, then earliest end and sequence. It will count the subject entry once.
* **Repeated interruption:** The first candidate must be strictly louder than both preceding subject chunks. Missing either prevents activation. Its next two qualifying candidates complete the pattern, without another loudness condition. Intervening non-overlaps are allowed. No extra history window applies.
* **Text and rate:** SQL will lowercase ASCII and replace tab, LF, CR, double quote, parentheses, comma, hyphen, period, colon, semicolon, question mark, and exclamation mark with spaces. It will collapse spaces and match complete phrases at token boundaries. The rate calculation will count space-separated tokens and use `60 × count / chunk_duration_seconds`. Address phrases are `you are wrong` and `you are ridiculous`. Each occurrence is considered separately. Signal and rate must strictly exceed their thresholds.
* **Extended turn:** The query will combine subject chunks while gaps are at most one second and no other speaker starts in the gap. It will measure elapsed time from the first chunk's start. The first chunk crossing 30 seconds activates the model once for that turn. Continuations do not restart its deadline.
* **Repair:** The query will match `i am sorry` or `i apologize` from the subject in the same case. The allowance starts at the latest server receipt time of the activation's supporting observations. A later repair must have a greater sequence than all supporting observations and arrive before the deadline. One exactly at the deadline is too late. A repair may satisfy all applicable earlier activations. It cannot prevent later activations.
* **Same-chunk repair:** For an address phrase, repair must follow that phrase in normalized text. For interruption and extended turn, a repair anywhere in the completing chunk counts. Chunk measurements cannot tell us when each word was spoken.

The query will choose the earliest permitted repair by sequence, then phrase position. An incomplete interruption sequence has no completed activation or deadline yet. Matches from different models do not count as a conflict.

Models will use the parameter names and defaults below. Validation will require positive durations, nonnegative turn gap and level rise, finite signal/rate thresholds, and nonempty unique normalized phrase lists. It will reject missing or unknown parameters.

| Parameters | Used by |
| :---- | :---- |
| `repair_allowance_us: 10000000`, `repair_terms: ["i am sorry", "i apologize"]` | All models |
| `address_terms: ["you are wrong", "you are ridiculous"]` | Shared phrase query, with address matches used by intensity |
| `overlap_min_us: 300000`, `level_rise_db: 0` | Interruption |
| `volume_threshold_dbfs: -18`, `rate_threshold_wpm: 180` | Intensity |
| `duration_threshold_us: 30000000`, `turn_gap_us: 1000000` | Extended turn |

At startup, the model service will seed absent models, compare existing definitions directly, validate parameters and unique rule IDs, and compile the read-only queries against the migrated schema. It will check their expected result columns and bindings. Invalid or changed content under the same identity will stop startup. Model definitions will remain fixed during the run. SQL failures will be reported as operational errors, with no assessment stored for the failed query.

## **Scheduling and worker** {#scheduling-and-worker}

`SchedulerState` has a lock, `deadlines: dict[case_id, datetime]`, and `queued_cases: set[case_id]`. Only ready tasks enter the queue. A pending assessment updates the case's earliest deadline. The scheduler enqueues it when due.

Under the scheduling lock, an observation request either reuses a waiting task or inserts one. The scheduler will clear the future deadline only after acceptance. The worker removes the case from `queued_cases` before capturing history. Observations arriving during evaluation can then request another task. When evaluation finishes, the scheduler will leave any waiting task in place. If none is waiting, it will keep the earliest pending deadline from successful models. A scheduled check and an apology can share one waiting task. Observations arriving after capture still get another evaluation.

Snapshot capture will read server time and the latest case sequence under a short database writer lock, then release it and read the immutable history. Every model in that task will use those same values. Model evaluation will run without holding the scheduling lock.

![][image4]

The worker will continue other models after one fails and keep any committed IDs. It will use the queue's success or failure acknowledgment without automatic retries. Acknowledgment failure will stop the worker and fail readiness. If the scheduler cannot enqueue a task, it will keep its deadline, report the error, and stop dispatch until restart. An ingestion enqueue failure will return the committed observation reference.

Startup will open the queue with recovery of unacknowledged messages enabled, then drain and acknowledge all old work before starting producers. The scheduler will start with empty state. Only a new committed observation resumes a case. SQL derives any remaining or expired deadlines from its retained history. Startup and repeated positives do not fill gaps left by failed downstream writes.

# **Quality Attribute Design** {#quality-attribute-design}

## **Performance** {#performance}

The worker will evaluate models outside request handling. The scheduler will combine waiting requests per case. Startup will load validated model definitions once. The system will not cache mutable assessment results or impose an observation limit. Query work and response size will grow with the case history, which is acceptable for the prototype.&nbsp;

## **Reliability** {#reliability}

Every committed record will remain unchanged after restart. Recovery tests will use a real temporary SQLite database and queue to cover these failures:

| Parameters | Used by |
| :---- | :---- |
| Before observation commit | No partial case or observation |
| After observation commit, before enqueue | The observation will remain stored. Startup will create no assessment |
| Queued or in-progress task at restart | Startup will drain the old task without evaluating it |
| Before assessment/intervention commit | The transaction will roll back that write and keep prior commits |
| After assessment commit, before intervention | The assessment will remain stored without the missing intervention being created |
| Before delivery commit | Interventions remain unsent |
| Response lost after delivery commit | Interventions remain sent and are excluded from the next delivery |

## **Auditability and logging** {#auditability-and-logging}

An intervention leads to its assessment, model version, explanation, and exact case history. Historical results do not change when new observations arrive. Logs will record receipt/rejection, queue acceptance/failure, assessment outcome, rule reasons, intervention creation, delivery, and startup/shutdown failures. Entries will include relevant case, observation, evaluation, assessment, and intervention IDs. HTTP failures will also include the request ID. Diagnostic logs will not contain whole transcripts.

The system will write the same diagnostics to stdout and a log file in the configured directory:

data/logs/20260920T120000123456Z.log

The filename starts with the application's UTC start time and ends in `.log`. `LOG_DIR` sets the directory. The database keeps the observations, assessments, and interventions separately from these diagnostic logs.

# **Implementation Guidance** {#implementation-guidance}

## **Coding and review** {#coding-and-review}

Code will use typed functions, snake\_case names, one import per line, Ruff's formating, and strict mypy type checking. Stored microseconds will use `_us`, and API and service records will use timezone-aware datetimes. Validation will enforce the field relationships defined in this design. New limits or configuration will need a use within the prototype.

Implementation will proceed in this order:

1. Storage work will update the fields, schemas, and migrations, then complete immutable model loading. Tests will cover initialization and reopening (FR-01–03).
2. Observation and assessment work will add reads, writes, and SQL evaluation. Tests will verify model cases, assessment history, and explanations (FR-04–11, as revised).
3. Scheduling work will add worker and scheduler loops with the real queue, deduplication, timers, and next-observation restart behavior (QA-02, FR-16).
4. Intervention work will add creation, audit retrieval, and delivery that marks records sent when retrieved (FR-12–15, as revised).
5. Final work will complete logs and readiness. HTTP, recovery, and repeatability tests will run, and packaging checks will verify that migrations are included (QA-02–04).
