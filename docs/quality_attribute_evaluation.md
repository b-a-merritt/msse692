# Quality Attribute Evaluation

## Result

The prototype passes the first quality attribute of performance. We stated that the "p95 assessment time [should be] at most 250 ms across the 100 requests." We measured the performance of the application across all boundaries. After stress testing, the worst case for assessing the observations was 337 ms (237 ms for evaluation + 100 ms for how late it was scheduled). That is 3.4% of the shortest repair allowance (10 s). We met the quality attribute, because, despite the worst case being over, the p95 was under 150 ms under load.

## Method

Both runs used one machine: WSL2 Linux with 12 cores, Python 3.13.15, and SQLite 3.53.1. Each run used one assessment worker. All timings come from the structured log timestamps, so they include the cost of logging.

**Measurements**

| Metric | Definition |
|---|---|
| Observation → evaluation | `observation.committed` to its `evaluation.committed` |
| Queue wait | `scheduling.queued` to `task.started` |
| Deadline lateness | `repairs.deadline_due` time minus the scheduled `due_at_us` |
| Intervention lateness | `intervention.created` time minus window open minus the 2 s window |
| Worker busy | Total task time divided by the phase's elapsed time |

## Results

### Baseline (12 real cases)

| Metric | p50 | p95 | Max |
|---|---|---|---|
| Observation → evaluation | 16.5 ms | 32.0 ms | 67.8 ms |
| Assessment queue wait | 2.1 ms | 4.6 ms | 47.1 ms |
| Assessment task | 12.1 ms | 23.9 ms | 36.5 ms |
| Repair check task | 15.2 ms | 32.2 ms | 52.5 ms |
| Deadline lateness (n=25) | 46.0 ms | 95.9 ms | 99.5 ms |
| Intervention lateness (n=26) | 46.2 ms | 87.8 ms | 113.9 ms |

Observations arrived a median of 3.1 s apart. The worker was idle more than 99% of the time.

### Stress (9,966 observations, about 14 minutes)

All 9,966 observations were committed and evaluated. All 13,282 tasks that started also completed. The log contains no warnings or errors, thus meaning we also met the Reliability attribute goals (which was, "100% of committed records are recovered with zero duplicates").

| Phase | Offered | Achieved | Worker busy | Obs → eval p50 / p95 / max | Queue wait p95 | Most tasks queued | Deadline lateness max | Intervention lateness max |ses lets each step be measured on its own. Sessions rotate through ten scenarios: calm conversat
|---|---|---|---|---|---|---|---|---|
| p1 | 3.7/s | 3.5/s | 5% | 13.9 / 19.8 / 48 ms | 3.6 ms | 2 | 84 ms | 39 ms |
| p2 | 7.2/s | 6.6/s | 9% | 13.7 / 21.3 / 45 ms | 3.6 ms | 2 | 99 ms | 77 ms |
| p3 | 10.6/s | 9.4/s | 13% | 14.2 / 25.8 / 69 ms | 4.6 ms | 2 | 100 ms | 53 ms |
| p4 | 20.9/s | 16.5/s | 23% | 15.0 / 30.6 / 72 ms | 15.8 ms | 3 | 95 ms | 32 ms |
| p5 | 31.6/s | 22.2/s | 32% | 15.4 / 35.2 / 90 ms | 18.5 ms | 5 | 67 ms | 57 ms |
| p6 | 40.9/s | 25.5/s | 40% | 16.7 / 48.6 / 237 ms | 28.3 ms | 6 | 96 ms | 30 ms |

The median latency barely moved, from 13.9 to 16.7 ms. The tail grew with load. The slowest phase-6 evaluations spent 90–150 ms between saving the observation and queuing its task, not in the worker.

## Limitations

- Stress sessions are short, about 30 observations each. Assessment time grows with case length: in the baseline, the median assessment rose from 9.8 ms over sequences 1–20 to 26.2 ms over sequences 81–100. Stress results do not cover long cases under load.
- Results come from one machine and one run per input.
- The testing did not find the system's limits, but rather that it met the quality attributes.
