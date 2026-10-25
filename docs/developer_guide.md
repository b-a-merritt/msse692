# Developer guide

This guide describes the current implementation.

## 1. Environment and architecture

Install Git and [uv](https://docs.astral.sh/uv/getting-started/installation/), clone the repository, and run from its root:

```bash
uv sync --locked
uv run pre-commit install
uv run fastapi dev src/normative_conformance/main.py
```

`.python-version` pins Python 3.13. `uv.lock` pins dependencies. The development server reloads on changes. Each reload restarts the worker. Use separate storage for experiments, as shown in the [user guide](user_guide.md). Readiness is `GET /health/ready`. The interactive API is `/docs`.

```mermaid
flowchart LR
    C[HTTP client] --> R[Routes and schemas]
    subgraph Process[One application process]
        R --> S[Service operations]
        W[Worker thread] --> S
        W --- T[Deadlines and windows]
    end
    S --> DB[(Application SQLite)]
    S -->|Request work| Q[(Queue SQLite)]
    Q --> W
```

Routes validate input, supply dependencies, and return service results. Services own operations, including transaction boundaries and follow-up work. The scheduler coalesces waiting requests per case. After a task starts, new observations can queue a follow-up. Assessment and repair requests have separate waiting sets. One process owns the worker and its coordination state.

`stage_observation` inserts an observation within a caller-owned write transaction. It does not commit, roll back, or schedule assessment. `ingest` commits the transaction before requesting assessment.

Startup configures logging, migrates storage, validates every stored model, and starts the worker. Model validation checks the schema, rule execution against an empty case, and intervention-message coverage. The worker uses this validated catalog until restart.

## 2. Assessment and intervention flow

```mermaid
sequenceDiagram
    participant C as Client
    participant A as API / services
    participant D as Records
    participant Q as Queue
    participant W as Worker
    C->>A: POST observation
    A->>D: Commit case + observation
    A->>Q: Request case assessment
    A-->>C: 202 + stored observation
    Q->>W: Assessment task
    W->>D: Capture prefix + time, evaluate models, commit
    W->>Q: Request repair check
    Note over W,D: Match may wait for repair deadline
    W->>D: Append repair / resolution
    Note over W,D: New confirmation opens a grouping window
    W->>D: Store intervention when window closes
    C->>A: POST deliver
    A->>D: Mark pending interventions sent and commit
    A-->>C: Sent interventions
```

The sequence shows successful operation. A **202** confirms observation storage and a successful scheduling request, not assessment completion. If queueing fails after commit, **503 ENQUEUE_FAILED** carries `committed_observation`. A duplicate submission does not retry scheduling.

Cases start without a target. The worker skips unresolved cases. Ingestion recomputes order-based selections from speech start/end time and receipt sequence; missing and `PENDING` labels do not count. Manual selections persist until explicitly replaced. Configuring a resolved target schedules existing speech through the current queue.

Each evaluation captures a case sequence and server time. Rules query that prefix. New arrivals belong to later evaluations. A matching undesired model creates `pending` with a deadline or `conformant` immediately when its allowance is null. No match creates no assessment. Reusing a pending match preserves its original deadline.

Repair timeliness uses server receipt time. A qualifying repair must arrive strictly before the deadline and remove the original match at its speech boundary. Resolution appends a linked `non-conformant` or `conformant` assessment. The original remains unchanged. A recognized repair also permits future detection after that boundary.

New undesired confirmations open one grouping window per case. At window close, one message is selected by an ordered policy table, and the intervention links all eligible unlinked confirmations since the window opened. The window batches work. Slow evaluation can include confirmations after its nominal end. The policy currently always authorizes a message.

## 3. Code and stored data

Paths below are relative to `src/normative_conformance/`.

| Location | Responsibility |
|---|---|
| `main.py`, `lifespan.py`, `config.py` | ASGI app, startup/shutdown, environment settings |
| `routes/`, `schemas/` | HTTP boundary and validated public contracts |
| `static/`, `services/capture/` | Microphone PCM streaming, controls, and RMS level measurement |
| `services/case/` | Configure case targets and resolve distinct speaker order |
| `services/observation/` | Store and retrieve observations; stage inserts within caller-owned transactions |
| `services/model/`, `services/assessment/` | Evaluate SQL models and append results |
| `services/scheduler/` | Request coalescing, worker loop, repair and intervention timers |
| `services/intervention/`, `services/health/` | Create/deliver messages. Check readiness |
| `models/`, `database.py`, `queue.py` | SQLModel tables, transactions, persistent task queue |
| `migrations/` | Alembic environment and schema/catalog revisions |
| `logging.py`, `timestamps.py` | Structured diagnostics and UTC/microsecond conversion |

```mermaid
flowchart LR
    C[Case] --> O[Observations]
    C --> A[Assessments]
    M[Model version] --> A
    A -->|resolves_assessment_id| P[Original pending assessment]
    I[Intervention] --> S[Source links]
    S --> A
```

An assessment records its model version and evaluated prefix (`through_sequence`). The API reconstructs that prefix as `extent`. It is the evaluated history, not a minimal set of causal observations. Rule explanations record status and any repair observation IDs. SQLModel tables and database triggers enforce the stored invariants. Times are integer UTC microseconds in storage and timezone-aware timestamps at API boundaries.

## Microphone capture and tests

The page scripts are ES modules under `static/`:

| File | Responsibility |
|---|---|
| `capture.js` | Binds buttons and readouts; the only module that touches the page |
| `capture/session.js` | `CaptureSession` owns the microphone, audio graph, and WebSocket, and releases them once. It reports status keys, not text |
| `capture/status.js` | Fixed page text for each status key |
| `capture/levels.js` | Summarizes one `levels` message |
| `pcm-worklet.js` | Converts audio to 100 ms PCM16 packets |

The capture page uses an [AudioWorklet](https://developer.mozilla.org/en-US/docs/Web/API/AudioWorkletProcessor) in a 16 kHz audio context to emit mono PCM16. The worklet leaves its output silent to avoid microphone playback. It flushes its final packet before sending the stop command. Browser and server buffers are bounded; a browser send backlog above one second stops capture with a gap message.

`LevelMeter` consumes the WebSocket bytes, carries incomplete 20 ms frames between messages, and discards audio after measurement. It has no database or provider dependency. The page displays returned levels and releases the microphone and audio context on stop, failure, or navigation.

Python unit tests cover the math and route orchestration with in-memory inputs and WebSocket doubles. HTTP/WebSocket integration tests cover packaged assets and the wire protocol. JavaScript unit tests use Node's built-in test runner and browser API doubles; they do not establish microphone or browser compatibility. Run them with the Node version pinned in `.nvmrc`:

```bash
nvm use
node --test "tests/unit/static/**/test_*.mjs"
```

For a browser check, open `/capture` on localhost, grant microphone access, speak, stop, and confirm the microphone indicator switches off. Repeat after denying permission and after interrupting the connection. Run the Python checks listed in [Useful commands](commands.md).
