#!/usr/bin/env python3
"""Replay case files on fresh servers and report what the stored records show."""

import argparse
import json
import math
import os
import re
import shutil
import sqlite3
import statistics
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from collections import defaultdict
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from itertools import combinations
from itertools import pairwise
from pathlib import Path

SEND_OBSERVATIONS = Path(__file__).with_name("send_observations.py")
SAMPLE_SECONDS = 2
POLL_SECONDS = 2
STARTUP_ATTEMPTS = 120
PAGE_SIZE = os.sysconf("SC_PAGE_SIZE")
CLOCK_TICKS = os.sysconf("SC_CLK_TCK")


@dataclass(frozen=True)
class _Job:
    name: str
    files: tuple[Path, ...]
    port: int


def _natural(value: object) -> list[int | str]:
    """Sort key that places case-2 before case-10."""
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", str(value))]


def _databases(paths: Iterable[Path]) -> list[Path]:
    """Expand directories to their databases, keeping the order given."""
    found: list[Path] = []
    for path in paths:
        found.extend(sorted(path.glob("*.sqlite3"), key=_natural) if path.is_dir() else [path])
    return found


def _connect(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)


def _selected(case_id: str, pattern: str | None) -> bool:
    return pattern is None or re.search(pattern, case_id) is not None


def _group(case_id: str, pattern: str | None) -> str:
    match = re.search(pattern, case_id) if pattern else None
    if match is None:
        return "all"
    return match.group(1) if match.groups() else match.group(0)


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)]


def _spread(values: list[float]) -> str:
    return (
        f"p50={_percentile(values, 0.5):7.2f} p95={_percentile(values, 0.95):7.2f}"
        f" max={max(values):7.2f}"
    )


def _resources(pid: int) -> tuple[float, float]:
    fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    cpu_seconds = (int(fields[11]) + int(fields[12])) / CLOCK_TICKS
    rss_mb = int(Path(f"/proc/{pid}/statm").read_text().split()[1]) * PAGE_SIZE / 1e6
    return cpu_seconds, rss_mb


def _sample(pid: int, path: Path, stopped: threading.Event) -> None:
    with path.open("w") as output:
        while not stopped.is_set():
            try:
                cpu_seconds, rss_mb = _resources(pid)
            except (FileNotFoundError, ProcessLookupError):
                return
            row = {"at": time.time(), "cpu_seconds": cpu_seconds, "rss_mb": rss_mb}
            output.write(json.dumps(row) + "\n")
            output.flush()
            stopped.wait(SAMPLE_SECONDS)


def _observation_counts(files: Iterable[Path]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for path in files:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                counts[json.loads(line)["case_id"]] += 1
    return dict(counts)


def _all_handled(db: Path, expected: dict[str, int]) -> bool:
    connection = _connect(db)
    try:
        handled = dict(
            connection.execute("select case_id, last_handled_sequence from conversation_case")
        )
    finally:
        connection.close()
    return all(handled.get(case_id) == count for case_id, count in expected.items())


def _wait_for_server(url: str, server: subprocess.Popen[bytes]) -> None:
    for _ in range(STARTUP_ATTEMPTS):
        if server.poll() is not None:
            raise RuntimeError("server exited during startup")
        try:
            urllib.request.urlopen(url + "/docs", timeout=2).close()
            return
        except (urllib.error.URLError, ConnectionError):
            time.sleep(0.5)
    raise RuntimeError("server did not start")


def _replay(job: _Job, args: argparse.Namespace) -> None:
    db = args.output / f"{job.name}.sqlite3"
    if db.exists():
        raise RuntimeError(f"{db} already exists")
    if args.seed:
        shutil.copyfile(args.seed, db)
    env = {**os.environ, "APP_DB_PATH": str(db), "LOG_DIR": str(args.output / f"{job.name}.logs")}
    url = f"http://127.0.0.1:{job.port}"
    expected = _observation_counts(job.files)
    stopped = threading.Event()
    with (args.output / f"{job.name}.out").open("w") as output:
        server = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "normative_conformance.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(job.port),
            ],
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
        )
        sampler = threading.Thread(
            target=_sample,
            args=(server.pid, args.output / f"{job.name}.samples.jsonl", stopped),
        )
        try:
            _wait_for_server(url, server)
            sampler.start()
            senders = [
                subprocess.Popen(
                    [
                        sys.executable,
                        str(SEND_OBSERVATIONS),
                        str(path),
                        "--target-speaker-id",
                        args.target_speaker_id,
                        "--base-url",
                        url,
                    ],
                    env=env,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                )
                for path in job.files
            ]
            exit_codes = [sender.wait() for sender in senders]
            if any(exit_codes):
                raise RuntimeError("a replay failed")
            deadline = time.monotonic() + args.timeout
            while not _all_handled(db, expected):
                if time.monotonic() > deadline:
                    raise RuntimeError("cases were not handled in time")
                time.sleep(POLL_SECONDS)
        finally:
            stopped.set()
            if sampler.is_alive():
                sampler.join()
            server.terminate()
            server.wait(timeout=60)
    print(f"{job.name}: done", flush=True)


def _select_rows(path: Path, pattern: str | None, output: Path) -> Path:
    """Return a case file holding only the selected cases."""
    if pattern is None:
        return path
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    rows = [
        line for line in lines if line.strip() and _selected(json.loads(line)["case_id"], pattern)
    ]
    if not rows:
        raise SystemExit(f"{path} has no cases matching {pattern}")
    selected = output / f"{path.stem}-selected.jsonl"
    selected.write_text("".join(rows), encoding="utf-8")
    return selected


def _run(args: argparse.Namespace) -> None:
    """Replay case files, each replicate on its own server and fresh database."""
    args.output.mkdir(parents=True, exist_ok=True)
    files = [_select_rows(path, args.cases, args.output) for path in args.case_files]
    named = (
        [(f"run-{replicate}", tuple(files)) for replicate in range(1, args.replicates + 1)]
        if args.together
        else [
            (f"{original.stem}-run-{replicate}", (path,))
            for replicate in range(1, args.replicates + 1)
            for original, path in zip(args.case_files, files, strict=True)
        ]
    )
    jobs = [
        _Job(name=name, files=job_files, port=args.base_port + index)
        for index, (name, job_files) in enumerate(named)
    ]

    def attempt(job: _Job) -> str | None:
        try:
            _replay(job, args)
        except Exception as error:
            return f"{job.name}: {error}"
        return None

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        failures = [failure for failure in pool.map(attempt, jobs) if failure]
    if failures:
        raise SystemExit("\n".join(failures))


def _case_outcome(connection: sqlite3.Connection, case_id: str) -> dict:
    interventions = [
        row[0]
        for row in connection.execute(
            "select a.through_sequence from intervention i join assessment a using (assessment_id)"
            " where a.case_id = ? order by 1",
            (case_id,),
        )
    ]
    behaviors = {
        row[0]
        for row in connection.execute(
            "select distinct s.behavior from classification_behavior_score s"
            " join classification c using (classification_id)"
            " join assessment a using (assessment_id)"
            " where a.case_id = ? and s.score >= a.selection_threshold",
            (case_id,),
        )
    }
    return {"interventions": interventions, "behaviors": behaviors}


def _result(prediction: str, interventions: list[int]) -> str:
    if prediction == "either":
        return "Match"
    if prediction == "yes":
        return "Match" if interventions else "Missed"
    return "False positive" if interventions else "Match"


def _counted(behaviors: Iterable[str], presence: Counter[str]) -> str:
    return ", ".join(f"{behavior} {presence[behavior]}" for behavior in sorted(behaviors)) or "-"


def _outcomes(args: argparse.Namespace) -> None:
    """Report interventions and behaviors per case, scored when expected outcomes are given."""
    expected = json.loads(args.expected.read_text(encoding="utf-8")) if args.expected else {}
    runs: dict[str, list[dict]] = defaultdict(list)
    for path in _databases(args.databases):
        connection = _connect(path)
        cases = [row[0] for row in connection.execute("select distinct case_id from assessment")]
        for case_id in cases:
            if _selected(case_id, args.cases):
                runs[case_id].append(_case_outcome(connection, case_id))
        connection.close()

    print("case | interventions | first | predicted | result | behaviors | unexpected")
    results: dict[str, list[str]] = {}
    for case_id in sorted(runs, key=_natural):
        outcomes = runs[case_id]
        presence = Counter(behavior for outcome in outcomes for behavior in outcome["behaviors"])
        prediction = expected.get(case_id, {})
        predicted = prediction.get("intervene")
        known = prediction.get("behaviors")
        results[case_id] = (
            [_result(predicted, outcome["interventions"]) for outcome in outcomes]
            if predicted
            else []
        )
        counts = Counter(results[case_id])
        print(
            f"{case_id}"
            f" | {', '.join(str(len(outcome['interventions'])) for outcome in outcomes)}"
            f" | {', '.join(str(outcome['interventions'][0]) if outcome['interventions'] else '-' for outcome in outcomes)}"  # noqa: E501
            f" | {predicted or '-'}"
            f" | {', '.join(f'{name} {count}' for name, count in counts.items()) or '-'}"
            f" | {_counted(presence if known is None else known, presence)}"
            f" | {_counted([] if known is None else set(presence) - set(known), presence)}"
        )

    stable = sum(
        len({bool(outcome["interventions"]) for outcome in outcomes}) == 1
        for outcomes in runs.values()
    )
    print(
        f"\nwhether a case had an intervention was unchanged across runs: {stable} of {len(runs)}"
    )
    scored = {case_id: found for case_id, found in results.items() if found}
    for run in range(max((len(found) for found in scored.values()), default=0)):
        cases = [found[run] for found in scored.values() if len(found) > run]
        print(f"run {run + 1}: {cases.count('Match')} of {len(cases)} matched")


def _decision_rows(path: Path, args: argparse.Namespace) -> list[dict]:
    connection = _connect(path)
    speech: dict[tuple[str, int], tuple[float, float]] = {}
    last: dict[str, int] = {}
    # Speaker corrections are stored with no arrival time, and decisions ignore them.
    for case_id, sequence, received, end in connection.execute(
        "select case_id, sequence, received_at_us, end_at_us from observation"
        " where received_at_us is not null"
    ):
        speech[(case_id, sequence)] = (received / 1e6, end / 1e6)
        last[case_id] = max(last.get(case_id, 0), sequence)
    rows = []
    for case_id, through, action, evaluated, completed in connection.execute(
        "select case_id, through_sequence, action, evaluated_at_us, completed_at_us from assessment"
    ):
        if action is None or not _selected(case_id, args.cases):
            continue
        received, end = speech[(case_id, through)]
        following = speech.get((case_id, through + 1))
        closed_at = received + args.idle_seconds
        if following:
            closed_at = min(following[0], closed_at)
        rows.append(
            {
                "group": _group(case_id, args.group),
                "ending": through == last[case_id],
                "transcription": received - end,
                "wait_to_close": closed_at - received,
                "poll": max(0.0, evaluated / 1e6 - closed_at),
                "model_and_store": (completed - evaluated) / 1e6,
                "total": completed / 1e6 - (end if args.live else received),
            }
        )
    connection.close()
    return rows


def _timing(args: argparse.Namespace) -> None:
    """Report the time from the end of speech to a stored decision."""
    rows = [row for path in _databases(args.databases) for row in _decision_rows(path, args)]
    parts = ["wait_to_close", "poll", "model_and_store", "total"]
    if args.live:
        parts.insert(0, "transcription")
    for group in sorted({row["group"] for row in rows}, key=_natural):
        for name, ending in (("mid-conversation", False), ("conversation end", True)):
            selected = [row for row in rows if row["group"] == group and row["ending"] == ending]
            print(f"\n{group}, {name} (n={len(selected)})")
            if selected:
                for part in parts:
                    print(f"  {part:16} {_spread([row[part] for row in selected])}")


def _report_arrivals(rows: list[tuple[str, float, float]], args: argparse.Namespace) -> None:
    arrivals: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for case_id, received, end in rows:
        arrivals[_group(case_id, args.group)].append((received, end))
    start = min(received for _, received, _ in rows)
    for group in sorted(arrivals, key=_natural):
        received = [row[0] for row in arrivals[group]]
        recorded = [row[1] for row in arrivals[group]]
        cases = {case_id for case_id, _, _ in rows if _group(case_id, args.group) == group}
        print(
            f"{group}: cases={len(cases)} observations={len(received)}"
            f" offered={len(recorded) / (max(recorded) - min(recorded)):.1f}/s"
            f" received={len(received) / (max(received) - min(received)):.1f}/s"
            f" window=+{min(received) - start:.0f}..+{max(received) - start:.0f} s"
        )


def _report_resources(db: Path) -> None:
    path = db.with_suffix(".samples.jsonl")
    if not path.exists():
        return
    samples = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    samples = [sample for sample in samples if "rss_mb" in sample]
    rss = [sample["rss_mb"] for sample in samples]
    cpu = [
        (b["cpu_seconds"] - a["cpu_seconds"]) / (b["at"] - a["at"]) * 100
        for a, b in pairwise(samples)
    ]
    print("\n## Server process")
    print(f"memory MB: start {rss[0]:.0f}, peak {max(rss):.0f}, end {rss[-1]:.0f}")
    print(
        f"CPU % of one core: p50 {_percentile(cpu, 0.5):.0f},"
        f" p95 {_percentile(cpu, 0.95):.0f}, max {max(cpu):.0f}"
    )


def _report_logs(db: Path) -> None:
    logs = db.with_suffix(".logs")
    if not logs.is_dir():
        return
    events: Counter[str] = Counter()
    statuses: Counter[int] = Counter()
    durations: list[float] = []
    for path in logs.glob("*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            events[record.get("event")] += 1
            if record.get("level") not in ("INFO", None):
                events[f"level:{record['level']}"] += 1
            if record.get("event") == "http.request":
                statuses[record.get("status_code", record.get("status"))] += 1
                if record.get("duration_ms") is not None:
                    durations.append(record["duration_ms"])
    print("\n## Logs")
    print(f"events {dict(events)}")
    print(f"http statuses {dict(statuses)}")
    if durations:
        print(f"http ms {_spread(durations)}")


def _load(args: argparse.Namespace) -> None:
    """Report arrival rates, throughput, and resource use for one server's database."""
    connection = _connect(args.database)
    assessments = [
        row
        for row in connection.execute(
            "select case_id, through_sequence, evaluated_at_us / 1e6, completed_at_us / 1e6"
            " from assessment"
        )
        if _selected(row[0], args.cases)
    ]
    observations = [
        row
        for row in connection.execute(
            "select case_id, received_at_us / 1e6, end_at_us / 1e6 from observation"
            " where received_at_us is not null"
        )
        if _selected(row[0], args.cases)
    ]
    connection.close()

    calls = [completed - evaluated for _, _, evaluated, completed in assessments]
    first = min(row[2] for row in assessments)
    end = max(row[3] for row in assessments)
    start = min(row[1] for row in observations)
    repeated = sum(count > 1 for count in Counter((row[0], row[1]) for row in assessments).values())
    print("## Totals")
    print(f"observations {len(observations)}, assessments {len(assessments)}")
    print(f"batches assessed twice {repeated}")
    print(f"database MB {args.database.stat().st_size / 1e6:.1f}")
    print(f"throughput first to last assessment {len(assessments) / (end - first):.2f}/s")
    print(f"model call and store {_spread(calls)}")
    print(f"worker busy {sum(calls) / (end - first) * 100:.0f}%")

    print("\n## Arrivals")
    _report_arrivals(observations, args)

    print("\n## Assessments stored per second, by minute")
    minutes = Counter(int((row[3] - start) // 60) for row in assessments)
    for minute, count in sorted(minutes.items()):
        print(f"  +{minute * 60:>4} s: {count / 60:.2f}/s")

    _report_resources(args.database)
    _report_logs(args.database)


def _batches(path: Path, pattern: str | None) -> dict[str, dict[int, dict]]:
    connection = _connect(path)
    intervened = {row[0] for row in connection.execute("select assessment_id from intervention")}
    probabilities = dict(
        connection.execute(
            "select assessment_id, probability from assessment_action_probability"
            " where action = 'intervene'"
        )
    )
    batches: dict[str, dict[int, dict]] = defaultdict(dict)
    for assessment_id, case_id, through, request in connection.execute(
        "select assessment_id, case_id, through_sequence, request_json from assessment"
    ):
        if _selected(case_id, pattern):
            batches[case_id][through] = {
                "intervened": assessment_id in intervened,
                "evidence": json.loads(request).get("evidence") is not None,
                "intervene_probability": probabilities.get(assessment_id),
            }
    connection.close()
    return dict(batches)


def _behavior_scores(path: Path, pattern: str | None) -> dict[tuple[str, int, str], float]:
    connection = _connect(path)
    scores = {
        (case_id, sequence, behavior): score
        for case_id, sequence, behavior, score in connection.execute(
            "select o.case_id, o.sequence, s.behavior, s.score"
            " from classification_behavior_score s"
            " join classification c using (classification_id)"
            " join observation o using (observation_key)"
        )
        if _selected(case_id, pattern)
    }
    connection.close()
    return scores


def _score_differences(pairs: Iterable[tuple[dict, dict]]) -> list[float]:
    return [
        abs(first[key] - second[key])
        for first, second in pairs
        for key in first.keys() & second.keys()
    ]


def _report_batches(case_id: str, sides: dict[str, list[dict]]) -> None:
    print(f"\n{case_id}")
    ends: set[int] = set()
    for name, runs in sides.items():
        for run in runs:
            batches = run.get(case_id, {})
            ends |= batches.keys()
            interventions = [end for end, batch in sorted(batches.items()) if batch["intervened"]]
            evidence = [end for end, batch in sorted(batches.items()) if batch["evidence"]]
            print(f"  {name:8} interventions={interventions} evidence={evidence}")
    for end in sorted(ends):
        cells = []
        for name, runs in sides.items():
            values = [
                run[case_id][end]["intervene_probability"]
                for run in runs
                if end in run.get(case_id, {})
                and run[case_id][end]["intervene_probability"] is not None
            ]
            mean = f"{statistics.mean(values):.2f}" if values else "-"
            cells.append(f"{name}={mean}")
        print(f"  through {end:>3}: mean intervene probability {' '.join(cells)}")


def _compare(args: argparse.Namespace) -> None:
    """Compare interventions, evidence, and behavior scores between two sets of runs."""
    baseline, variant = _databases(args.baseline), _databases(args.variant)
    sides = {
        "baseline": [_batches(path, args.cases) for path in baseline],
        "variant": [_batches(path, args.cases) for path in variant],
    }
    shared = {case_id for runs in sides.values() for run in runs for case_id in run}
    for case_id in sorted(shared, key=_natural):
        _report_batches(case_id, sides)

    base_scores = [_behavior_scores(path, args.cases) for path in baseline]
    variant_scores = [_behavior_scores(path, args.cases) for path in variant]
    within = _score_differences([*combinations(base_scores, 2), *combinations(variant_scores, 2)])
    between = _score_differences(
        [(first, second) for first in base_scores for second in variant_scores]
    )
    print("\nbehavior score differences")
    for name, values in (("within a set", within), ("between sets", between)):
        if values:
            print(f"  {name}: mean={statistics.mean(values):.4f} max={max(values):.4f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(required=True)

    run = commands.add_parser("run", help="replay case files on fresh servers")
    run.add_argument("output", type=Path, help="directory for databases, logs, and samples")
    run.add_argument("case_files", type=Path, nargs="+", help="JSONL observations to replay")
    run.add_argument("--target-speaker-id", required=True)
    run.add_argument("--replicates", type=int, default=1, help="replays of each case file")
    run.add_argument("--concurrency", type=int, default=1, help="servers running at once")
    run.add_argument("--together", action="store_true", help="replay all files on one server")
    run.add_argument("--cases", help="replay only case IDs matching this regex")
    run.add_argument("--seed", type=Path, help="start each run from a copy of this database")
    run.add_argument("--base-port", type=int, default=8200)
    run.add_argument("--timeout", type=float, default=1800, help="seconds to wait after sending")
    run.set_defaults(command=_run)

    outcomes = commands.add_parser("outcomes", help="report interventions and behaviors")
    outcomes.add_argument("databases", type=Path, nargs="+", help="databases or directories")
    outcomes.add_argument("--cases", help="report only case IDs matching this regex")
    outcomes.add_argument("--expected", type=Path, help="JSON of expected outcomes by case ID")
    outcomes.set_defaults(command=_outcomes)

    timing = commands.add_parser("timing", help="report time from speech to stored decision")
    timing.add_argument("databases", type=Path, nargs="+", help="databases or directories")
    timing.add_argument("--cases", help="report only case IDs matching this regex")
    timing.add_argument("--group", help="regex whose first group splits cases into groups")
    timing.add_argument("--live", action="store_true", help="the database holds live capture")
    timing.add_argument("--idle-seconds", type=float, default=20, help="server's idle limit")
    timing.set_defaults(command=_timing)

    load = commands.add_parser("load", help="report throughput and resources for one server")
    load.add_argument("database", type=Path)
    load.add_argument("--cases", help="report only case IDs matching this regex")
    load.add_argument("--group", help="regex whose first group splits cases into groups")
    load.set_defaults(command=_load)

    compare = commands.add_parser("compare", help="compare two sets of runs")
    compare.add_argument("--baseline", type=Path, nargs="+", required=True)
    compare.add_argument("--variant", type=Path, nargs="+", required=True)
    compare.add_argument("--cases", help="report only case IDs matching this regex")
    compare.set_defaults(command=_compare)

    args = parser.parse_args()
    args.command(args)


if __name__ == "__main__":
    main()
