# Developer guide

Use the pinned Python and Node versions, `uv sync --locked`, and the [development commands](commands.md). Startup requires a decision-model credential; [deployment](deployment_guide.md) lists settings.

## Assessment flow

```mermaid
flowchart LR
    C[Capture or HTTP ingest] --> D[(SQLite)]
    D --> W[Polling worker]
    W --> M[Decision model]
    M --> W
    W -->|Decisions and progress| D
    D --> A[Assessment API]
```

One worker visits each ready case per pass, then waits 0.1 seconds. A resolved target and new ingested sequences or a changed target revision make a case ready. Calls are synchronous, so inference delays other cases.

`process_case` loads speech and the target in a read transaction. `batch_end` selects up to the configured batch size, extending the boundary to include a revised turn. `build_snapshot` overlays each turn's latest revision and includes recent context. Corrected rows overlapping unhandled originals are new; a merged row may also contain handled speech. If revisions remove all new speech, the worker advances progress without calling the decision model.

Inference runs outside database transactions. On success, decisions and progress commit together. A target change during inference preserves the decision under its original assignment and leaves the new target pending. Failures leave progress unchanged and retry on later polls. There is no persisted attempt budget or interrupted-request recovery.

## Questions and results

The decision-model adapter calls a pinned model version through the provider SDK with a 30-second HTTP timeout and no SDK retries. `services/decision/` contains batching, context, question construction, answer conversion, and prompt wording. The adapter trusts typed SDK responses.

Every new observation gets topic scores and a primary-topic choice. Only target speech gets the seven behavior scores and hostility intensity. When the batch has new target speech, one action question considers the surrounding conversation, including apologies and clarification. Other batches get no action question.

`store_assessment` retains raw answers in relational tables and the request as JSON. `report_observation` selects scores at the assessment's stored threshold (0.7), sorts labels, and reports an unselected primary topic as `unknown`. Actions are recommendations; there is no automatic intervention creation.

## Storage and capture

See the [schema](schema.md). Times are UTC microseconds in storage and aware timestamps in responses. Append-only triggers protect observations, revisions, target assignments, assessments, and classifications.

Ingested observations have a sequence and receipt time. Corrected observations reference a speaker revision; `replaced_observation` links it to the ingested rows it replaces. Classifications reference exact observation keys. Revisions affect later snapshots without changing past decisions, target selection, or polling eligibility.

`target_assignment` records speaker-label changes. Speaking order uses ingested speech; selecting a label clears that order. Assessments reference the assignment they used. Each stored intervention references one `intervene` assessment. Delivery marks it sent once, only while its target revision remains current.

Capture stores each final turn and revision batch before notifying the browser. Finals and corrections share `build_observations`; IDs include session, turn, word span, and label. Storage runs in a thread pool. `LevelMeter` measures 20 ms frames; `PCMBuffer` preserves the provider's minimum packet size. The [API reference](api.md#live-capture-stream) defines the wire protocol.

## Tests

Follow [AGENTS.md](../AGENTS.md): explicit scenario data, isolated unit tests, integration tests for real storage and transport, and at least 95% unit-only branch coverage. Provider doubles test application behavior, not model accuracy. JavaScript tests use browser doubles; check microphone access and Stop separately in a browser.
