"""Evaluate exact reference sets and statuses against source-backed labels.

Precision covers findings intersecting labelled refs, not all Report findings.
Usage: python eval/kt/score.py <report.json> [more-report.json ...]
       python eval/kt/score.py --validate-labels
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LABELS = ROOT / "seeds/kt/eval/labels.jsonl"
SPLIT = ROOT / "seeds/kt/eval/split.json"
STATUSES = ("unchanged", "changed", "moved", "added", "missing", "duplicate", "unresolved")
SEMANTIC_STATUSES = STATUSES[:-1]
PARTITIONS = ("regression", "development", "holdout", "unassigned")


def file_path(name: str) -> Path:
    path = (ROOT / name).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError(f"Fixture outside repository: {name}")
    return path


def _next_number(previous: tuple[int, ...], current: tuple[int, ...]) -> bool:
    return (len(current) <= len(previous) and current[:-1] == previous[:len(current) - 1]
            and current[-1] == previous[len(current) - 1] + 1) or current == previous + (1,)


def _cross_reference(prefix: str) -> bool:
    return bool(re.search(r"(?:\bпп?\.|\bпункт\w*|\bраздел\w*|\bclause|\bsection)\s*$", prefix, re.I))


@lru_cache(maxsize=32)
def source_clauses(source: str) -> dict[str, str | None]:
    """Independent conservative resolver; never import the application's parser.

    Inline numeric markers require sentence-boundary and expected sibling/child
    evidence. Preserve internal whitespace/newlines; reject ambiguous requested
    boundaries. Dates and prose references are text, not numbered clauses.
    """
    marker = re.compile(r"(?<!\w)(?<!\d\.)(?P<number>\d+(?:\.\d+)*)\.(?!\d)|(?m:^[ \t]*(?P<letter>[а-яёa-z])\.)")
    events, ambiguous = [], []
    counts = Counter()
    previous, parent = (), None
    for match in marker.finditer(source):
        prefix = source[source.rfind("\n", 0, match.start()) + 1:match.start()]
        line_start = not prefix.strip(" \t\r\ufeff")
        if match.group("number"):
            base = match.group("number")
            numbers = tuple(map(int, base.split(".")))
            if len(numbers) == 3 and 1 <= numbers[0] <= 31 and 1 <= numbers[1] <= 12 and numbers[2] >= 1900:
                continue
            if not line_start:
                if _cross_reference(prefix):
                    continue
                expected = previous and _next_number(previous, numbers)
                boundary = bool(re.search(r"[.!?;:]\s*$", prefix))
                if not (expected and boundary):
                    if expected:
                        ambiguous.append(match.start())
                    continue
            previous, parent = numbers, base
        else:
            if parent is None:
                continue
            base = parent + "/" + match.group("letter")
        counts[base] += 1
        identifier = base if counts[base] == 1 else f"{base}@{counts[base]}"
        start = match.end()
        while start < len(source) and source[start] in " \t":
            start += 1
        events.append((identifier, match.start(), start))
    result = {}
    for i, (identifier, _, start) in enumerate(events):
        end = events[i + 1][1] if i + 1 < len(events) else len(source)
        result[identifier] = (None if any(start <= offset < end for offset in ambiguous)
                              else source[start:end].rstrip(" \t\r\n"))
    return result


def clause_text(source: str, clause_id: str) -> str:
    clauses = source_clauses(source)
    if clause_id not in clauses:
        raise ValueError(f"Clause absent or unsupported marker: {clause_id}")
    if clauses[clause_id] is None:
        raise ValueError(f"Ambiguous embedded clause boundary in {clause_id}")
    return clauses[clause_id]


def label_sha256(row: dict) -> str:
    """Stable digest: UTF-8, sorted keys, compact JSON, no final newline."""
    return hashlib.sha256(json.dumps(row, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def load_labels(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    seen = set()
    for row in rows:
        if row["id"] in seen:
            raise ValueError(f"Duplicate label ID: {row['id']}")
        seen.add(row["id"])
        if row["kind"] not in ("real", "synthetic") or row["expected_status"] not in STATUSES:
            raise ValueError(f"Invalid kind/status: {row['id']}")
        docs = {}
        for doc in row["documents"]:
            if doc["doc"] in docs:
                raise ValueError(f"Duplicate document alias: {row['id']} {doc['doc']}")
            raw = file_path(doc["file"]).read_bytes()
            if hashlib.sha256(raw).hexdigest() != doc["sha256"]:
                raise ValueError(f"Fixture hash mismatch: {row['id']} {doc['file']}")
            docs[doc["doc"]] = raw.decode("utf-8-sig")
        required, cited = refs(row["before"] + row["after"]), refs(row["citations"])
        if not required or not required <= cited:
            raise ValueError(f"Missing citations for refs: {row['id']}")
        for alias, clause_id in required | cited:
            if alias not in docs:
                raise ValueError(f"Unknown cited document: {row['id']} {alias}")
            clause_text(docs[alias], clause_id)
        for citation in row["citations"]:
            if not citation["quote"] or citation["quote"] not in clause_text(docs[citation["doc"]], citation["clause_id"]):
                raise ValueError(f"Quote outside cited clause: {row['id']} {citation['clause_id']}")
    return rows


def equivalent_hashes(label_doc: dict, kind: str) -> set[str]:
    hashes = {label_doc["sha256"]}
    if kind == "real" and label_doc["file"] in ("seeds/kt/v8.txt", "seeds/kt/v9.txt"):
        docx = file_path(label_doc["file"].removesuffix(".txt") + ".docx")
        hashes.add(hashlib.sha256(docx.read_bytes()).hexdigest())
    return hashes


def report_aliases(row: dict, report: dict) -> dict[str, str] | None:
    """Map Report aliases to label aliases by content identity and edition.

    Different document multiset: inapplicable. Matching multiset but ambiguous
    same-side identity or inconsistent editions: error, never silent exclusion.
    """
    documents = report["documents"]
    if len(documents) != len(row["documents"]):
        return None
    if len({d["doc"] for d in documents}) != len(documents):
        raise ValueError("Duplicate Report document alias")
    candidates = [[i for i, doc in enumerate(documents)
                   if doc["sha256"] in equivalent_hashes(labelled, row["kind"])]
                  for labelled in row["documents"]]

    def solutions(options: list[list[int]]) -> list[tuple[int, ...]]:
        found = []
        def visit(chosen: tuple[int, ...]) -> None:
            if len(found) > 1:
                return
            if len(chosen) == len(options):
                found.append(chosen)
                return
            for candidate in options[len(chosen)]:
                if candidate not in chosen:
                    visit(chosen + (candidate,))
        visit(())
        return found

    if not solutions(candidates):
        return None
    for index, labelled in enumerate(row["documents"]):
        sides = {side for side in ("before", "after")
                 if any(ref["doc"] == labelled["doc"] for ref in row[side])}
        # These aliases carry edition semantics in plan.md's public contract.
        # Arbitrary labels do not; ambiguous arbitrary aliases still fail.
        conventional = re.fullmatch(r"(before|after)-\d+", labelled["doc"])
        named_side = (conventional.group(1) if conventional else
                      {"v8": "before", "v9": "after"}.get(labelled["doc"]))
        if named_side:
            sides.add(named_side)
        if len(sides) > 1:
            raise ValueError(f"Label alias used on both sides: {row['id']} {labelled['doc']}")
        if sides:
            side = next(iter(sides))
            candidates[index] = [i for i in candidates[index] if documents[i].get("edition") == side]
    matches = solutions(candidates)
    if len(matches) != 1:
        raise ValueError(f"Ambiguous/inconsistent document identity or edition: {row['id']}; "
                         "same-side identical files need an explicit disambiguating contract")
    return {documents[i]["doc"]: labelled["doc"]
            for labelled, i in zip(row["documents"], matches[0])}


def refs(items: list[dict], aliases: dict[str, str] | None = None) -> frozenset[tuple[str, str]]:
    return frozenset((aliases.get(r["doc"], r["doc"]) if aliases else r["doc"], r["clause_id"])
                     for r in items)


def signature(row: dict, aliases: dict[str, str] | None = None) -> tuple[frozenset, frozenset]:
    return refs(row["before"], aliases), refs(row["after"], aliases)


def format_ratio(numerator: int, denominator: int) -> str:
    return f"{numerator}/{denominator} ({numerator / denominator:.1%})" if denominator else "0/0 (n/a)"


def citation_diagnostics(report: dict) -> dict:
    """Report-internal provenance, independent of semantic status correctness."""
    clauses = {(c["doc"], c["clause_id"]): c["text"] for c in report.get("clauses", [])}
    errors, checked = [], 0
    for section in ("findings", "conclusion"):
        for index, item in enumerate(report.get(section, [])):
            item_id = item.get("id", str(index))
            cited = refs(item.get("citations", []))
            if section == "findings":
                for key in refs(item["before"] + item["after"]) - cited:
                    errors.append({"item": item_id, "section": section, "error": "uncited_ref", "ref": list(key)})
            for citation in item.get("citations", []):
                checked += 1
                key = citation["doc"], citation["clause_id"]
                if key not in clauses or not citation.get("quote") or citation["quote"] not in clauses[key]:
                    errors.append({"item": item_id, "section": section, "error": "quote_not_in_report_clause", "ref": list(key)})
    return {"scope": "Report.clauses only; not proof of source extraction completeness or semantic truth",
            "citations_checked": checked, "failures": len(errors),
            "duplicate_clause_keys": len(report.get("clauses", [])) - len(clauses), "errors": errors}


def score_group(name: str, matched: list[tuple[dict, dict, dict[str, str]]]) -> dict:
    gold, tp, fp, abstained, counts = Counter(), Counter(), Counter(), Counter(), Counter()
    errors, batches = [], {}
    for report, row, aliases in matched:
        batch = batches.setdefault(id(report), {"report": report, "cases": []})
        canonical = signature(row, {label: report_alias for report_alias, label in aliases.items()})
        batch["cases"].append((row, canonical))
    for batch in batches.values():
        report, cases = batch["report"], batch["cases"]
        wanted = [(row["expected_status"], key) for row, key in cases]
        for status, _ in wanted:
            if status == "unresolved":
                counts["appropriate_abstention_gold"] += 1
            else:
                gold[status] += 1
        labelled_refs = set().union(*(before | after for _, (before, after) in wanted))
        claimed, appropriate, scoped = set(), set(), []
        for index, finding in enumerate(report["findings"]):
            counts["findings_total"] += 1
            status, candidate = finding["status"], signature(finding)
            candidate_refs = candidate[0] | candidate[1]
            if status not in STATUSES:
                counts["unknown_status_findings"] += 1
            if not candidate_refs & labelled_refs:
                counts["unlabelled_findings"] += 1
                continue
            counts["scoped_findings"] += 1
            scoped.append((index, finding, candidate))
            if status == "unresolved":
                counts["scoped_unresolved_findings"] += 1
                hit = next((i for i, key in enumerate(wanted)
                            if i not in appropriate and key == (status, candidate)), None)
                if hit is not None:
                    appropriate.add(hit)
                    counts["appropriate_abstention_matches"] += 1
                else:
                    counts["other_unresolved_findings"] += 1
                continue
            if status not in SEMANTIC_STATUSES:
                continue
            hit = next((i for i, key in enumerate(wanted)
                        if i not in claimed and key == (status, candidate)), None)
            if hit is None:
                fp[status] += 1
            else:
                claimed.add(hit)
                tp[status] += 1
        report_refs = refs(report.get("clauses", []))
        for i, (row, wanted_refs) in enumerate(cases):
            status = row["expected_status"]
            case_refs = wanted_refs[0] | wanted_refs[1]
            overlaps = [(f, key) for _, f, key in scoped if case_refs & (key[0] | key[1])]
            unresolved = [(f, key) for f, key in overlaps if f["status"] == "unresolved"]
            exact_unresolved = any(key == wanted_refs for _, key in unresolved)
            if i not in claimed and unresolved:
                abstained[status] += 1  # Historical overlap diagnostic, not semantic TP.
            if i not in claimed and any(key != wanted_refs for _, key in unresolved):
                counts["partial_overlap_refusal_labels"] += 1
            case_errors = []
            missing_refs = case_refs - report_refs
            if missing_refs:
                case_errors.append("parsing_omission")
            if any(f["status"] not in STATUSES for f, _ in overlaps):
                case_errors.append("unknown_status_prediction")
            resolved = [(f, key) for f, key in overlaps if f["status"] in SEMANTIC_STATUSES]
            if status == "unresolved":
                if resolved:
                    case_errors.append("unsupported_resolution")
                if i not in appropriate:
                    case_errors.append("wrong_abstention_refs" if unresolved else "no_appropriate_abstention")
            elif i not in claimed:
                if unresolved:
                    case_errors.append("abstention_on_resolvable")
                if any(key == wanted_refs and f["status"] != status for f, key in resolved):
                    case_errors.append("wrong_status")
                if any(key != wanted_refs for _, key in resolved):
                    case_errors.append("wrong_match")
                if not overlaps:
                    case_errors.append("no_prediction")
            if i in claimed and any((f["status"], key) != (status, wanted_refs) for f, key in resolved):
                case_errors.append("extra_conflicting_prediction")
            if i in claimed and sum((f["status"], key) == (status, wanted_refs) for f, key in resolved) > 1:
                case_errors.append("extra_duplicate_prediction")
            if case_errors:
                errors.append({"label_id": row["id"], "run_id": report.get("run_id"),
                               "categories": case_errors, "missing_report_refs": [list(r) for r in sorted(missing_refs)],
                               "exact_ref_abstention": exact_unresolved,
                               "finding_ids": [f.get("id") for f, _ in overlaps]})
    statuses = {status: {"gold": gold[status], "tp": tp[status], "fp": fp[status],
                         "fn": gold[status] - tp[status],
                         "precision_denominator": tp[status] + fp[status],
                         "recall_denominator": gold[status], "overlap_abstentions": abstained[status]}
                for status in SEMANTIC_STATUSES}
    error_counts = Counter(category for error in errors for category in error["categories"])
    result = {"group": name, "label_evaluations": len(matched), "statuses": statuses,
              "semantic_gold": sum(gold.values()), "tp": sum(tp.values()), "fp": sum(fp.values()),
              "fn": sum(gold.values()) - sum(tp.values()),
              "counts": {key: counts[key] for key in (
                  "findings_total", "scoped_findings", "unlabelled_findings", "unknown_status_findings",
                  "scoped_unresolved_findings", "appropriate_abstention_gold", "appropriate_abstention_matches",
                  "other_unresolved_findings", "partial_overlap_refusal_labels")},
              "error_counts": dict(error_counts), "errors": errors,
              "candidate_recall": "unmeasured: Report does not expose complete candidate sets",
              "extraction_completeness": "unmeasured: missing gold refs checks only labelled source points"}
    print(f"\n{name}: {len(matched)} label evaluations")
    print("status       TP FP FN gold precision          recall             overlap abstentions")
    for status, values in statuses.items():
        print(f"{status:<12} {values['tp']:2} {values['fp']:2} {values['fn']:2} {values['gold']:4} "
              f"{format_ratio(values['tp'], values['precision_denominator']):<18} "
              f"{format_ratio(values['tp'], values['gold']):<18} "
              f"{format_ratio(values['overlap_abstentions'], values['gold'])}")
    print(f"TOTAL semantic_gold={result['semantic_gold']} tp={result['tp']} fp={result['fp']} fn={result['fn']}")
    print("Appropriate abstention (exact refs; separate from semantic TP): "
          + format_ratio(counts['appropriate_abstention_matches'], counts['appropriate_abstention_gold']))
    print("Counts: " + json.dumps(result["counts"], sort_keys=True))
    print("Errors (categories may overlap): " + json.dumps(dict(error_counts), sort_keys=True))
    return result


def partitions(labels: list[dict], label_path: Path, split_path: Path = SPLIT) -> dict[str, str]:
    if not split_path.exists():
        if label_path.name == "challenge.jsonl":
            raise ValueError("Challenge requires split.json membership; no implicit holdout")
        return {row["id"]: "unassigned" for row in labels}
    split = json.loads(split_path.read_text(encoding="utf-8-sig"))
    if split.get("schema_version") != 1:
        raise ValueError("Unsupported split.json schema_version")
    relative = label_path.resolve().relative_to(ROOT).as_posix()
    if label_path.name == "challenge.jsonl" and relative not in split.get("datasets", {}):
        raise ValueError(f"Challenge dataset hash absent from split: {relative}")
    if relative in split.get("datasets", {}):
        if hashlib.sha256(label_path.read_bytes()).hexdigest() != split["datasets"][relative]:
            raise ValueError(f"Split dataset hash mismatch: {relative}")
    membership = {}
    for row in labels:
        case = split.get("cases", {}).get(row["id"])
        if case is None:
            if label_path.name == "challenge.jsonl":
                raise ValueError(f"Challenge case absent from split: {row['id']}")
            membership[row["id"]] = "unassigned"
            continue
        if case["partition"] not in PARTITIONS or case["kind"] != row["kind"]:
            raise ValueError(f"Invalid split membership: {row['id']}")
        if case["label_sha256"] != label_sha256(row):
            raise ValueError(f"Split label hash mismatch: {row['id']}")
        membership[row["id"]] = case["partition"]
    return membership


def review_states(labels: list[dict], split_path: Path = SPLIT) -> dict[str, str]:
    """Surface review custody; computing agreement cannot confirm human review."""
    cases = (json.loads(split_path.read_text(encoding="utf-8-sig")).get("cases", {})
             if split_path.exists() else {})
    return {row["id"]: cases.get(row["id"], {}).get("review_status", "unrecorded") for row in labels}


def require_reviewed_holdout(labels: list[dict], membership: dict[str, str], reviews: dict[str, str]) -> None:
    """Do not reveal holdout agreement before source review confirms the gold."""
    if any(membership[row["id"]] == "holdout"
           and reviews.get(row["id"]) not in ("confirmed", "legacy_accepted") for row in labels):
        raise ValueError("Holdout scoring requires confirmed human source review; "
                         "use --partition development until Alibi confirms holdout")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="*", type=Path, help="Report JSON files")
    parser.add_argument("--labels", type=Path, default=LABELS)
    parser.add_argument("--validate-labels", action="store_true")
    parser.add_argument("--partition", choices=PARTITIONS)
    parser.add_argument("--json-out", type=Path, help="Save this evaluator's metrics as JSON")
    args = parser.parse_args()
    labels = load_labels(args.labels)
    membership = partitions(labels, args.labels)
    if args.partition:
        labels = [row for row in labels if membership[row["id"]] == args.partition]
        if not labels:
            raise ValueError(f"No labels in partition: {args.partition}")
    counts = Counter(row["kind"] for row in labels)
    reviews = review_states(labels)
    print(f"Validated {len(labels)} labels: {counts['real']} real, {counts['synthetic']} synthetic; "
          "all fixture hashes, clause refs and quotes resolve")
    print("Human review: " + json.dumps(dict(Counter(reviews.values())), sort_keys=True)
          + "; pending/unrecorded labels yield provisional agreement, not confirmed human gold")
    if not args.reports:
        if args.validate_labels:
            return
        parser.error("provide at least one Report JSON, or --validate-labels")
    matched, diagnostics, evaluated = {}, [], set()
    for path in args.reports:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if "payload" in data:
            data = data["payload"]
        if not isinstance(data, dict) or not isinstance(data.get("documents"), list) or not isinstance(data.get("findings"), list):
            raise ValueError(f"Not a Report JSON: {path}")
        applicable = [(row, aliases) for row in labels
                      if (aliases := report_aliases(row, data)) is not None]
        if not applicable:
            raise ValueError(f"No selected labels match a report's document hashes: {path}")
        require_reviewed_holdout([row for row, _ in applicable], membership, reviews)
        diagnostics.append({"report": str(path), "run_id": data.get("run_id"), **citation_diagnostics(data)})
        for row, aliases in applicable:
            group = membership[row["id"]] + "/" + row["kind"]
            matched.setdefault(group, []).append((data, row, aliases))
            evaluated.add(row["id"])
    groups = []
    for group, cases in sorted(matched.items()):
        result = score_group(group, cases)
        result["review_status_counts"] = dict(Counter(reviews[row["id"]] for _, row, _ in cases))
        groups.append(result)
    metrics = {"schema_version": 1, "labels_file": str(args.labels),
               "scope": "Exact refs/status; precision only on intersecting labelled refs; appropriate abstention separate",
               "group_counts_scope": "Each partition/kind has its own intersecting-ref scope; do not sum unlabelled counts across groups",
               "groups": groups,
               "provenance": diagnostics,
               "unevaluated_label_ids": [row["id"] for row in labels if row["id"] not in evaluated]}
    for item in diagnostics:
        print(f"Provenance {item['report']}: checked={item['citations_checked']} failures={item['failures']} "
              f"duplicate_clause_keys={item['duplicate_clause_keys']} (Report-internal only)")
    print(f"Selected labels without a matching report: {len(metrics['unevaluated_label_ids'])}")
    print("Unlabelled findings, candidate recall and full-source extraction completeness are unmeasured.")
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
