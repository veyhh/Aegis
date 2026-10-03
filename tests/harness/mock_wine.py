"""Synthetic Wine process for shell orchestration tests; never loads a driver."""
import json
import os
from pathlib import Path
import sys
import time

state = Path(os.environ["AEGIS_MOCK_STATE"])
mode = os.environ.get("AEGIS_MOCK_MODE", "pass")
data = json.loads(state.read_text()) if state.exists() else {"created": False, "running": False, "calls": []}
args = sys.argv[1:]
data["calls"].append(args)


def finish(code=0, message=""):
    state.write_text(json.dumps(data))
    if message:
        print(message, file=sys.stderr)
    raise SystemExit(code)


if args == ["--version"]:
    print("wine-SYNTHETIC-HARNESS-TEST")
    finish()
if args[0] == "sc.exe":
    action = args[1]
    if action == "query":
        if mode == "query_denied":
            finish(5, "failed to open service 5 at address 1060")
        finish(0 if data["created"] else 1060, "[SC] OpenService FAILED 1060" if not data["created"] else "")
    if action == "create":
        if mode == "install_fail":
            finish(5, "failed to create service 5")
        data["created"] = True
        finish()
    if action == "start":
        if mode == "missing":
            finish(1, "AEGIS: driver_init_reached=true\nNo implementation for ntoskrnl.exe.ExInitializePushLock\nZwLoadDriver failed")
        if mode == "timeout":
            state.write_text(json.dumps(data))
            time.sleep(10)
            finish()
        data["running"] = True
        finish(0, "AEGIS: driver_init_reached=true\nAEGIS: device_created=true\nAEGIS: driver_loaded=true")
    if action == "stop":
        if mode == "cleanup_fail":
            finish(5, "service stop error 5")
        if not data["running"]:
            finish(1062, "[SC] ControlService FAILED 1062")
        data["running"] = False
        finish()
    if action == "delete":
        data["created"] = False
        finish()
    finish(2, "unexpected sc command")
if mode == "client_fail":
    print("AEGIS_PUSHLOCK_TEST\ndriver_loaded=true\ndevice_opened=true\nioctl_success=false\nwin32_error=1\nresult=FAIL")
    finish(3)
print(Path(os.environ["AEGIS_MOCK_CLIENT_FIXTURE"]).read_text(), end="")
finish()
