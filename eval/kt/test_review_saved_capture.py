"""Offline archive and event-pair custody guards; no model/API execution."""
import json
from pathlib import Path
import tempfile
import unittest
import warnings
from zipfile import ZipFile, ZipInfo

import review_saved_capture as review


class ArchiveCustody(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archive = self.root / "package.zip"
        self.destination = self.root / "extracted"

    def package(self, members):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with ZipFile(self.archive, "w") as package:
                for name, data in members:
                    info = ZipInfo(name)
                    info.filename = name  # Keep adversarial ZIP names verbatim on Windows too.
                    package.writestr(info, data)
        return review.sha(self.archive)

    def test_wrong_expected_sha_writes_nothing(self):
        self.package([("report.json", b"{}")])
        with self.assertRaisesRegex(ValueError, "SHA"):
            review.extract_verified(self.archive, "0" * 64, self.destination)
        self.assertFalse(self.destination.exists())

    def test_traversal_and_nonportable_paths_fail_before_writes(self):
        for bad in ("../outside", "/absolute", "a/../alias", "./alias", "a\\b", "C:drive", "NUL", "trailing."):
            with self.subTest(member=bad):
                sha = self.package([("first.txt", b"safe"), (bad, b"bad")])
                with self.assertRaisesRegex(ValueError, "Unsafe"):
                    review.extract_verified(self.archive, sha, self.destination)
                self.assertFalse(self.destination.exists())

    def test_duplicate_and_case_alias_paths_fail_before_writes(self):
        for names in (("report.json", "report.json"), ("report.json", "REPORT.json"), ("a/", "A/")):
            with self.subTest(names=names):
                sha = self.package([(name, b"") for name in names])
                with self.assertRaisesRegex(ValueError, "Duplicate"):
                    review.extract_verified(self.archive, sha, self.destination)
                self.assertFalse(self.destination.exists())

    def test_existing_equal_extraction_is_preserved(self):
        sha = self.package([("nested/report.json", b'{"captured":true}\n')])
        first = review.extract_verified(self.archive, sha, self.destination)
        file = self.destination / "nested/report.json"
        timestamp = file.stat().st_mtime_ns
        (self.destination / "unrelated.txt").write_bytes(b"preserve")
        second = review.extract_verified(self.archive, sha.upper(), self.destination)
        self.assertEqual(first, second)
        self.assertEqual(timestamp, file.stat().st_mtime_ns)
        self.assertEqual((self.destination / "unrelated.txt").read_bytes(), b"preserve")

    def test_existing_different_extraction_is_not_overwritten(self):
        self.destination.mkdir()
        old = self.destination / "report.json"
        old.write_bytes(b"old evidence")
        sha = self.package([("new.txt", b"new"), ("report.json", b"different")])
        with self.assertRaisesRegex(ValueError, "Existing extraction differs"):
            review.extract_verified(self.archive, sha, self.destination)
        self.assertEqual(old.read_bytes(), b"old evidence")
        self.assertFalse((self.destination / "new.txt").exists())

    def test_file_used_as_archive_parent_fails_before_writes(self):
        sha = self.package([("first.txt", b"safe"), ("a", b"file"), ("a/b", b"nested")])
        with self.assertRaisesRegex(ValueError, "parent directory"):
            review.extract_verified(self.archive, sha, self.destination)
        self.assertFalse(self.destination.exists())

    def test_manifest_outside_verified_inventory_is_not_used(self):
        self.destination.mkdir()
        (self.destination / "capture-manifest.json").write_text("{}", encoding="utf-8")
        sha = self.package([("unrelated.txt", b"captured")])
        with self.assertRaisesRegex(ValueError, "exactly one capture manifest"):
            review.review(self.archive, sha, self.destination, self.root / "output", "HEAD")

    def test_missing_pinned_archive_artifact_cannot_use_existing_file(self):
        self.destination.mkdir()
        (self.destination / "server-attestation.json").write_text("{}", encoding="utf-8")
        manifest = {"artifacts": {"report.json": "irrelevant"}}
        sha = self.package([("capture/capture-manifest.json", json.dumps(manifest)),
                            ("control-deterministic-score.json", "{}"), ("control-agent-score.json", "{}")])
        with self.assertRaisesRegex(ValueError, "absent from verified archive"):
            review.review(self.archive, sha, self.destination, self.root / "output", "HEAD")


class ToolPairCustody(unittest.TestCase):
    @staticmethod
    def event(kind, call_id, seq, name="get_clause"):
        return {"type": kind, "seq": seq, "data": {"call_id": call_id, "name": name}}

    def test_pairs_require_unique_ids_on_both_sides(self):
        c1, c2 = self.event("tool_call", "one", 1), self.event("tool_call", "two", 2)
        r1, r2 = self.event("tool_result", "one", 3), self.event("tool_result", "two", 4)
        self.assertTrue(review.tool_pairs_valid([c1, c2, r1, r2]))
        self.assertFalse(review.tool_pairs_valid([c1, c1, r1, r2]))
        self.assertFalse(review.tool_pairs_valid([c1, c2, r1, r1]))

    def test_unpaired_reordered_and_renamed_results_fail(self):
        call = self.event("tool_call", "one", 2)
        for result in (self.event("tool_result", "other", 3), self.event("tool_result", "one", 1),
                       self.event("tool_result", "one", 3, name="different")):
            with self.subTest(result=result):
                self.assertFalse(review.tool_pairs_valid([call, result]))


if __name__ == "__main__":
    unittest.main()
