"""Conservative evidence extraction for the AEGIS PushLock smoke test."""
from __future__ import annotations

import re
from typing import Any

DRIVER = "aegis_pushlock_test"
PUSHLOCK_APIS = [
    "ExInitializePushLock",
    "ExAcquirePushLockExclusiveEx",
    "ExReleasePushLockExclusiveEx",
]
_MODULE_API = re.compile(
    r"\b(?P<module>ntoskrnl(?:\.exe)?|[A-Za-z0-9_-]+\.(?:dll|exe))"
    r"[.!](?P<api>[A-Za-z_][A-Za-z0-9_]*)(?![A-Za-z0-9_])", re.I
)
_FAILURES = {
    "zw_load_driver_failed": r"\bZwLoadDriver\b.*\bfailed\b",
    "driver_creation_failed": r"failed to create driver\b",
    "service_start_failed": r"service start failed|StartService\s+(?:FAILED|failed)|StartService\s+error",
}


def parse_client(text: str | None, exit_code: int | None) -> dict[str, Any]:
    fields: dict[str, str] = {}
    errors: list[str] = []
    if text is None:
        return {"fields": fields, "valid": False, "errors": [], "present": False}
    lines = text.strip().splitlines()
    if not lines or lines[0].strip() != "AEGIS_PUSHLOCK_TEST":
        errors.append("client_header_missing")
    for line in lines[1:]:
        if "=" not in line:
            errors.append("malformed_client_line")
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        if key in fields:
            errors.append("duplicate_client_field:" + key)
        fields[key] = value
    expected = {
        "driver_loaded": "true", "device_opened": "true",
        "ioctl_success": "true", "bytes_returned": "20", "version": "1",
        "passed": "1", "initial_value": "0", "final_value": "1",
        "error_code": "0", "result": "PASS",
    }
    valid = not errors and exit_code == 0 and all(
        fields.get(key) == value for key, value in expected.items()
    )
    if not valid and not errors:
        errors.append("client_result_not_verified")
    return {"fields": fields, "valid": valid, "errors": errors, "present": True}


def parse_log(text: str, *, client_text: str | None = None,
              client_exit_code: int | None = None,
              metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Unknown stages are None; absent diagnostics never imply implementation."""
    stages: dict[str, bool | None] = {
        "driver_image_loaded": None, "driver_init_address_found": None,
        "driver_init_reached": None, "loaded": None, "device_created": None,
        "device_opened": None, "ioctl_success": None,
    }
    evidence: dict[str, list[str]] = {}
    missing: set[str] = set()
    unimplemented: set[tuple[str, str]] = set()
    failures: set[str] = set()
    metadata = metadata or {}

    def record(stage: str, value: bool, line: str) -> None:
        # Conflicting stage markers are retained as a failure, never a false PASS.
        if stages[stage] is not None and stages[stage] != value:
            failures.add("conflicting_evidence:" + stage)
        stages[stage] = value
        evidence.setdefault(stage, []).append(line.strip())

    for line in text.splitlines():
        if re.search(r"No implementation for|unimplemented function", line, re.I):
            failures.add("unimplemented_call")
            evidence.setdefault("unimplemented", []).append(line.strip())
            for match in _MODULE_API.finditer(line):
                module = match["module"].lower()
                module = "ntoskrnl.exe" if module in ("ntoskrnl", "ntoskrnl.exe") else module
                api = match["api"]
                unimplemented.add((module, api))
                if module == "ntoskrnl.exe":
                    missing.add(api)
        for kind, pattern in _FAILURES.items():
            if re.search(pattern, line, re.I):
                failures.add(kind)
                evidence.setdefault(kind, []).append(line.strip())
        # AEGIS markers originate in our driver. Client stdout is parsed separately.
        for stage in ("driver_init_reached", "device_created", "driver_loaded"):
            match = re.search(r"\bAEGIS:\s*" + stage + r"=(true|false)\b", line)
            if match:
                record("loaded" if stage == "driver_loaded" else stage,
                       match[1] == "true", line)
        if DRIVER in line.lower():
            if re.search(r"\bLoaded\s+L?[\"'].*aegis_pushlock_test\.sys[\"']|"
                         r"mapped image.*aegis_pushlock_test\.sys", line, re.I):
                record("driver_image_loaded", True, line)
            if re.search(r"\binit done for\b", line, re.I):
                record("driver_init_reached", True, line)
            if re.search(r"\bDriverInit\s*(?:=|address[:=])\s*(?:0x)?[0-9a-f]+", line, re.I):
                record("driver_init_address_found", True, line)

    client = parse_client(client_text, client_exit_code)
    fields = client["fields"]
    # A successfully opened device proves a loaded driver; an open failure does
    # not prove it was unloaded (ACLs and link creation may have failed).
    if "client_header_missing" not in client["errors"] and not any(
        item.startswith("duplicate_client_field") for item in client["errors"]
    ):
        for stage in ("device_opened", "ioctl_success"):
            if fields.get(stage) in ("true", "false"):
                record(stage, fields[stage] == "true", "client:" + stage + "=" + fields[stage])
        if fields.get("device_opened") == "true":
            for stage in ("loaded", "device_created", "driver_init_reached", "driver_image_loaded"):
                record(stage, True, "client:device_opened=true")

    for step in ("install", "start", "stop", "delete", "harness"):
        code = metadata.get(step + "_exit_code")
        if code is not None and code != 0:
            failures.add("harness_" + step + "_failed")
    if failures.intersection({"zw_load_driver_failed", "driver_creation_failed", "service_start_failed", "harness_start_failed"}):
        # Do not erase positive stage evidence if a driver failed after mapping.
        if stages["loaded"] is None:
            stages["loaded"] = False
    failures.update(client["errors"])
    passed = client["valid"] and not failures
    observed = bool(evidence or failures or client["present"])
    return {
        "schema_version": 1, "test": "PushLock", "driver": DRIVER,
        **stages,
        "required_ntoskrnl": PUSHLOCK_APIS.copy(),
        "missing_ntoskrnl": sorted(missing),
        "unimplemented": [{"module": module, "function": api} for module, api in sorted(unimplemented)],
        "client_result": fields.get("result"), "client_exit_code": client_exit_code,
        "client_fields": fields, "failures": sorted(failures),
        "evidence": evidence, "environment": metadata,
        "verification": "OBSERVED" if observed else "NOT_VERIFIED",
        "scope": "uncontended_exclusive_smoke_test",
        "result": "PASS" if passed else "FAIL",
    }
