#!/usr/bin/env python3
import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from urllib.request import Request
from urllib.request import urlopen


def _parse_timestamp(*, value: str) -> datetime:
    # Python 3.10's fromisoformat rejects the "Z" suffix.
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Submit a JSONL case to the observation API")
    parser.add_argument(
        "case_file",
        type=Path,
        help="JSONL observations to submit",
    )
    parser.add_argument("--base-url", default="http://localhost:8000", help="API server URL")
    parser.add_argument(
        "--delay",
        type=float,
        help="Seconds between submissions (default: replay recorded gaps)",
    )
    args = parser.parse_args()

    url = args.base_url.rstrip("/") + "/api/v1/observations"

    with args.case_file.open(encoding="utf-8") as case_file:
        prev_end_at = None

        for line_number, line in enumerate(case_file, start=1):
            if not line.strip():
                continue

            observation = json.loads(line)
            end_at = _parse_timestamp(value=observation["end_at"])

            if args.delay is not None:
                delay_sec = args.delay
            elif prev_end_at is None:
                delay_sec = 0.0
            else:
                diff = end_at - prev_end_at
                delay_sec = max(0.0, diff.total_seconds())

            # Overlapping chunks can end out of order
            prev_end_at = end_at if prev_end_at is None else max(prev_end_at, end_at)

            time.sleep(delay_sec)

            request = Request(
                url=url,
                data=line.encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urlopen(request, timeout=10) as response:
                print(
                    f"Submitted line {line_number}: HTTP {response.status} | Delay: {delay_sec}",
                    flush=True,
                )


if __name__ == "__main__":
    main()
