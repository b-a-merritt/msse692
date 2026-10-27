# Known limitations

- Inference failures retry on later polls without a persisted attempt limit or backoff. Interrupted calls may be repeated after restart.
- One synchronous worker handles all cases. Slow inference delays other cases; the batch duration limits speech time, not request bytes. While a batch is open, each poll reloads the case's speech.
- Actions are saved recommendations. Intervention creation, grouping, and external notifications are not implemented.
- Decisions use the speaker labels speech arrived with. Revisions are stored but never reassessed, and they do not remap targets.
- A short acknowledgement from another speaker ends the target's turn and its batch.
- Speaker labels identify speakers only within a session. Microphone processing and attribution errors can affect results.
- Model scores and the 0.7 selection threshold are not calibrated accuracy claims. Automated tests do not establish real-provider accuracy or human benefit.
- There is no authentication, pagination, or retention policy. Storage grows with observations, revisions, and decisions.
- The schema is disposable; use fresh database paths. Multiple server processes sharing a database are unsupported.
