"""Offline capture custody guard tests. These are NOT provider/agent runs."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import capture_control as capture


class CaptureGuards(unittest.TestCase):
    def test_multiline_sse(self):
        event = {"type": "final", "data": {"payload": {"run_id": "r"}}}
        self.assertEqual(capture.sse_events("event: final\r\ndata: " + json.dumps(event) + "\r\n\r\n"), [event])

    def test_frozen_bytes_guard(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            for side in ("before", "after"):
                (base / (side + ".txt")).write_text(side)
            capture.write_json(base / "manifest.json", {"files": [{"path": s + ".txt", "sha256": capture.digest(base / (s + ".txt"))} for s in ("before", "after")]})
            with patch.object(capture, "CONTROL", base):
                self.assertEqual(len(capture.pinned_inputs("txt")), 2)
                (base / "after.txt").write_text("tampered")
                with self.assertRaisesRegex(ValueError, "frozen"):
                    capture.pinned_inputs("txt")

    def test_same_bytes_still_require_correct_editions(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "same.txt"
            path.write_text("same")
            sha = capture.digest(path)
            report = {"documents": [{"edition": s, "sha256": sha} for s in ("before", "after")]}
            capture.check_report_inputs(report, [("before", path), ("after", path)])
            report["documents"][1]["edition"] = "before"
            with self.assertRaisesRegex(ValueError, "editions"):
                capture.check_report_inputs(report, [("before", path), ("after", path)])

    def test_templates_are_not_approval(self):
        self.assertFalse(capture.actual_value({"model": "FILL"}))
        self.assertFalse(capture.actual_value({"provider": ""}))
        self.assertTrue(capture.actual_value({"seed": "unsupported", "temperature": 0}))

    def test_intake_requires_complete_same_format_pair(self):
        self.assertTrue(capture.complete_input_pair({"x/before.docx": "a", "x/after.docx": "b"}))
        self.assertFalse(capture.complete_input_pair({"x/before.txt": "a", "x/before.docx": "b"}))
        self.assertFalse(capture.complete_input_pair({"x/before.txt": "a", "x/after.docx": "b"}))
        self.assertFalse(capture.complete_input_pair({}))

    def test_schema_historical_null_agent(self):
        result = capture.trace_summary({"agent": None, "findings": []}, [])
        self.assertEqual(result["investigated_finding_ids"], [])
        self.assertFalse(result["model_inference_proven"])

    def test_findings_are_not_refs_and_events_are_not_inference(self):
        ref = {"doc": "before-1", "clause_id": "2"}
        report = {"findings": [{"id": "one", "status": "unresolved", "before": [ref], "after": []},
                               {"id": "two", "status": "unresolved", "before": [ref], "after": []}]}
        result = capture.trace_summary(report, [{"type": "tool_call", "data": {"name": "search"}}])
        self.assertEqual(result["unresolved_findings"], 2)
        self.assertEqual(result["unresolved_distinct_refs"], 1)
        self.assertFalse(result["model_inference_proven"])

    def test_multipart_preserves_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "input.bin"
            data = b"\x00\xff\r\nhello"
            path.write_bytes(data)
            body, kind = capture.multipart([("before", path)], False)
            self.assertIn(data, body)
            self.assertIn(b'name="before_files"', body)
            self.assertIn(b"false", body)
            self.assertTrue(kind.startswith("multipart/form-data; boundary="))


class RevisionCustody(unittest.TestCase):
    """Real temporary Git repositories and saved packages; no provider or network."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.control = self.root / "seeds/kt/eval/control"
        self.control.mkdir(parents=True)
        self.package = self.root / "package"
        self.package.mkdir()
        self.core = self.root / "apps/api/app/nested/core.py"
        self.core.parent.mkdir(parents=True)
        self.core.write_bytes(b"value = 1\n")
        (self.core.parent.parent / "__init__.py").write_bytes(b"")
        (self.core.parent / "excluded.txt").write_bytes(b"not Python\n")
        self.git("init", "--quiet")
        self.git("config", "core.autocrlf", "false")
        self.git("add", "apps/api/app")
        self.git("-c", "user.name=Offline Test", "-c", "user.email=test@example.invalid",
                 "commit", "--quiet", "-m", "test core")
        self.revision = self.git("rev-parse", "HEAD").decode().strip()
        self.addCleanup(patch.stopall)
        patch.object(capture, "ROOT", self.root).start()
        patch.object(capture, "CONTROL", self.control).start()
        self.hashes = capture.snapshot()
        inputs = {}
        for side in ("before", "after"):
            path = self.control / (side + ".txt")
            path.write_bytes(side.encode())
            inputs[path.relative_to(self.root).as_posix()] = capture.digest(path)
        capture.write_json(self.control / "manifest.json", {"files": [
            {"path": Path(name).name, "sha256": sha} for name, sha in inputs.items()]})
        runs = []
        for mode in ("deterministic", "agent"):
            report = {"run_id": mode, "mode": "deterministic", "findings": [], "documents": [
                {"edition": Path(name).stem, "sha256": sha} for name, sha in inputs.items()]}
            events = [{"seq": 1, "type": "final", "run_id": mode, "data": {"payload": report}}]
            capture.write_json(self.package / (mode + ".json"), report)
            capture.write_json(self.package / (mode + "-reopened.json"), report)
            capture.write_json(self.package / (mode + "-trace.json"), {"run_id": mode, "events": events})
            (self.package / (mode + ".sse")).write_text("data: " + json.dumps(events[0]) + "\n\n", encoding="utf-8")
            runs.append({"requested": mode, "run_id": mode,
                         "report_sha256": capture.digest(self.package / (mode + ".json"))})
        self.manifest = {"status": "captured", "revision": self.revision,
                         "schema_revision": self.revision, "core_hashes": self.hashes,
                         "configuration": {"model": "offline-fixture-no-inference"},
                         "input_sha256": inputs, "runs": runs,
                         "artifacts": {p.name: capture.digest(p) for p in self.package.iterdir()}}
        self.save_manifest()

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, stderr=subprocess.PIPE)

    def save_manifest(self):
        capture.write_json(self.package / "capture-manifest.json", self.manifest)

    def test_raw_git_blobs_accept_exact_complete_manifest(self):
        result = capture.verify_package(self.package, core_revision=self.revision)
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["core_verification"]["files_checked"], 2)
        self.assertTrue(result["core_verification"]["exact_manifest_matches"])

    def test_missing_core_file_fails_membership(self):
        self.manifest["core_hashes"].pop("apps/api/app/__init__.py")
        self.save_manifest()
        result = capture.verify_package(self.package, core_revision=self.revision)
        self.assertIn("Captured core file membership differs from requested Git revision", result["errors"])
        self.assertEqual(result["core_verification"]["missing_manifest_files"], ["apps/api/app/__init__.py"])

    def test_extra_core_file_fails_membership(self):
        self.manifest["core_hashes"]["apps/api/app/extra.py"] = "0" * 64
        self.save_manifest()
        result = capture.verify_package(self.package, core_revision=self.revision)
        self.assertIn("Captured core file membership differs from requested Git revision", result["errors"])
        self.assertEqual(result["core_verification"]["unexpected_manifest_files"], ["apps/api/app/extra.py"])

    def test_different_commit_fails_even_with_same_core_bytes(self):
        self.git("-c", "user.name=Offline Test", "-c", "user.email=test@example.invalid",
                 "commit", "--quiet", "--allow-empty", "-m", "different revision")
        result = capture.verify_package(self.package, core_revision="HEAD")
        self.assertIn("Requested core revision differs from captured manifest revision", result["errors"])
        self.assertTrue(result["core_verification"]["exact_manifest_matches"])

    def test_altered_captured_byte_fails_hash(self):
        path = "apps/api/app/nested/core.py"
        self.manifest["core_hashes"][path] = capture.hashlib.sha256(b"value = 2\n").hexdigest()
        self.save_manifest()
        result = capture.verify_package(self.package, core_revision=self.revision)
        self.assertIn("Captured core hashes differ from raw Git blobs at requested revision", result["errors"])
        self.assertEqual(result["core_verification"]["hash_mismatches"], [path])

    def test_raw_git_blobs_ignore_checkout_crlf_but_default_still_fails(self):
        self.core.write_bytes(b"value = 1\r\n")
        checkout = capture.verify_package(self.package)
        self.assertEqual(checkout["integrity_failures"], 1)
        self.assertFalse(checkout["local_core_hashes_equal"])
        raw = capture.verify_package(self.package, core_revision=self.revision)
        self.assertEqual(raw["errors"], [])
        self.assertFalse(raw["local_core_hashes_equal"])
        self.assertEqual(raw["core_verification"]["source"], "raw_git_blobs")

    def test_missing_revision_fails_closed(self):
        result = capture.verify_package(self.package, core_revision="does-not-exist")
        self.assertEqual(result["integrity_failures"], 1)
        self.assertFalse(result["core_verification"]["exact_manifest_matches"])


if __name__ == "__main__":
    unittest.main()
