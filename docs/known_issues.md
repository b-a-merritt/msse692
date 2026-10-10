# Known issues and limitations

The [QA report](quality_assurance_report.md) holds the evidence, severity, and triage. This page summarizes it for operators. The system supports one local research process and is not ready for production.

## Open defects

| Severity | Effect | Workaround |
|---|---|---|
| P2 | "You're acting crazy" is not recognized by the label model | None |

## Limitations by design

| Boundary | Consequence |
|---|---|
| Failed operations are not retried | If an operation fails, such as SQLite staying locked past its 5-second timeout, it is marked failed and never retried, even after restart. Late interventions have little value in a time-sensitive conversation |
| Confirmed matches suppressed until repair | A second offense without a repair produces no new intervention |
| Fixed phrase lists and chunk-level measurements | Phrases outside the lists are missed, such as the threat in case 8 |
| Subject fixed at database initialization | Changing the environment variable does not retarget an existing experiment |
| One process with coordination partly in memory | Multiple workers or replicas sharing storage are unsupported |
| No authentication, authorization, or transcript-size limit | Use only a controlled local instance. The requirements accept this risk for the prototype |
| Server receipt time decides whether a repair is on time | Replay or network delay can make a repair arrive after the deadline |

## Planned improvements

Before the final presentation, I plan to fix the open defect: broader recognition of insulting labels. A change to detection needs a new film-case replay and updated acceptance results.

A production deployment would also need authentication and authorization, a request size limit, TLS, a scaling decision, and an ethics review before the system processes the speech of real people.
