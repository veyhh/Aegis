#!/usr/bin/env python3
"""Internal harness helper; argv fields avoid shell-built JSON."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys


def sha256(filename):
    if not filename:
        return None
    digest = hashlib.sha256()
    with Path(filename).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    output, driver, client, prefix, version, *codes = sys.argv[1:]
    report = {
        "platform": "wine", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "host": platform.platform(), "architecture": platform.machine(),
        "wine_version": Path(version).read_text(encoding="utf-8", errors="replace").strip(),
        "wineprefix": prefix, "winedebug": "+ntoskrnl,+module,+service",
        "driver_sha256": sha256(driver), "client_sha256": sha256(client),
    }
    for step, code in zip(("install", "start", "client", "stop", "delete", "harness"), codes, strict=True):
        report[step + "_exit_code"] = int(code)
    Path(output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
