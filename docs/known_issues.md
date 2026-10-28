# Known limitations

- Failed inference retries on every poll without a limit or backoff. Only requests the provider rejects (400 or 422) are skipped, leaving a gap in assessed sequences. Interrupted calls may be repeated after restart.
- One synchronous worker handles all cases. Slow inference delays other cases; the batch duration limits speech time, not request bytes. While a batch is open, each 1-second poll reloads the case's speech.
- Interventions are not grouped, and delivery sends no external notification; a client must call the delivery endpoint.
- Decisions use the speaker labels speech arrived with. Revisions are stored but never reassessed, and they do not remap targets.
- A short acknowledgement from another speaker ends the target's turn and its batch.
- A dropped transcription stream ends capture; speech until the next Start is lost, and that Start creates a new case.
- Speaker labels identify speakers only within a session. Microphone processing and attribution errors can affect results.
- Model scores and the 0.7 selection threshold are not calibrated accuracy claims. Automated tests do not establish real-provider accuracy or human benefit.
- There is no authentication, pagination, or retention policy. Storage grows with observations, revisions, and decisions.
- The schema is disposable; use fresh database paths. Multiple server processes sharing a database are unsupported.
