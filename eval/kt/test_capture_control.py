"""Offline capture custody guard tests. These are NOT provider/agent runs."""
import json
from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
