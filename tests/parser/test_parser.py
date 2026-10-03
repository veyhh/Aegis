"""Fixtures are synthetic. These tests do not certify kernel compatibility."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from aegis_log import PUSHLOCK_APIS, parse_log  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


class ParserTests(unittest.TestCase):
    def test_all_present_with_client(self):
        report = parse_log(fixture("all_present.log"), client_text=fixture("client_pass.txt"), client_exit_code=0)
        self.assertEqual(report["result"], "PASS")
        self.assertEqual(report["missing_ntoskrnl"], [])
        self.assertIs(report["loaded"], True)
        self.assertIs(report["driver_init_reached"], True)

    def test_log_alone_never_passes(self):
        report = parse_log(fixture("all_present.log"))
        self.assertEqual(report["result"], "FAIL")
        self.assertIsNone(report["ioctl_success"])

    def test_single_missing(self):
        report = parse_log(fixture("single_missing.log"))
        self.assertEqual(report["missing_ntoskrnl"], ["ExInitializePushLock"])
        self.assertEqual(report["result"], "FAIL")

    def test_multiple_missing_deduplicated(self):
        report = parse_log(fixture("multiple_missing.log"))
        self.assertEqual(report["missing_ntoskrnl"], sorted(PUSHLOCK_APIS))
        self.assertIs(report["driver_image_loaded"], True)
        self.assertIs(report["loaded"], False)

    def test_zw_load_driver_failure(self):
        report = parse_log(fixture("zw_failure.log"))
        self.assertIs(report["loaded"], False)
        self.assertIn("zw_load_driver_failed", report["failures"])
        self.assertIn("driver_creation_failed", report["failures"])
        self.assertIn("service_start_failed", report["failures"])

    def test_empty_and_malformed_are_not_verified(self):
        for text in ("", fixture("malformed.log"), "result=PASS"):
            with self.subTest(text=text):
                report = parse_log(text)
                self.assertEqual(report["result"], "FAIL")
                self.assertEqual(report["verification"], "NOT_VERIFIED")
                self.assertIsNone(report["loaded"])

    def test_address_is_not_execution(self):
        report = parse_log("aegis_pushlock_test DriverInit = 0x12345")
        self.assertIs(report["driver_init_address_found"], True)
        self.assertIsNone(report["driver_init_reached"])

    def test_unimplemented_other_module(self):
        report = parse_log("wine: unimplemented function other.dll.SampleApi, aborting")
        self.assertEqual(report["missing_ntoskrnl"], [])
        self.assertEqual(report["unimplemented"], [{"module": "other.dll", "function": "SampleApi"}])
        self.assertEqual(report["result"], "FAIL")

    def test_unimplemented_without_symbol_still_fails(self):
        report = parse_log("wine: unimplemented function", client_text=fixture("client_pass.txt"), client_exit_code=0)
        self.assertEqual(report["result"], "FAIL")

    def test_case_insensitive_and_bang_separator(self):
        report = parse_log("No implementation for NTOSKRNL.EXE!ExInitializePushLock")
        self.assertEqual(report["missing_ntoskrnl"], ["ExInitializePushLock"])

    def test_bad_client_results_never_pass(self):
        output = fixture("client_pass.txt")
        variants = [output.replace("version=1", "version=2"),
                    output.replace("bytes_returned=20", "bytes_returned=4"),
                    output.replace("final_value=1", "final_value=0"),
                    output.replace("error_code=0", "error_code=1"),
                    output.replace("AEGIS_PUSHLOCK_TEST", "OTHER_TEST"),
                    output + "result=PASS\n", "result=PASS\n", ""]
        for text in variants:
            with self.subTest(text=text):
                self.assertEqual(parse_log("", client_text=text, client_exit_code=0)["result"], "FAIL")

    def test_client_exit_code_required(self):
        for code in (None, 1, 124):
            self.assertEqual(parse_log("", client_text=fixture("client_pass.txt"), client_exit_code=code)["result"], "FAIL")

    def test_diagnostics_override_client_pass(self):
        report = parse_log(fixture("single_missing.log"), client_text=fixture("client_pass.txt"), client_exit_code=0)
        self.assertEqual(report["result"], "FAIL")

    def test_cleanup_failure_overrides_client_pass(self):
        for step in ("install", "start", "stop", "delete", "harness"):
            with self.subTest(step=step):
                report = parse_log("", client_text=fixture("client_pass.txt"), client_exit_code=0,
                                   metadata={step + "_exit_code": 1})
                self.assertEqual(report["result"], "FAIL")

    def test_open_failure_does_not_prove_unloaded(self):
        report = parse_log("", client_text="AEGIS_PUSHLOCK_TEST\ndriver_loaded=false\ndevice_opened=false\nioctl_success=false\nresult=FAIL\n", client_exit_code=2)
        self.assertIsNone(report["loaded"])
        self.assertIs(report["device_opened"], False)

    def test_conflicting_evidence_fails(self):
        report = parse_log("AEGIS: driver_loaded=false", client_text=fixture("client_pass.txt"), client_exit_code=0)
        self.assertIn("conflicting_evidence:loaded", report["failures"])
        self.assertEqual(report["result"], "FAIL")


class CliTests(unittest.TestCase):
    def run_cli(self, script, *args):
        return subprocess.run([sys.executable, str(ROOT / "tools" / script), *map(str, args)],
                              capture_output=True, text=True, timeout=10)

    def test_parser_and_report_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            result = self.run_cli("parse-wine-log.py", FIXTURES / "all_present.log", "--client-output", FIXTURES / "client_pass.txt", "--client-exit-code", 0, "--output", output)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = self.run_cli("aegis-report.py", output)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("IOCTL completed: PASS", result.stdout)

    def test_parser_fail_json(self):
        result = self.run_cli("parse-wine-log.py", FIXTURES / "multiple_missing.log")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["result"], "FAIL")

    def test_windows_bom_client_and_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            client = Path(directory) / "client.stdout"
            metadata = Path(directory) / "metadata.json"
            client.write_text(fixture("client_pass.txt"), encoding="utf-8-sig")
            metadata.write_text('{"platform":"windows"}', encoding="utf-8-sig")
            result = self.run_cli("parse-wine-log.py", FIXTURES / "all_present.log",
                                  "--client-output", client, "--client-exit-code", 0, "--metadata", metadata)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_parser_missing_file_is_input_error(self):
        result = self.run_cli("parse-wine-log.py", FIXTURES / "does-not-exist.log")
        self.assertEqual(result.returncode, 2)
        self.assertIn("input error", result.stderr)

    def test_metadata_must_be_object(self):
        with tempfile.TemporaryDirectory() as directory:
            metadata = Path(directory) / "bad.json"
            metadata.write_text("[]", encoding="utf-8")
            result = self.run_cli("parse-wine-log.py", FIXTURES / "all_present.log", "--metadata", metadata)
            self.assertEqual(result.returncode, 2)

    def test_report_unknown_schema_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "bad.json"
            report.write_text('{"schema_version":2}', encoding="utf-8")
            self.assertEqual(self.run_cli("aegis-report.py", report).returncode, 2)

    def test_unknown_stage_rendering(self):
        spec = importlib.util.spec_from_file_location("aegis_report", ROOT / "tools" / "aegis-report.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertIn("Device created: NOT VERIFIED", module.render(parse_log("")))


if __name__ == "__main__":
    unittest.main()
