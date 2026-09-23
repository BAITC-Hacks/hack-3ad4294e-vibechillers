"""Boundary checks for the existing evaluator; no aligner imports or shared suite."""
from __future__ import annotations

import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("kt_score", Path(__file__).with_name("score.py"))
score = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(score)


def ref(doc, clause):
    return {"doc": doc, "clause_id": clause}


def gold(status="changed", before=None, after=None, identifier="case-1"):
    return {"id": identifier, "kind": "synthetic", "expected_status": status,
            "before": before if before is not None else [ref("old", "1.1")],
            "after": after if after is not None else [ref("new", "1.1")]}


def prediction(row, status=None):
    return {"id": "finding-1", "status": status or row["expected_status"],
            "before": copy.deepcopy(row["before"]), "after": copy.deepcopy(row["after"]),
            "citations": []}


def report_for(row, findings):
    return {"run_id": "test-run", "findings": findings,
            "clauses": [{**item, "text": "Source text."} for item in row["before"] + row["after"]]}


def evaluate(row, findings):
    report = report_for(row, findings)
    with contextlib.redirect_stdout(io.StringIO()):
        return score.score_group("test/synthetic", [(report, row, {"old": "old", "new": "new"})])


class ReferenceAndAbstentionTests(unittest.TestCase):
    def test_compound_order_independent_but_not_subset(self):
        row = gold(after=[ref("new", "1.1"), ref("new", "1.2")])
        finding = prediction(row)
        finding["after"].reverse()
        result = evaluate(row, [finding])
        self.assertEqual((result["tp"], result["fp"], result["fn"]), (1, 0, 0))
        finding["after"].pop()
        result = evaluate(row, [finding])
        self.assertEqual((result["tp"], result["fp"], result["fn"]), (0, 1, 1))
        self.assertEqual(result["error_counts"]["wrong_match"], 1)

    def test_wrong_status_degrades_precision_and_recall(self):
        row = gold()
        result = evaluate(row, [prediction(row, "moved")])
        self.assertEqual(result["statuses"]["moved"]["fp"], 1)
        self.assertEqual(result["statuses"]["changed"]["fn"], 1)
        self.assertEqual(result["error_counts"]["wrong_status"], 1)

    def test_duplicate_prediction_is_extra_fp(self):
        row = gold()
        result = evaluate(row, [prediction(row), prediction(row)])
        self.assertEqual((result["tp"], result["fp"], result["fn"]), (1, 1, 0))
        self.assertEqual(result["error_counts"]["extra_duplicate_prediction"], 1)

    def test_unlabelled_is_unmeasured_not_tp(self):
        row = gold()
        unrelated = prediction(gold(before=[ref("old", "9")], after=[ref("new", "9")]))
        result = evaluate(row, [prediction(row), unrelated])
        self.assertEqual((result["tp"], result["fp"]), (1, 0))
        self.assertEqual(result["counts"]["unlabelled_findings"], 1)

    def test_unknown_status_is_visible(self):
        row = gold()
        result = evaluate(row, [prediction(row, "invented")])
        self.assertEqual(result["counts"]["unknown_status_findings"], 1)
        self.assertEqual(result["fn"], 1)
        self.assertEqual(result["error_counts"]["unknown_status_prediction"], 1)

    def test_exact_appropriate_abstention_is_not_semantic_tp(self):
        row = gold("unresolved")
        result = evaluate(row, [prediction(row)])
        self.assertEqual((result["semantic_gold"], result["tp"], result["fn"]), (0, 0, 0))
        self.assertEqual(result["counts"]["appropriate_abstention_matches"], 1)
        self.assertEqual(result["counts"]["appropriate_abstention_gold"], 1)

    def test_partial_abstention_is_not_appropriate(self):
        row = gold("unresolved", after=[ref("new", "1.1"), ref("new", "1.2")])
        finding = prediction(row)
        finding["after"].pop()
        result = evaluate(row, [finding])
        self.assertEqual(result["counts"]["appropriate_abstention_matches"], 0)
        self.assertEqual(result["counts"]["partial_overlap_refusal_labels"], 1)
        self.assertEqual(result["error_counts"]["wrong_abstention_refs"], 1)

    def test_abstention_on_resolvable_and_unsupported_resolution(self):
        result = evaluate(gold(), [prediction(gold(), "unresolved")])
        self.assertEqual(result["fn"], 1)
        self.assertEqual(result["error_counts"]["abstention_on_resolvable"], 1)
        result = evaluate(gold("unresolved"), [prediction(gold(), "changed")])
        self.assertEqual(result["fp"], 1)
        self.assertEqual(result["error_counts"]["unsupported_resolution"], 1)

    def test_missing_report_clause_is_only_labelled_omission(self):
        row = gold()
        report = report_for(row, [prediction(row)])
        report["clauses"].pop()
        with contextlib.redirect_stdout(io.StringIO()):
            result = score.score_group("test", [(report, row, {"old": "old", "new": "new"})])
        self.assertEqual(result["tp"], 1)  # Ref/status result and provenance stay separate.
        self.assertEqual(result["error_counts"]["parsing_omission"], 1)
        self.assertIn("unmeasured", result["candidate_recall"])
        self.assertIn("unmeasured", result["extraction_completeness"])

    def test_per_label_aliases_are_canonicalised(self):
        first = gold(identifier="first")
        second = gold(before=[ref("old-2", "1.2")], after=[ref("new-2", "1.2")], identifier="second")
        findings = [prediction(first), prediction(gold(before=[ref("old", "1.2")], after=[ref("new", "1.2")]))]
        report = report_for(first, findings)
        with contextlib.redirect_stdout(io.StringIO()):
            result = score.score_group("test", [(report, first, {"old": "old", "new": "new"}),
                                                (report, second, {"old": "old-2", "new": "new-2"})])
        self.assertEqual((result["tp"], result["fn"]), (2, 0))


class DocumentIdentityTests(unittest.TestCase):
    def setUp(self):
        self.row = {**gold(), "documents": [{"doc": "old", "file": "fixture.txt", "sha256": "same"},
                                            {"doc": "new", "file": "fixture.txt", "sha256": "same"}]}
        self.report = {"documents": [{"doc": "upload-a", "sha256": "same", "edition": "before"},
                                      {"doc": "upload-b", "sha256": "same", "edition": "after"}]}

    def test_same_file_both_sides(self):
        self.assertEqual(score.report_aliases(self.row, self.report), {"upload-a": "old", "upload-b": "new"})

    def test_same_side_ambiguous_fails(self):
        self.row["before"].append(ref("new", "1.1"))
        self.row["after"] = []
        self.report["documents"][1]["edition"] = "before"
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            score.report_aliases(self.row, self.report)

    def test_different_fixture_returns_none(self):
        self.report["documents"][1]["sha256"] = "different"
        self.assertIsNone(score.report_aliases(self.row, self.report))

    def test_four_docs_arbitrary_aliases(self):
        row = {**gold(before=[ref("a", "1"), ref("b", "1")], after=[ref("c", "1"), ref("d", "1")]),
               "documents": [{"doc": alias, "file": "x", "sha256": alias} for alias in "abcd"]}
        report = {"documents": [{"doc": "upload-" + alias, "sha256": alias,
                                   "edition": "before" if alias in "ab" else "after"} for alias in "dcba"]}
        self.assertEqual(score.report_aliases(row, report), {"upload-" + alias: alias for alias in "abcd"})

    def test_four_docs_unreferenced_identical_pair_uses_contract_aliases(self):
        row = {**gold(before=[ref("before-1", "1")], after=[ref("after-1", "1")]),
               "documents": [{"doc": alias, "file": "x", "sha256": digest}
                             for alias, digest in [("before-1", "a"), ("after-1", "b"),
                                                   ("before-2", "same"), ("after-2", "same")]]}
        report = {"documents": [{"doc": "upload-" + str(i), "sha256": doc["sha256"],
                                  "edition": doc["doc"].split("-")[0]}
                                 for i, doc in enumerate(row["documents"])]}
        self.assertEqual(score.report_aliases(row, report),
                         {"upload-" + str(i): doc["doc"] for i, doc in enumerate(row["documents"])})


class ClauseBoundaryTests(unittest.TestCase):
    def test_inline_marker_does_not_leak_quote_into_previous_clause(self):
        source = "1.1. First. 1.2.Second."
        self.assertEqual(score.clause_text(source, "1.1"), "First.")
        self.assertEqual(score.clause_text(source, "1.2"), "Second.")
        self.assertNotIn("Second.", score.clause_text(source, "1.1"))

    def test_no_space_start_and_multiline(self):
        self.assertEqual(score.clause_text("3.10.Workers audit.\r\nContinue here.\r\n3.11. End.", "3.10"),
                         "Workers audit.\r\nContinue here.")

    def test_inline_marker_without_separating_space(self):
        self.assertEqual(score.clause_text("1.1.First.1.2.Second.", "1.1"), "First.")
        self.assertEqual(score.clause_text("1.1.First.1.2.Second.", "1.2"), "Second.")

    def test_letter_and_repeated_paths(self):
        source = "3.4. Units.\nа. First.\nб. Second.\n3.4. Other units.\nа. Third."
        self.assertEqual(score.clause_text(source, "3.4/а"), "First.")
        self.assertEqual(score.clause_text(source, "3.4@2"), "Other units.")
        self.assertEqual(score.clause_text(source, "3.4/а@2"), "Third.")

    def test_crossrefs_and_dates_are_not_markers(self):
        source = "1.1. See п. 1.2. and пункт 1.3. dated 25.06.2021.\n1.2. Actual clause."
        self.assertIn("п. 1.2.", score.clause_text(source, "1.1"))
        self.assertEqual(score.clause_text(source, "1.2"), "Actual clause.")
        with self.assertRaises(ValueError):
            score.clause_text(source, "25.06.2021")

    def test_ambiguous_inline_fails_visibly(self):
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            score.clause_text("1.1. First 1.2. Maybe another clause.", "1.1")
        with self.assertRaises(ValueError):
            score.clause_text("1.1. First 1.2. Maybe another clause.", "1.2")


class ValidationTests(unittest.TestCase):
    def test_pending_holdout_cannot_be_scored(self):
        row = gold()
        for review in ("pending_human", "unrecorded", None):
            with self.subTest(review=review):
                with self.assertRaisesRegex(ValueError, "use --partition development until Alibi confirms holdout"):
                    score.require_reviewed_holdout([row], {row["id"]: "holdout"}, {row["id"]: review})
        for review in ("confirmed", "legacy_accepted"):
            score.require_reviewed_holdout([row], {row["id"]: "holdout"}, {row["id"]: review})
        score.require_reviewed_holdout([row], {row["id"]: "development"}, {row["id"]: "pending_human"})

    def test_context_citation_is_allowed_and_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = "1. Parent duty.\n1.1. Child duty.\n"
            fixture = root / "fixture.txt"
            fixture.write_text(source, encoding="utf-8")
            row = {**gold("missing", before=[ref("old", "1.1")], after=[]),
                   "documents": [{"doc": "old", "file": "fixture.txt",
                                  "sha256": hashlib.sha256(fixture.read_bytes()).hexdigest()}],
                   "citations": [{**ref("old", "1.1"), "quote": "Child duty."},
                                 {**ref("old", "1"), "quote": "Parent duty."}]}
            labels = root / "labels.jsonl"
            labels.write_text(json.dumps(row), encoding="utf-8")
            with patch.object(score, "ROOT", root):
                self.assertEqual(len(score.load_labels(labels)), 1)
                row["citations"][1]["quote"] = "Invented context."
                labels.write_text(json.dumps(row), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "Quote outside"):
                    score.load_labels(labels)

    def test_provenance_failure_separate_from_semantic_match(self):
        row = gold()
        finding = prediction(row)
        finding["citations"] = [{**r, "quote": "Invented quote."} for r in row["before"] + row["after"]]
        self.assertEqual(evaluate(row, [finding])["tp"], 1)
        diagnostics = score.citation_diagnostics(report_for(row, [finding]))
        self.assertEqual((diagnostics["citations_checked"], diagnostics["failures"]), (2, 2))

    def test_split_hash_and_membership_are_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            labels = root / "challenge.jsonl"
            labels.write_text("fixture", encoding="utf-8")
            split_file = root / "split.json"
            row = gold()
            split = {"schema_version": 1, "datasets": {"challenge.jsonl": hashlib.sha256(labels.read_bytes()).hexdigest()},
                     "cases": {row["id"]: {"partition": "development", "kind": "synthetic",
                                            "label_sha256": score.label_sha256(row)}}}
            split_file.write_text(json.dumps(split), encoding="utf-8")
            with patch.object(score, "ROOT", root):
                self.assertEqual(score.partitions([row], labels, split_file), {row["id"]: "development"})
                row["expected_status"] = "moved"
                with self.assertRaisesRegex(ValueError, "label hash mismatch"):
                    score.partitions([row], labels, split_file)


if __name__ == "__main__":
    unittest.main()
