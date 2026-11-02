# Case Manifest

| Case file | Film | Scene | YouTube title | Source URL |
|---|---|---|---|---|
| `cases/case-1.jsonl` | Revolutionary Road (2008) | "I Love My Children, Frank" (clip 4/8) | Revolutionary Road (4/8) Movie CLIP - I Love My Children, Frank (2008) HD | https://www.youtube.com/watch?v=m_7Bm1gyq2c |
| `cases/case-2.jsonl` | Marriage Story (2019) | Argument between Nicole (Scarlett Johansson) and Charlie (Adam Driver) | Scarlett Johansson and Adam Driver in Marriage Story l Netflix | https://www.youtube.com/watch?v=FDFdroN7d0w&t=2s |
| `cases/case-3.jsonl` | The Social Network (2010) | Opening bar breakup between Erica (Rooney Mara, `speaker-1`) and Mark (Jesse Eisenberg, `speaker-2`) | The Social Network (2010) - You're Breaking Up With Me? Scene (1/10) \| Movieclips | https://www.youtube.com/watch?v=VlSkPA60ujQ |
| `cases/case-4.jsonl` | Before Midnight (2013) | Hotel-room fight between Celine (Julie Delpy, `speaker-1`) and Jesse (Ethan Hawke, `speaker-2`) | Before Midnight 2013 Celine Argument Scene | https://www.youtube.com/watch?v=aaqDa2UJ_kM |
| `cases/case-5.jsonl` | Who's Afraid of Virginia Woolf? (1966) | George plays "Get the Guests" with Martha (Elizabeth Taylor, `speaker-1`), George (Richard Burton, `speaker-2`), Nick (George Segal, `speaker-3`) and Honey (Sandy Dennis, `speaker-4`) | Who's Afraid of Virginia Woolf  George plays "get the guests" | https://www.youtube.com/watch?v=p59MMlPae3U |
| `cases/case-6.jsonl` | Fences (2016) | Rose's "same spot" speech between Troy (Denzel Washington, `speaker-1`) and Rose (Viola Davis, `speaker-2`) | Fences (2016) - The Same Spot As You Scene (5/10) \| Movieclips | https://www.youtube.com/watch?v=2hs-yt-Pmk0 |
| `cases/case-7.jsonl` | Kramer vs. Kramer (1979) | Restaurant custody scene between Joanna (Meryl Streep, `speaker-1`) and Ted (Dustin Hoffman, `speaker-2`) | Kramer vs. Kramer (4/8) Movie CLIP - I Want My Son (1979) HD | https://www.youtube.com/watch?v=M_ejjr2-4WE |
| `cases/case-8.jsonl` | Breaking Bad (S4E6) | "I am the one who knocks" between Skyler (Anna Gunn, `speaker-1`) and Walt (Bryan Cranston, `speaker-2`) | Breaking Bad - I Am the One Who Knocks Scene (S4E6) \| Rotten Tomatoes TV | https://www.youtube.com/watch?v=Ca3kPemW2CE |
| `cases/case-9.jsonl` | Phantom Thread (2017) | Asparagus dinner between Alma (Vicky Krieps, `speaker-1`) and Reynolds (Daniel Day-Lewis, `speaker-2`) | The Asparagus Fight \| Phantom Thread | https://www.youtube.com/watch?v=Q3KBAOoLh0k |
| `cases/case-10.jsonl` | The Break-Up (2006) | Dishes argument between Brooke (Jennifer Aniston, `speaker-1`) and Gary (Vince Vaughn, `speaker-2`) | I Want You to WANT to do the Dishes - The Break-Up \| RomComs | https://www.youtube.com/watch?v=xj7sYdMEKec |
| `cases/case-11.jsonl` | Good Will Hunting (1997) | Park bench scene between Will (Matt Damon, `speaker-1`) and Sean (Robin Williams, `speaker-2`) | [Great Movie Scenes] Good Will Hunting - Park Scene | https://www.youtube.com/watch?v=qM-gZintWDc |
| `cases/case-12.jsonl` | Forrest Gump (1994) | Forrest (Tom Hanks, `speaker-1`) meets his son at Jenny's (Robin Wright, `speaker-2`) apartment, with little Forrest (Haley Joel Osment, `speaker-3`) and Jenny's coworker (`speaker-4`) | Forrest Gump: Named after his dad (HD CLIP) | https://www.youtube.com/watch?v=ITGEGE9v0d0 |

## Replay

Configure the target explicitly:

```bash
uv run python scripts/send_observations.py scripts/cases/case-3.jsonl --target-speaker-id speaker-2
```

Use fresh storage or new case IDs. The decision model assesses topics for all new speech and behaviors for the target. `cases/predictions.md` lists the expected behaviors and interventions. Model scores are not fixed.

## Capture a case file

Capture each clip once, then replay the file. Route system audio to the browser's microphone input with a loopback device rather than speakers, keep playback volume the same for every clip, and select **Stop** after the clip's last line. Read the transcript on the capture page, record the target's label in this manifest, and capture again if the target shares a label with another speaker or is split across two. Export the case with a stable ID:

```bash
uv run python scripts/export_case.py <capture-case-id> scripts/cases/<case-id>.jsonl --as-case-id <case-id>
```

The file holds speech as ingested, in sequence order. Speaker corrections are left out because decisions ignore them.

## Additional inputs

`cases/control/` is AI-written dialogue between one couple, a control test for process discovery: 8 training and 6 held-out conversations, one file each, a week apart. `cases/predictions.md` lists the planted pattern and expected outcomes. Replay the 8 training conversations into one database, then run `uv run discover-model` with the same `APP_DB_PATH`. For each held-out run with evidence, start the server on a copy of that database, so held-out conversations are never discovered from. For each run without evidence, use an empty database:

```bash
uv run python scripts/send_observations.py scripts/cases/control/control-test-01.jsonl --target-speaker-id speaker-2
```

`cases/stress.jsonl` is AI-generated synthetic speech for 330 interleaved cases, increasing the offered rate across six phases. Recorded gaps take approximately 11.5 minutes to replay. HTTP response time adds to that duration. The whole file causes about 4,400 decision-model calls. Phases 1–3, the cases with IDs starting `stress-p1`, `stress-p2`, and `stress-p3`, cause about 800 and exceed the worker's capacity.

| File | Contents |
|---|---|
| `cases/demo-unrepaired.jsonl` | Two interruptions by `speaker-2` |
| `cases/demo-repaired.jsonl` | The interruptions followed by an apology |
| `cases/demo-speaker-control.jsonl` | `speaker-1` says "You are crazy." |
| `cases/demo-target-label.jsonl` | `speaker-2` says "You are crazy." |
| `cases/demo-grouped.jsonl` | Two interruptions, the second loud |

## Evaluate

`evaluate.py` replays any case files and reports on any databases. Run it from the repository root. `run` calls the paid decision model and writes a database, logs, and resource samples for each run to the directory it is given. Use a path under `data/`, which git ignores.

| Command | Reports |
|---|---|
| `run` | Nothing. Replays case files on fresh servers |
| `outcomes` | Interventions and behaviors per case, scored against `cases/expected.json` when given |
| `timing` | Time from the end of speech to a stored decision. Add `--live` for live capture |
| `load` | Arrival rates, throughput, memory, CPU, and logs for one server's database |
| `compare` | Interventions, evidence, and behavior scores between two sets of runs |

`outcomes` counts every database holding a case as one run, so pass only the runs to compare.

Film cases, three replays each:

```bash
uv run python scripts/evaluate.py run data/eval/film scripts/cases/case-*.jsonl --target-speaker-id speaker-2 --replicates 3 --concurrency 6
uv run python scripts/evaluate.py outcomes data/eval/film --expected scripts/cases/expected.json
uv run python scripts/evaluate.py timing data/eval/film
```

Control dialogue, with and without discovered evidence:

```bash
uv run python scripts/evaluate.py run data/eval/train scripts/cases/control/control-train-*.jsonl --target-speaker-id speaker-2 --together
APP_DB_PATH=data/eval/train/run-1.sqlite3 uv run discover-model
uv run python scripts/evaluate.py run data/eval/with scripts/cases/control/control-test-*.jsonl --target-speaker-id speaker-2 --together --replicates 3 --concurrency 6 --seed data/eval/train/run-1.sqlite3
uv run python scripts/evaluate.py run data/eval/without scripts/cases/control/control-test-*.jsonl --target-speaker-id speaker-2 --together --replicates 3 --concurrency 6 --base-port 8300
uv run python scripts/evaluate.py compare --baseline data/eval/without --variant data/eval/with --cases control-test
uv run python scripts/evaluate.py outcomes data/eval/with --cases control-test --expected scripts/cases/expected.json
```

Stress phases 1–3 on one server:

```bash
uv run python scripts/evaluate.py run data/eval/stress scripts/cases/stress.jsonl --target-speaker-id speaker-2 --cases 'stress-p[123]'
uv run python scripts/evaluate.py load data/eval/stress/stress-run-1.sqlite3 --group 'stress-(p\d)'
uv run python scripts/evaluate.py timing data/eval/stress --group 'stress-(p\d)'
```
