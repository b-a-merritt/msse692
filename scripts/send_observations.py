#!/usr/bin/env python3
import argparse
import time
from pathlib import Path
from urllib.request import Request
from urllib.request import urlopen


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
        default=0.0,
        help="Seconds between submissions (default: 0)",
    )
    args = parser.parse_args()

    url = args.base_url.rstrip("/") + "/api/v1/observations"

    with args.case_file.open(encoding="utf-8") as case_file:
        for line_number, line in enumerate(case_file, start=1):
            time.sleep(args.delay)

            request = Request(
                url=url,
                data=line.encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urlopen(request, timeout=10) as response:
                print(f"Submitted line {line_number}: HTTP {response.status}", flush=True)


if __name__ == "__main__":
    main()
