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


def unit_ref(doc, unit):
    return {"doc": doc, "unit_id": unit}


def domain_gold(target="unit_change", expected=None):
    if target == "risk":
        return {"id": "risk-1", "target": target, "kind": "synthetic", "expected_kind": expected or "potential_duplication",
                "refs": [ref("new", "2.1"), ref("new", "2.2")],
                "units": [unit_ref("new", "1.1"), unit_ref("new", "1.2")]}
    return {"id": "unit-1", "target": target, "kind": "synthetic", "expected_status": expected or "reorganised",
            "before": [unit_ref("old", "1.1")], "after": [unit_ref("new", "1.1"), unit_ref("new", "1.2")]}


def domain_prediction(row, expected=None):
    if row["target"] == "risk":
        return {"id": "risk-output", "kind": expected or row["expected_kind"], "refs": copy.deepcopy(row["refs"]),
                "units": copy.deepcopy(row["units"]), "citations": [], "review_required": True}
    return {"id": "unit-output", "status": expected or row["expected_status"],
            "before": copy.deepcopy(row["before"]), "after": copy.deepcopy(row["after"]), "citations": []}


def agent_execution(status="not_requested"):
    return {"status": status, "model": None, "turns": 0, "tool_calls": 0,
            "investigated_finding_ids": [], "stop_reason": "Scorer unit-test fixture; no inference"}


def domain_evaluate(row, outputs, absent=False):
    report = {"run_id": "stage3-test", "clauses": [], "documents": [], "agent": agent_execution()}
    if not absent:
        report["risks" if row["target"] == "risk" else "unit_changes"] = outputs
    with contextlib.redirect_stdout(io.StringIO()):
        return score.score_group("development/synthetic/" + row["target"], [(report, row, {"old": "old", "new": "new"})])


class Stage3ScoringTests(unittest.TestCase):
    def test_unit_nm_exact_set_and_partial_failure(self):
        row = domain_gold()
        row["before"].append(unit_ref("old", "1.2"))
        prediction = domain_prediction(row)
        prediction["before"].reverse()
        prediction["after"].reverse()
        self.assertEqual(domain_evaluate(row, [prediction])["tp"], 1)
        prediction["after"].pop()
        result = domain_evaluate(row, [prediction])
        self.assertEqual((result["tp"], result["fp"], result["fn"]), (0, 1, 1))

    def test_unit_side_swap_is_not_a_match(self):
        row = domain_gold()
        prediction = domain_prediction(row)
        prediction["before"], prediction["after"] = prediction["after"], prediction["before"]
        self.assertEqual(domain_evaluate(row, [prediction])["tp"], 0)

    def test_missing_or_null_sections_are_not_assessed(self):
        for target in ("unit_change", "risk"):
            row = domain_gold(target)
            for outputs, absent in ((None, True), (None, False), ({"invalid": "section"}, False)):
                result = domain_evaluate(row, outputs, absent)
                self.assertEqual((result["tp"], result["fp"], result["fn"], result["semantic_gold"]), (0, 0, 0, 0))
                self.assertEqual(result["counts"]["not_assessed_labels"], 1)
            report = {"risks": {"invalid": "section"}, "unit_changes": {"invalid": "section"}}
            self.assertEqual(score.citation_diagnostics(report)["stage3_sections"],
                             {"risks": "not_assessed", "unit_changes": "not_assessed"})
            result = domain_evaluate(row, [])
            self.assertEqual((result["semantic_gold"], result["fn"]), (1, 1))

    def test_unit_appropriate_abstention_stays_separate(self):
        row = domain_gold(expected="unresolved")
        result = domain_evaluate(row, [domain_prediction(row)])
        self.assertEqual((result["tp"], result["semantic_gold"]), (0, 0))
        self.assertEqual(result["counts"]["appropriate_abstention_matches"], 1)
        prediction = domain_prediction(row)
        prediction["after"].pop()
        result = domain_evaluate(row, [prediction])
        self.assertEqual(result["counts"]["appropriate_abstention_matches"], 0)
        self.assertEqual(result["error_counts"]["wrong_abstention_refs"], 1)

    def test_historical_agent_default_cannot_yield_risk_true_negative_or_unit_fn(self):
        for target, expected in (("unit_change", "retained"), ("risk", "none"), ("risk", "potential_duplication")):
            row = domain_gold(target, expected)
            section = "unit_changes" if target == "unit_change" else "risks"
            for marker in (None, {}, "not_requested", {"status": "not_requested"}):
                report = {section: [], "agent": marker}
                with contextlib.redirect_stdout(io.StringIO()):
                    result = score.score_group("test", [(report, row, {"old": "old", "new": "new"})])
                self.assertEqual(result["counts"]["not_assessed_labels"], 1)
                self.assertEqual((result["semantic_gold"], result["fn"], result["counts"]["negative_gold"],
                                  result["counts"]["negative_correct"]), (0, 0, 0, 0))
                self.assertEqual(score.citation_diagnostics(report)["stage3_sections"][section], "not_assessed")
            report = {section: []}
            self.assertFalse(score.stage3_assessed(report, section))
            for status in score.AGENT_STATUSES:
                report["agent"] = agent_execution(status)
                self.assertTrue(score.stage3_assessed(report, section))

    def test_missing_agent_does_not_change_function_metrics(self):
        row = gold()
        self.assertEqual(evaluate(row, [prediction(row)])["tp"], 1)

    def test_unit_abstention_on_resolvable_is_fn(self):
        row = domain_gold()
        result = domain_evaluate(row, [domain_prediction(row, "unresolved")])
        self.assertEqual((result["tp"], result["fn"]), (0, 1))
        self.assertEqual(result["counts"]["abstention_on_resolvable"], 1)

    def test_risk_kind_and_unit_sets_are_required(self):
        row = domain_gold("risk")
        prediction = domain_prediction(row, "potential_conflict_of_interest")
        result = domain_evaluate(row, [prediction])
        self.assertEqual((result["tp"], result["fp"], result["fn"]), (0, 1, 1))
        self.assertEqual(result["error_counts"]["wrong_risk_kind"], 1)
        prediction = domain_prediction(row)
        prediction["units"].pop()
        result = domain_evaluate(row, [prediction])
        self.assertEqual((result["tp"], result["fp"], result["fn"]), (0, 1, 1))

    def test_negative_catches_both_risk_kinds_without_semantic_tp(self):
        row = domain_gold("risk", "none")
        result = domain_evaluate(row, [])
        self.assertEqual((result["semantic_gold"], result["tp"], result["counts"]["negative_correct"]), (0, 0, 1))
        for kind in score.RISK_KINDS:
            result = domain_evaluate(row, [domain_prediction(row, kind)])
            self.assertEqual((result["fp"], result["counts"]["negative_violations"]), (1, 1))
        result = domain_evaluate(row, [], absent=True)
        self.assertEqual(result["counts"]["negative_gold"], 0)

    def test_risk_empty_is_not_appropriate_abstention(self):
        result = domain_evaluate(domain_gold("risk"), [])
        self.assertEqual((result["fn"], result["counts"]["appropriate_abstention_gold"]), (1, 0))

    def test_unknown_and_duplicate_predictions_degrade_precision(self):
        for target in ("unit_change", "risk"):
            row = domain_gold(target)
            prediction = domain_prediction(row)
            result = domain_evaluate(row, [prediction, copy.deepcopy(prediction)])
            self.assertEqual((result["tp"], result["fp"]), (1, 1))
            result = domain_evaluate(row, [prediction, domain_prediction(row, "invented")])
            self.assertEqual((result["tp"], result["fp"], result["precision_denominator"]), (1, 1, 2))

    def test_unlabelled_risks_are_unmeasured(self):
        row = domain_gold("risk")
        unrelated = domain_prediction(row)
        unrelated["refs"] = [ref("new", "99")]
        result = domain_evaluate(row, [domain_prediction(row), unrelated])
        self.assertEqual((result["tp"], result["fp"], result["counts"]["unlabelled_outputs"]), (1, 0, 1))

    def test_output_types_cannot_share_denominator(self):
        with self.assertRaisesRegex(ValueError, "Score output types separately"):
            score.score_group("mixed", [({}, gold(), {}), ({}, domain_gold(), {})])

    def test_risk_aliases_identical_bytes_edition(self):
        row = domain_gold("risk")
        row["documents"] = [{"doc": "old", "file": "a", "sha256": "same", "edition": "before"},
                            {"doc": "new", "file": "a", "sha256": "same", "edition": "after"}]
        report = {"documents": [{"doc": "x", "sha256": "same", "edition": "after"},
                                {"doc": "y", "sha256": "same", "edition": "before"}]}
        self.assertEqual(score.report_aliases(row, report), {"y": "old", "x": "new"})
        report["documents"][0]["edition"] = "before"
        with self.assertRaisesRegex(ValueError, "Ambiguous/inconsistent"):
            score.report_aliases(row, report)

    def test_unit_aliases_canonicalised_per_case(self):
        row = domain_gold()
        report = {"unit_changes": [domain_prediction(row)], "agent": agent_execution()}
        renamed = copy.deepcopy(row)
        for side in ("before", "after"):
            for item in renamed[side]:
                item["doc"] += "-label"
        with contextlib.redirect_stdout(io.StringIO()):
            result = score.score_group("test", [(report, renamed, {"old": "old-label", "new": "new-label"})])
        self.assertEqual(result["tp"], 1)

    def test_zero_denominator_is_na(self):
        self.assertEqual(score.format_ratio(0, 0), "0/0 (n/a)")

    def test_stage3_requires_registered_split_and_preserves_holdout_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            labels = root / "stage3.jsonl"
            labels.write_text("fixed source-first labels", encoding="utf-8")
            split_file = root / "split.json"
            row = domain_gold()
            with patch.object(score, "ROOT", root):
                with self.assertRaisesRegex(ValueError, "requires split.json"):
                    score.partitions([row], labels, split_file)
                split = {"schema_version": 1, "datasets": {}, "cases": {}}
                split_file.write_text(json.dumps(split), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "dataset hash absent"):
                    score.partitions([row], labels, split_file)
                split["datasets"]["stage3.jsonl"] = hashlib.sha256(labels.read_bytes()).hexdigest()
                split_file.write_text(json.dumps(split), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "case absent"):
                    score.partitions([row], labels, split_file)
                split["cases"][row["id"]] = {"partition": "holdout", "kind": "synthetic",
                                              "label_sha256": score.label_sha256(row), "review_status": "pending_human"}
                split_file.write_text(json.dumps(split), encoding="utf-8")
                membership = score.partitions([row], labels, split_file)
                with self.assertRaisesRegex(ValueError, "confirmed human source review"):
                    score.require_reviewed_holdout([row], membership, score.review_states([row], split_file))


class Stage3ProvenanceTests(unittest.TestCase):
    def test_conclusion_links_resolve_by_output_type_without_requiring_generic_links(self):
        report = {"agent": agent_execution(),
                  "findings": [{"id": "f", "before": [], "after": [], "citations": []}],
                  "unit_changes": [{"id": "u", "before": [], "after": [], "citations": []}],
                  "risks": [{"id": "r", "refs": [], "units": [], "citations": [], "review_required": True}],
                  "conclusion": [{"text": "Generic advisory recommendation", "citations": []},
                                 {"text": "Linked result", "finding_ids": ["f"], "unit_change_ids": ["u"], "risk_ids": ["r"]}]}
        def link_errors():
            return [e for e in score.citation_diagnostics(report)["errors"] if e["error"] == "unknown_conclusion_link"]
        self.assertEqual(link_errors(), [])
        report["conclusion"][1]["finding_ids"].append("u")  # Existing ID in wrong namespace.
        report["conclusion"][1]["unit_change_ids"].append("missing-unit")
        report["conclusion"][1]["risk_ids"].append("missing-risk")
        self.assertEqual({(e["field"], e["target_id"]) for e in link_errors()},
                         {("finding_ids", "u"), ("unit_change_ids", "missing-unit"), ("risk_ids", "missing-risk")})

    def test_risk_review_and_after_edition_are_independent(self):
        row = domain_gold("risk")
        prediction = domain_prediction(row)
        prediction["review_required"] = False
        report = {"risks": [prediction], "documents": [{"doc": "new", "edition": "before"}]}
        errors = score.citation_diagnostics(report)["errors"]
        categories = {item["error"] for item in errors}
        self.assertTrue({"risk_not_review_required", "risk_not_after", "unit_not_in_report", "uncited_ref"} <= categories)
        self.assertEqual(domain_evaluate(row, [prediction])["tp"], 1)  # Separate semantic agreement.

    def test_unit_cannot_be_a_role_and_needs_defining_citation(self):
        row = domain_gold()
        report = {"unit_changes": [domain_prediction(row)],
                  "units": [{**item, "kind": "role", "citations": []} for item in row["before"] + row["after"]],
                  "documents": [{"doc": "old", "edition": "before"}, {"doc": "new", "edition": "after"}]}
        categories = {item["error"] for item in score.citation_diagnostics(report)["errors"]}
        self.assertIn("role_used_as_structural_unit", categories)
        self.assertIn("uncited_unit_definition", categories)

    def test_quotes_on_new_sections_are_verified(self):
        row = domain_gold("risk")
        prediction = domain_prediction(row)
        prediction["citations"] = [{**ref("new", "2.1"), "quote": "Invented"}]
        report = {"risks": [prediction], "clauses": [{**ref("new", "2.1"), "text": "Real"}]}
        diagnostic = score.citation_diagnostics(report)
        self.assertEqual(diagnostic["citations_checked"], 1)
        self.assertIn("quote_not_in_report_clause", {e["error"] for e in diagnostic["errors"]})

    def test_source_locations_compare_exact_representation(self):
        row = domain_gold()
        row["source_locations"] = [{**ref("new", "1.1"), "location": {"sheet": "Units", "cell_range": "A2:B2"},
                                    "document_sha256": "xlsx"}]
        report = {"unit_changes": [domain_prediction(row)], "agent": agent_execution(), "documents": [{"doc": "new", "sha256": "xlsx"}],
                  "clauses": [{**ref("new", "1.1"), "location": {"sheet": "Units", "cell_range": "A2:B2"}}]}
        def result():
            with contextlib.redirect_stdout(io.StringIO()):
                return score.score_group("test", [(report, row, {"new": "new", "old": "old"})])
        self.assertEqual(result()["counts"]["source_locations_matched"], 1)
        report["clauses"][0]["location"]["cell_range"] = "A3:B3"
        self.assertEqual(len(result()["source_location_errors"]), 1)
        report["documents"][0]["sha256"] = "docx"
        self.assertEqual(result()["counts"]["source_locations_expected"], 0)

    def test_invalid_source_location_shape(self):
        for location in ({"page": 0}, {"page": True}, {"block": -1}, {"block": 0}, {"sheet": ""}, {"invented": 2}):
            with self.subTest(location=location), self.assertRaises(ValueError):
                score.validate_location(location)
        score.validate_location({"page": None, "block": 1, "sheet": "Units", "cell_range": "A1"})

    def test_source_location_missing_is_visible_when_domain_not_assessed(self):
        row = domain_gold()
        row["source_locations"] = [{**ref("new", "1.1"), "location": {"page": 1}}]
        result = domain_evaluate(row, [], absent=True)
        self.assertEqual(result["counts"]["not_assessed_labels"], 1)
        self.assertEqual((result["counts"]["source_locations_matched"], result["counts"]["source_locations_expected"]), (0, 1))
        self.assertEqual(len(result["source_location_errors"]), 1)

    def test_function_locations_are_checked_separately_from_semantics(self):
        row = gold()
        row["source_locations"] = [{**ref("new", "1.1"), "location": {"block": 3}}]
        result = evaluate(row, [prediction(row)])
        self.assertEqual(result["tp"], 1)
        self.assertEqual((result["source_locations"]["matched"], result["source_locations"]["expected"]), (0, 1))

    def test_risk_unit_definition_need_not_be_duplicated_in_risk_citations(self):
        row = domain_gold("risk")
        prediction = domain_prediction(row)
        prediction["citations"] = [{**item, "quote": "Duty"} for item in row["refs"]]
        report = {"risks": [prediction], "documents": [{"doc": "new", "edition": "after"}],
                  "units": [{**item, "kind": "unit", "citations": [{**ref("new", item["unit_id"]), "quote": "Unit"}]}
                            for item in row["units"]],
                  "clauses": [{**item, "text": "Duty"} for item in row["refs"]]
                             + [{**ref("new", item["unit_id"]), "text": "Unit"} for item in row["units"]]}
        self.assertEqual(score.citation_diagnostics(report)["failures"], 0)
        report["units"][0]["citations"] = []
        self.assertIn("uncited_unit_definition", {e["error"] for e in score.citation_diagnostics(report)["errors"]})

    def test_source_quotes_cannot_be_forged_with_report_clause(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source.txt").write_bytes(b"1. Real source.\r\nContinuation.\r\n")
            row = {"documents": [{"doc": "new", "file": "source.txt"}]}
            report = {"risks": [{"id": "r", "citations": [{**ref("upload", "1"), "quote": "Invented source."}]}],
                      "clauses": [{**ref("upload", "1"), "text": "Invented source."}]}
            with patch.object(score, "ROOT", root):
                result = score.source_diagnostics(report, row, {"upload": "new"})
                self.assertEqual((result["citations_checked"], result["failures"]), (1, 1))
                report["risks"][0]["citations"][0]["quote"] = "Real source.\r\nContinuation."
                self.assertEqual(score.source_diagnostics(report, row, {"upload": "new"})["failures"], 0)

    def test_stage3_label_sources_and_representation_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source.txt").write_bytes(b"1. Unit A.\n2. Duty A.\n")
            (root / "source.pdf").write_bytes(b"frozen test representation")
            row = {"id": "risk-label", "kind": "synthetic", "target": "risk", "expected_kind": "none",
                   "documents": [{"doc": "new", "file": "source.txt", "edition": "after",
                                  "sha256": hashlib.sha256((root / "source.txt").read_bytes()).hexdigest(),
                                  "representations": [{"file": "source.pdf", "sha256": hashlib.sha256((root / "source.pdf").read_bytes()).hexdigest()}]}],
                   "refs": [ref("new", "2")], "units": [unit_ref("new", "1")],
                   "unit_evidence": [{**unit_ref("new", "1"), "name": "Unit A", "kind": "unit",
                                      "citations": [{**ref("new", "1"), "quote": "Unit A."}]}],
                   "citations": [{**ref("new", "1"), "quote": "Unit A."}, {**ref("new", "2"), "quote": "Duty A."}]}
            labels = root / "labels.jsonl"
            def write():
                labels.write_text(json.dumps(row), encoding="utf-8")
            write()
            with patch.object(score, "ROOT", root):
                self.assertEqual(len(score.load_labels(labels)), 1)
                digest = row["documents"][0]["representations"][0]["sha256"]
                self.assertEqual(score.report_aliases(row, {"documents": [{"doc": "x", "sha256": digest, "edition": "after"}]}), {"x": "new"})
                row["source_locations"] = [{**ref("new", "1"), "location": {"page": 1}, "document_sha256": "mistyped"}]
                write()
                with self.assertRaisesRegex(ValueError, "not a pinned representation"):
                    score.load_labels(labels)
                row["source_locations"][0]["document_sha256"] = digest
                write()
                self.assertEqual(len(score.load_labels(labels)), 1)
                row["source_locations"][0]["location"] = {}
                write()
                with self.assertRaisesRegex(ValueError, "Empty expected source location"):
                    score.load_labels(labels)
                row.pop("source_locations")
                row["unit_evidence"][0]["name"] = "Invented Unit"
                write()
                with self.assertRaisesRegex(ValueError, "Unit name outside"):
                    score.load_labels(labels)
                row["unit_evidence"][0]["name"] = "Unit A"
                write()
                (root / "source.pdf").write_bytes(b"modified")
                with self.assertRaisesRegex(ValueError, "Representation hash mismatch"):
                    score.load_labels(labels)


if __name__ == "__main__":
    unittest.main()
