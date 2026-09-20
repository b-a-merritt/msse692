# Architecture Document

**Project:** A Human Cyber-Physical System Architecture for Supporting Moral Self-Regulation

**Team:** Individual Track

**Author:** Ben Merritt

**Date:** 2026-09-12

**Status:** Draft

**Design-review amendment (2026-09-19):**
[The accepted review decisions](detailed_design.md#review-decisions) supersede the
earlier sliding-window, active abstention, four-produced-status, and delivery
failure descriptions below. It also removes baseline comparison and records the
full-case, positive-uniqueness, shared-repair, and consume-on-retrieval decisions.
The numerical performance qualification below is superseded by the current
prototype scope. Detailed interface contracts are maintained in the
[detailed design](detailed_design.md); the remaining
architecture prose and diagrams will be reconciled as those sections are completed.

# **Executive Summary**

The HiTLCPS prototype assesses simulated conversational observations against predefined normative models of undesirable behaviors. It begins research into a Human-in-the-Loop Cyber-Physical Systems (HiTLCPS) prototype that uses normative conformance checking to assess human behavior and intervene to correct habits. It comprises three stages: collecting mocked (for now) observations, evaluating conformance, and implementing interventions.

Observations persist in append-only event logs. The normative assessment is query-based, using SQL queries to determine whether these observations conform to prescribed, undesired activities. These assessments trigger when observations are ingested or when repair deadlines expire. Each assessment retains references to its normative model version and observations. An intervention policy considers only `conformant` results, meaning only a match with an undesirable pattern can authorize intervention. Even so, the intervention policy can be extended later to refrain from submitting.

The quality priorities are auditability, reliability, performance, and reproducibility. The design trades storage growth and repeated query work for traceable results. After restart, each case resumes assessment only when its next valid observation arrives.

Live sensing, adaptive models, and external delivery are outside scope. Evaluation can establish behavior under authored scenarios, but cannot establish intent, ethical wrongdoing, normative legitimacy, or human benefit.

# **Architectural Drivers**

The [MSSE692 Requirements Document](https://docs.google.com/document/d/1nvjwRWJQUfeS_D0TPtyShmFQfOBoSX4G_XCIbEQzXlw/edit?tab=t.0#heading=h.8s6vi5ue2d9r)defines four mandatory quality scenarios.&nbsp;

| Requirements |  |  |
| :---- | :---- | :---- |
| **Identifier** | **Scenario** | **Architectural priority** |
| QA-01 | Performance | Third |
| QA-02 | Reliability and restart recovery | Second |
| QA-03 | Auditability and structural explainability | First |
| QA-04 | Reproducibility | Supporting |

## **Auditability and Structural Explainability**

**Scenario:** For each completed result, including those that stop at intermediate stages, stdout logging and the event log itself must explain every decision and identify its references.

An evaluator must distinguish inputs, model results, and policy decisions. They should be able to do so from either the logs or the database. In the database, immutable model versions, rule identifiers, captured case prefixes, and source references make results traceable. Diagnostic logs connect explanations to those records (Discussed in ADR 001, 005, and 007).

## **Reliability and Restart Recovery**

**Scenario:** After stopping at different pipeline stages, restart must reload the model and recover 100% of committed records with zero duplicates, without creating missing later-stage records.

Lost evidence, duplicates, or changed models would undermine experiment reconstruction. SQLite transactions therefore commit each assessment or intervention with its provenance fields, and foreign keys enforce references. Startup validates the supplied model versions before readiness (See ADR 007).

## **Performance**

**Scenario:** After model initialization and validation, run 100 assessments of a case containing 1,000 observations. Every result must include its status and explanation fields without error, with p95 assessment latency at most 250 ms.

Execution overhead must be distinguishable from the model's intentional repair allowance.&nbsp;

## **Reproducibility**

The evaluator must reproduce expected statuses and explanation elements when repeated with locked dependencies, a fresh database, a fixed normative model, and the same ingested observations.

# **Architecture Overview**

## **Architectural Style**

The architecture is a modular monolith: one server application with separate ingestion, scheduling, assessment, and intervention components. This separation makes decisions traceable. A shared database provides transaction boundaries. A background worker handles case-specific assessment outside request handling.

| Components |  |
| :---- | :---- |
| **Component** | **Responsibility** |
| HTTP API | Validate incoming observations Expose stored records, namely interventions |
| Ingestion service | Append validated observations to the event log, preserving fields and insertion order without assigning social meaning |
| Model loader | Seed supplied versions without duplication or replacement Validate definitions before readiness |
| Scheduler | Enqueue case tasks in `persistqueue` after observation commits and at model deadlines; combine waiting requests using in-memory case coordination |
| Assessment service | Run each supplied normative model's full set of declarative queries Derive activities and store the status, explanation, and exact evaluated observation references |
| Intervention service | Evaluate conformant assessments and record authorization or abstention, policy identity, reason, and source assessment references |

Domain records and ready assessment tasks are persisted in SQLite; `persistqueue` owns queue delivery and acknowledgment state. The scheduler keeps future deadlines and queued-case membership in memory. On restart, old messages are drained without evaluation, and cases resume on new observations. Diagnostic logging writes decisions, record references, and rule references to stdout and a file.

## **Integration and Communication**

The researcher submits mocked observations and retrieves results through HTTP/JSON. Internal components communicate through service-level function calls, with SQL access to the local database and a SQLite-backed `persistqueue` queue for assessment work.

Each assessment describes the selected case history, with exactly one status

| Status | Meaning for the undesirable-pattern model |
| :---- | :---- |
| `conformant` | The history matches the pattern. |
| `non-conformant` | The history definitely does not match the pattern. |
| `pending` | The result depends on a future observation or an unexpired deadline. |
| `conflicted` | Applicable checks give unresolved, incompatible results. |

The processing sequence is:

1. The API rejects invalid or unsupported input before persistence or assessment.
2. Ingestion commits a valid observation, then enqueues assessment work for its case in `persistqueue`. The API acknowledges acceptance after enqueuing without waiting for assessment to complete.
3. The worker detects new patterns within the event log and checks unresolved repairs using retained evidence. It commits each assessment with its case, captured sequence cutoff, and model/version reference. If it assesses a case to be pending, it enqueues another assessment.
4. Only a `conformant` assessment reaches the intervention policy. In a separate transaction, the policy commits an intervention with a unique source assessment ID and null sent timestamp. All stored interventions are authorized.
5. Delivery sets `sent_at_us` on all selected pending interventions before returning the HTTP response. Response status is derived from that timestamp; the decision and source reference remain unchanged.

| Note that intervention pending means delivery is authorized and awaiting completion, while assessment pending means conformance is unresolved. Repair deadlines and relevant window expirations can also trigger assessment without an HTTP submission. Evaluation errors are operational failures, separate from conformance statuses. A later-stage failure leaves earlier commits intact. |
| :---- |

&nbsp;

Observation persistence and queue insertion are separate commits. If enqueueing fails, the observation remains committed, and the failure is logged. A crash between these commits can leave an observation without queued assessment work.

## **Deployment and Restart**

Run one FastAPI process that contains the scheduler and one background assessment worker. SQLite runs within that process and stores records in a local file ([SQLite architecture](https://www.sqlite.org/serverless.html)). Mock clients and evaluation commands run on the same machine.&nbsp;

On restart, the server revalidates models and makes committed records retrievable. Startup neither replays missed triggers nor creates missing downstream records. Persisted queue entries remain inactive until their case resumes. A case's next committed valid observation resumes its assessment and timers. Unresolved repair checks keep their original evidence and deadlines, so missed checks may resolve late. A case with no subsequent observation remains inactive.

Fixtures supply case identifiers. Automatic case creation after ten minutes without vocal activity is deferred.

# **Architecture Views**

The views follow C4's [system context](https://c4model.com/diagrams/system-context), [container](https://c4model.com/diagrams/container), and [component](https://c4model.com/diagrams/component) scopes.

## **Level 1: System Context**

The researcher operates the mock HTTP client outside the server boundary. Conversation participants appear only in fixtures. Live sensing, audio processing, and external notifications are excluded.

![][image1]

## **Level 2: Containers**

The server is the prototype's only application container. The database and event log are data stores. The researcher can view and review logs in stdout and the log file.

![][image2]

## **Level 3: Server Components**

![][image3]

## **Assessment Flow**

Observation, assessment, and intervention records are committed before the next stage begins. Abstention stops interventions before delivery.

## **Shared Components**

The model loader seeds and validates versions before the server reports health readiness. Validation failure stops startup. It supplies validated definitions to the assessment worker. All components log outcomes and failures.

| Consumer | Persistence use |
| :---- | :---- |
| HTTP API | Retrieve records and model identity |
| Observation ingestion | Commit observations |
| Assessment scheduler | Persist assessment work through `persistqueue`; read retained case and pending-check state when a case resumes |
| Assessment worker | Read evaluated observations, commit assessments with captured case prefixes |
| Intervention policy | Commit interventions with a unique source assessment reference |
| Local delivery adapter | Update delivery status |

# **Quality Attribute Achievement Strategy**

## **Performance**

**Target**&nbsp;
Complete 100 assessments of a case containing 1,000 observations without errors, returning the status and all explanation fields. The p95 assessment latency must be at most 250 ms.

**Tactics**

| Tactic | Purpose |
| :---- | :---- |
| Limit assessment scope | Evaluate the affected case's sliding window, plus evidence needed by pending repair checks. |
| Index query access paths | Index case/time filters and source-reference lookups based on actual predicates and query plans. |
| Separate request handling from assessment | Queue SQL work for the background worker. |
| Load and validate normative models at startup | Validate models before assessment begins. |

Index effectiveness depends on predicates and data distribution ([SQLite query planning](https://www.sqlite.org/queryplanner.html)). Background execution separates ingestion from assessment.

6. &nbsp;

| Note that while the system should eventually enable the user to change the normative models, that is out of scope. When that functionality is added, create an invalidation strategy to handle model changes while assessments are in progress. |
| :---- |

**Verification**

1. Initialize the database, validate models, and load 1,000 observations. Record model versions, parameters, timestamp distribution, and expected assessed extent.
2. Schedule 100 immediate assessments sequentially, using distinct request identities so all execute. Hold observations and logical evaluation time fixed. Retain assessment writes between requests.
3. Measure real elapsed time from scheduling submission until the harness receives the persisted status and complete explanation. Include queueing, SQL, persistence, and retrieval. Exclude startup, fixture loading, and intentional waiting for a repair deadline. Pending results can have the same latency target.
4. Validate results. The nearest-rank p95—the 95th value in ascending order—must be at most 250 ms. Any failed request fails the scenario.

Record hardware, software versions, database settings, and background workload. This benchmark does not establish concurrent-ingestion capacity, sustained throughput, or a bound on unresolved repair history.

## **Reliability and Recovery**

**Target**
After stopping and restarting the server, recover 100% of committed records with zero duplicates. Reload the supplied models without creating missing downstream records during startup.

**Tactics**

| Tactic | Purpose |
| :---- | :---- |
| Atomic persistence | Commit each assessment or intervention with its provenance fields in one transaction. |
| Reference and uniqueness checks | Enforce model/version foreign keys, case sequence references, and unique intervention sources. |
| Idempotent initialization | Seed models without duplicating or replacing definitions. Validate before readiness. |
| Controlled restart | Restore committed records and resume cases. |

Transactions preserve earlier commits when later stages fail. Use [SQLite transactions](https://www.sqlite.org/atomiccommit.html), and enable and check [foreign-key enforcement](https://www.sqlite.org/foreignkeys.html) on every connection.

**Verification**
Run controlled failures and restarts at these boundaries

| Stop point | Required result |
| :---- | :---- |
| Observation committed, but queue insertion not committed | Observation remains, and startup creates no assessment |
| Assessment work queued, but assessment not started | Observation and queued work remain; startup creates no assessment, and queued work waits for the case to resume |
| Assessment or intervention interrupted before commit | No partial record remains. Earlier commits are unchanged |
| Assessment committed, but policy not evaluated | Assessment and its captured prefix remain. Startup creates no intervention |
| Intervention committed as `pending` with delivery not attempted | Decision and source assessment reference remain, and startup does not deliver it |
| Local delivery fails | A pre-commit failure leaves the intervention pending; response loss after commit leaves it sent |

This covers controlled local restart or power-loss scenarios. Database loss and disk corruption recovery are outside the scope.

## **Auditability and Structural Explainability**

**Target**
For each completed result, stdout and the database records must explain every decision and identify its references, including traces that stop before the final stage.

**Tactics**

| Tactic | Purpose |
| :---- | :---- |
| Assessment provenance | Store model identity, version, evaluation time, rule identifiers, reasons, and the case and sequence cutoff identifying the exact evaluated prefix |
| Policy provenance | Store policy identity, reason, decision time, and source assessment ID |
| Correlated diagnostics | Log readable outcomes and references to stdout and the event log, including rejected input and operational failures |

These references let an evaluator trace delivery through the policy decision and assessments to the model definitions and observations. Explanations of absent repairs identify the evaluated history and deadline.

**Verification**
Independently write expectations covering all four assessment statuses: authorization, abstention, pending delivery, delivery failure, and success. Include invalid input, retained observations matching no activity, and SQL failure. Inspect both logging outputs for reasons and references at each executed stage.

## **Reproducibility**

**Target**
From a clean checkout, locked dependencies, and a fresh database, an evaluator must reproduce every expected assessment status and required explanation using consistent commands and mocks.

**Tactics**

| Tactic | Purpose |
| :---- | :---- |
| Fixed inputs | Model definitions, parameters, and expected results |
| Controlled logical time | Supply observation and evaluation times |
| Locked environment | Lock dependencies and document Python, SQLite, and operating-system versions |
| Independent expectations | Author expected statuses and evidence sets from model conditions, independently of the SQL under test |

**Verification**
Supply commands for initialization and the expected results. Run them in two fresh databases in the reference environment. Compare statuses, models, evaluated extents, rule reasons, and observation membership.

# **Technology Selection Rationale**

## **Language and HTTP Server Framework**

**Python** version 3.13.

**FastAPI and Pydantic** provide [request-body validation and API schemas](https://fastapi.tiangolo.com/tutorial/body/), making the observation contract inspectable.

## **Database and Query Execution**

**SQLite and SQL** for persistence and transactions. SQLite needs no separate database service, but allows only one writer at a time, meaning that ingestion and assessment can contend with each other ([SQLite use cases](https://www.sqlite.org/whentouse.html)). Short transactions, suitable indexes, and benchmarking will mitigate this.

[**SQLModel**](https://sqlmodel.tiangolo.com/) supplies typed table definitions and Object Relation Mapping (ORM) using Pydantic.

## **Integration and Deployment**

**HTTP/JSON** lets mock clients submit observations and retrieve records.

**Service calls and [`persistqueue`](https://github.com/peter-wangxu/persist-queue)** keep deployment local, with the queue's SQLite backend retaining queued work across restarts. Assessment work is enqueued only after the triggering observation commits. The scheduler manages repair-deadline and window-expiration timers and duplicate prevention. The queue stores work for the background worker. Timers must work without incoming requests.

**Local deployment** avoids service administration but leaves one process and one machine as single points of failure. Run performance and recovery evaluations without development auto-reload.

# **Architectural Constraints and Assumptions**

&nbsp;

| Constraints |  |
| :---- | :---- |
| **Constraint** | **Architectural consequence** |
| Local mocked inputs | Fixtures supply case and speaker identifiers. Sensing, source-media processing, external delivery, and production deployment are excluded |
| Fixed models | Seed and validate supplied versions at startup. There is no runtime editing, personalization, or feedback adaptation |
| Append-only evidence | Preserve committed observations and earlier assessments. Delivery updates preserve decision evidence |

&nbsp;

| Assumptions |  |
| :---- | :---- |
| **Assumption** | **Consequence** |
| Fixtures have consistent case, speaker, and timestamp references | Assessment may link unrelated behavior or repairs. |
| Fixtures actually exercise the declared model conditions | Missing cases may conceal errors. Independently review expectations and counterexamples. |
| The researcher controls the host and uses synthetic data | Real data or untrusted access requires security and privacy assessment. |
| Database and model files remain free of external edits during operation | Startup validation cannot catch a later edit. |
| The same database remains available after restart | Deleted, replaced, or damaged files fall outside recovery guarantees. Retain database paths and experiment artifacts. |
| Workloads stay within the evaluated range | Larger histories, more models, and concurrent ingestion require further measurement. |

## **Security Scope**

The requirements exclude application security. Authentication, authorization, TLS, multi-user isolation, and secrets management are out of scope. Remote deployment, use of personal data, or multiple users requires threat analysis, revised requirements, and an architecture review.

&nbsp;

| Risks and Mitigations |  |
| :---- | :---- |
| **Risk** | **Mitigation Strategy** |
| SQL evaluation or write contention exceeds the latency target | Measure queueing, SQL, and persistence separately. Optimize query plans and indexes against unchanged expectations before adding processes or services. |
| Timestamp ambiguity changes repair or window outcomes | Resolve Section 5.5's time rules; test equal timestamps and before/at/after boundaries with controlled time. |
| Multiple triggers duplicate work or interventions | Define work identity and policy handling for repeated matches. Test overlapping windows and simultaneous triggers. |
| Restart leaves checks or delivery inactive | Test stage-boundary recovery and document the next-observation resume rule. Cases without later observations stay inactive. |
| A crash leaves commits without diagnostic entries | Preserve relational provenance; test interrupted stages. SQLite and log writes are not atomic together. |
| Observations and historical results grow without bound | Bound evaluation runs and archive completed databases. Retain active-case evidence beyond window expiration; long-term retention remains future work. |
| Passing traces is mistaken for ethical accuracy | Use independent expectations and the rules-engine baseline; report technical outcomes separately from claims of normative legitimacy or human benefit. |
| Documents or tests use superseded assumptions | Trace tests to current ADRs and Section 2.5, especially observation persistence and intervention records. |
