#!/usr/bin/env python3
"""Produce JSON; exit 0=verified PASS, 1=FAIL/inconclusive, 2=input error."""
import argparse
import json
from pathlib import Path
import sys

from aegis_log import parse_log


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--client-output", type=Path)
    parser.add_argument("--client-exit-code", type=int)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        metadata = json.loads(args.metadata.read_text(encoding="utf-8-sig")) if args.metadata else {}
        if not isinstance(metadata, dict):
            raise ValueError("metadata must be a JSON object")
        report = parse_log(
            args.log.read_text(encoding="utf-8-sig", errors="replace"),
            client_text=args.client_output.read_text(encoding="utf-8-sig", errors="replace") if args.client_output else None,
            client_exit_code=args.client_exit_code, metadata=metadata,
        )
        output = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        if args.output:
            args.output.write_text(output, encoding="utf-8")
        else:
            sys.stdout.write(output)
        return 0 if report["result"] == "PASS" else 1
    except (OSError, ValueError) as exc:
        print(f"AEGIS parser input error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
