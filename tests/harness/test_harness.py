"""Run the real Bash entry points with a deterministic fake Wine executable."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def bash_path(path):
    path = str(path).replace("\\", "/")
    if os.name == "nt" and len(path) > 2 and path[1] == ":":
        return "/" + path[0].lower() + path[2:]
    return path


def find_bash():
    if os.environ.get("AEGIS_TEST_BASH"):
        return os.environ["AEGIS_TEST_BASH"]
    if os.name == "nt":
        candidate = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin/bash.exe"
        return str(candidate) if candidate.exists() else None
    return shutil.which("bash")


@unittest.skipUnless(find_bash(), "Bash unavailable; harness tests NOT VERIFIED")
class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="aegis harness ")
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.prefix = self.base / "wine prefix"
        (self.prefix / "drive_c/windows/system32/drivers").mkdir(parents=True)
        (self.prefix / "system.reg").write_text("synthetic test prefix")
        self.driver = self.base / "aegis_pushlock_test.sys"
        self.driver.write_bytes(b"SYNTHETIC: not a PE driver")
        self.client = self.base / "aegis_pushlock_client.exe"
        self.client.write_bytes(b"SYNTHETIC: not a PE client")
        self.mock = self.base / "mock-wine"
        self.mock.write_text('#!/usr/bin/env bash\nexec "$AEGIS_TEST_PYTHON" "$AEGIS_MOCK_SCRIPT" "$@"\n', encoding="utf-8", newline="\n")
        self.mock.chmod(0o755)
        self.state = self.base / "state.json"
        self.env = dict(os.environ, WINEPREFIX=bash_path(self.prefix),
            AEGIS_WINE_BIN=bash_path(self.mock), AEGIS_TEST_PYTHON=bash_path(sys.executable),
            AEGIS_PYTHON=bash_path(sys.executable), AEGIS_MOCK_SCRIPT=str(ROOT / "tests/harness/mock_wine.py"),
            AEGIS_MOCK_STATE=str(self.state), AEGIS_MOCK_CLIENT_FIXTURE=str(ROOT / "tests/parser/fixtures/client_pass.txt"),
            AEGIS_REPORT_DIR=bash_path(self.base / "reports"), AEGIS_TIMEOUT_SECONDS="2")

    def run_harness(self, mode="pass", with_client=True):
        self.env["AEGIS_MOCK_MODE"] = mode
        args = [find_bash(), bash_path(ROOT / "tools/wine-run-test.sh"), bash_path(self.driver)]
        if with_client:
            args.append(bash_path(self.client))
        process = subprocess.run(args, env=self.env, capture_output=True, text=True, timeout=25)
        reports = list((self.base / "reports").glob("*/report.json"))
        report = json.loads(reports[-1].read_text()) if reports else None
        return process, report

    def assert_cleaned(self):
        data = json.loads(self.state.read_text())
        self.assertFalse(data["created"])
        self.assertFalse((self.prefix / ".aegis-pushlock.lock").exists())
        self.assertFalse((self.prefix / "drive_c/windows/system32/drivers/aegis_pushlock_test.sys").exists())
        return data

    def test_success_and_type_one_service(self):
        process, report = self.run_harness()
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertEqual(report["result"], "PASS")
        data = self.assert_cleaned()
        create = next(call for call in data["calls"] if call[:2] == ["sc.exe", "create"])
        self.assertIn("type=", create)
        self.assertIn("kernel", create)
        self.assertIn("C:\\windows\\system32\\drivers\\aegis_pushlock_test.sys", create)
        self.assertNotIn("AEGIS: driver_loaded", process.stdout)

    def test_missing_api_and_cleanup(self):
        process, report = self.run_harness("missing")
        self.assertEqual(process.returncode, 1, process.stderr)
        self.assertEqual(report["missing_ntoskrnl"], ["ExInitializePushLock"])
        self.assert_cleaned()

    def test_timeout_fails_and_cleans(self):
        process, report = self.run_harness("timeout")
        self.assertEqual(process.returncode, 1, process.stderr)
        self.assertEqual(report["environment"]["start_exit_code"], 124)
        self.assert_cleaned()

    def test_client_failure(self):
        process, report = self.run_harness("client_fail")
        self.assertEqual(process.returncode, 1, process.stderr)
        self.assertIs(report["ioctl_success"], False)
        self.assert_cleaned()

    def test_no_client_is_never_pass(self):
        process, report = self.run_harness(with_client=False)
        self.assertEqual(process.returncode, 1, process.stderr)
        self.assertIsNone(report["ioctl_success"])
        self.assert_cleaned()

    def test_install_failure_rolls_back(self):
        process, report = self.run_harness("install_fail")
        self.assertEqual(process.returncode, 1, process.stderr)
        self.assertIn("harness_install_failed", report["failures"])
        self.assert_cleaned()

    def test_cleanup_failure_is_fail_and_preserves_image(self):
        process, report = self.run_harness("cleanup_fail")
        self.assertEqual(process.returncode, 1, process.stderr)
        self.assertIn("harness_stop_failed", report["failures"])
        self.assertTrue((self.prefix / "drive_c/windows/system32/drivers/aegis_pushlock_test.sys").exists())

    def test_existing_service_is_not_modified(self):
        self.state.write_text(json.dumps({"created": True, "running": True, "calls": []}))
        process, report = self.run_harness()
        self.assertEqual(process.returncode, 1, process.stderr)
        data = json.loads(self.state.read_text())
        self.assertTrue(data["created"])
        self.assertTrue(data["running"])
        self.assertFalse(any(call[:2] in (["sc.exe", "stop"], ["sc.exe", "delete"], ["sc.exe", "create"]) for call in data["calls"]))

    def test_existing_image_is_not_overwritten(self):
        destination = self.prefix / "drive_c/windows/system32/drivers/aegis_pushlock_test.sys"
        destination.write_bytes(b"existing")
        process, report = self.run_harness()
        self.assertEqual(process.returncode, 1, process.stderr)
        self.assertEqual(destination.read_bytes(), b"existing")

    def test_query_error_is_not_confused_with_missing_service(self):
        process, report = self.run_harness("query_denied")
        self.assertEqual(process.returncode, 1, process.stderr)
        data = json.loads(self.state.read_text())
        self.assertFalse(any(call[:2] == ["sc.exe", "create"] for call in data["calls"]))
        self.assert_cleaned()


if __name__ == "__main__":
    unittest.main()
