# Known limitations

- Inference failures retry on later polls without a persisted attempt limit or backoff. Interrupted calls may be repeated after restart.
- One synchronous worker handles all cases. Slow inference delays other cases; batch size does not cap transcript length or request bytes.
- Actions are saved recommendations. Intervention creation, grouping, and external notifications are not implemented.
- Revisions do not remap targets or reconsider completed decisions. A corrected run spanning handled and unhandled speech is classified as a whole.
- Speaker labels identify speakers only within a session. Microphone processing and attribution errors can affect results.
- Model scores and the 0.7 selection threshold are not calibrated accuracy claims. Automated tests do not establish real-provider accuracy or human benefit.
- There is no authentication, pagination, or retention policy. Storage grows with observations, revisions, and decisions.
- The schema is disposable; use fresh database paths. Multiple server processes sharing a database are unsupported.
