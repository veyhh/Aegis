#!/usr/bin/env python3
"""Render version 1 compatibility reports without inventing missing evidence."""
import argparse
import json
from pathlib import Path
import sys


def status(value):
    return "PASS" if value is True else "FAIL" if value is False else "NOT VERIFIED"


def render(report):
    lines = ["AEGIS Compatibility Report", "", "Test: " + report["test"]]
    for label, field in (
        ("Driver image loaded", "driver_image_loaded"),
        ("DriverInit address found", "driver_init_address_found"),
        ("DriverInit reached", "driver_init_reached"),
        ("Driver loaded", "loaded"), ("Device created", "device_created"),
        ("Device opened", "device_opened"), ("IOCTL completed", "ioctl_success"),
    ):
        lines.append(f"{label}: {status(report.get(field))}")
    lines += ["", "Missing NTOSKRNL APIs:"]
    lines += ["- " + api for api in report["missing_ntoskrnl"]] or ["- None observed (absence is not proof of support)"]
    if report.get("failures"):
        lines += ["", "Failures:"] + ["- " + item for item in report["failures"]]
    lines += ["", "Verification: " + report.get("verification", "NOT_VERIFIED"),
              "Overall:", report["result"]]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
        if report.get("schema_version") != 1 or report.get("result") not in ("PASS", "FAIL"):
            raise ValueError("unsupported schema version or result")
        output = render(report)
        if args.output:
            args.output.write_text(output, encoding="utf-8")
        else:
            print(output, end="")
        return 0 if report["result"] == "PASS" else 1
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        print(f"AEGIS report input error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
