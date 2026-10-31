#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

from normative_conformance.schemas.observation import ObservationInput


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a stored case as replayable JSONL")
    parser.add_argument("case_id", help="Stored case to export, such as a capture's case ID")
    parser.add_argument("output", type=Path, help="JSONL file to write")
    parser.add_argument("--as-case-id", help="Case ID to write instead of the stored one")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API server URL")
    args = parser.parse_args()

    url = (
        args.base_url.rstrip("/")
        + "/api/v1/cases/"
        + quote(args.case_id, safe="")
        + "/observations"
    )
    with urlopen(url, timeout=10) as response:
        records = json.load(response)["items"]

    # The API lists ingested speech newest first and omits speaker corrections.
    records.sort(key=lambda record: record["sequence"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as output:
        for record in records:
            row = {name: record[name] for name in ObservationInput.model_fields}
            if args.as_case_id is not None:
                row["case_id"] = args.as_case_id
            ObservationInput.model_validate(row)
            output.write(json.dumps(row, separators=(",", ":")) + "\n")
    print(f"Wrote {len(records)} observations to {args.output}")


if __name__ == "__main__":
    main()
