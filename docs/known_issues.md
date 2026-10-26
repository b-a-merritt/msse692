# Known issues and limitations

The [QA report](quality_assurance_report.md) holds the evidence, severity, and triage. This page summarizes it for operators. The system supports one local research process and is not ready for production.

## Open defects

No open defects are listed.

## Limitations by design

| Boundary | Consequence |
|---|---|
| Case processing retries on each poll | A failed transaction leaves progress unchanged, so a persistent error repeats until corrected |
| Intervention grouping windows are held in memory | Shutdown discards open windows. Failed intervention creation consumes its window and is not retried |
| Confirmed matches suppressed until repair | A second offense without a repair produces no new intervention |
| Fixed phrase lists and chunk-level measurements | Phrases outside the lists are missed, such as the threat in case 8 |
| Target selection is scoped to each case | Speaking order and manual labels select a target within a case; they do not identify a person across sessions |
| One process with coordination partly in memory | Multiple workers or replicas sharing storage are unsupported |
| No authentication, authorization, or transcript-size limit | Use only a controlled local instance. The requirements accept this risk for the prototype |
| Server receipt time decides whether a repair is on time | Replay or network delay can make a repair arrive after the deadline |
