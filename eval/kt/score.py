"""Score audit Report JSON against clause-level ground truth.

Usage: python eval/kt/score.py <report.json> [more-report.json ...]
       python eval/kt/score.py --validate-labels
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LABELS = ROOT / "seeds/kt/eval/labels.jsonl"
STATUSES = ("unchanged", "changed", "moved", "added", "missing", "duplicate", "unresolved")


def file_path(name: str) -> Path:
    path = (ROOT / name).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError(f"Fixture outside repository: {name}")
    return path


def clause_text(source: str, clause_id: str) -> str:
    """Return the labelled source line, including embedded numbered markers."""
    if "/" in clause_id:
        section, letter = clause_id.split("/", 1)
        start = re.search(rf"(?m)^{re.escape(section)}\.\s", source)
        if start is None:
            raise ValueError(f"Section absent: {section}")
        tail = source[start.end():]
        end = re.search(r"(?m)^\d+(?:\.\d+)*\.\s", tail)
        scope = tail[:end.start()] if end else tail
        hits = re.findall(rf"(?m)^{re.escape(letter)}\.\s*([^\r\n]*)", scope)
    else:
        hits = re.findall(rf"(?m)^{re.escape(clause_id)}\.\s*([^\r\n]*)", source)
    if len(hits) != 1:
        raise ValueError(f"Expected one {clause_id} clause, found {len(hits)}")
    return hits[0]


def load_labels(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    seen = set()
    for row in rows:
        if row["id"] in seen:
            raise ValueError(f"Duplicate label ID: {row['id']}")
        seen.add(row["id"])
        if row["kind"] not in ("real", "synthetic") or row["expected_status"] not in STATUSES:
            raise ValueError(f"Invalid kind/status: {row['id']}")
        docs = {}
        for doc in row["documents"]:
            path = file_path(doc["file"])
            if hashlib.sha256(path.read_bytes()).hexdigest() != doc["sha256"]:
                raise ValueError(f"Fixture hash mismatch: {row['id']} {doc['file']}")
            docs[doc["doc"]] = path.read_bytes().decode("utf-8-sig")
        refs = {(r["doc"], r["clause_id"]) for r in row["before"] + row["after"]}
        cites = {(c["doc"], c["clause_id"]) for c in row["citations"]}
        if not refs or cites != refs:
            raise ValueError(f"Refs and citations differ: {row['id']}")
        for alias, clause_id in refs:
            clause_text(docs[alias], clause_id)
        for c in row["citations"]:
            if not c["quote"] or c["quote"] not in clause_text(docs[c["doc"]], c["clause_id"]):
                raise ValueError(f"Quote outside cited clause: {row['id']} {c['clause_id']}")
    return rows


def equivalent_hashes(label_doc: dict, kind: str) -> set[str]:
    hashes = {label_doc["sha256"]}
    if kind == "real" and label_doc["file"] in ("seeds/kt/v8.txt", "seeds/kt/v9.txt"):
        docx = file_path(label_doc["file"].removesuffix(".txt") + ".docx")
        hashes.add(hashlib.sha256(docx.read_bytes()).hexdigest())
    return hashes


def report_aliases(row: dict, report: dict) -> dict[str, str] | None:
    """Map Report-local aliases to label aliases using fixture identity."""
    mapping = {}
    used = set()
    for labelled in row["documents"]:
        candidates = [d for d in report["documents"]
                      if d["sha256"] in equivalent_hashes(labelled, row["kind"])]
        if len(candidates) != 1 or candidates[0]["doc"] in used:
            return None
        report_alias = candidates[0]["doc"]
        mapping[report_alias] = labelled["doc"]
        used.add(report_alias)
    if len(report["documents"]) != len(row["documents"]):
        return None
    return mapping


def refs(items: list[dict], aliases: dict[str, str] | None = None) -> frozenset[tuple[str, str]]:
    return frozenset((aliases.get(r["doc"], r["doc"]) if aliases else r["doc"], r["clause_id"])
                     for r in items)


def signature(row: dict, aliases: dict[str, str] | None = None) -> tuple[frozenset, frozenset]:
    return refs(row["before"], aliases), refs(row["after"], aliases)


def format_ratio(numerator: int, denominator: int) -> str:
    return f"{numerator}/{denominator} ({numerator / denominator:.1%})" if denominator else "0/0 (n/a)"


def score_group(kind: str, matched: list[tuple[dict, dict, dict[str, str]]]) -> None:
    print(f"\n{kind}: {len(matched)} labelled cases")
    print("status       precision          recall             abstentions")
    gold = Counter()
    tp = Counter()
    fp = Counter()
    abstained = Counter()
    batches = {}
    for report, row, aliases in matched:
        batch = batches.setdefault(id(report), {"report": report, "cases": [], "aliases": aliases})
        batch["cases"].append(row)
    for batch in batches.values():
        report, cases, aliases = batch["report"], batch["cases"], batch["aliases"]
        wanted = [(row["expected_status"], signature(row)) for row in cases]
        for status, _ in wanted:
            gold[status] += 1
        labelled_refs = set().union(*(before | after for _, (before, after) in wanted))
        claimed = set()
        unresolved_refs = set()
        for finding in report["findings"]:
            status = finding["status"]
            if status not in STATUSES:
                raise ValueError(f"Unknown finding status: {status}")
            candidate = signature(finding, aliases)
            candidate_refs = candidate[0] | candidate[1]
            if not candidate_refs & labelled_refs:
                continue  # The gold set makes no claim about unrelated findings.
            if status == "unresolved":
                unresolved_refs.update(candidate_refs)
                continue
            hit = next((i for i, key in enumerate(wanted)
                        if i not in claimed and key == (status, candidate)), None)
            if hit is None:
                fp[status] += 1
            else:
                claimed.add(hit)
                tp[status] += 1
        for i, (status, (before, after)) in enumerate(wanted):
            if i not in claimed and (before | after) & unresolved_refs:
                abstained[status] += 1
    for status in STATUSES:
        if status == "unresolved" and not gold[status] and not tp[status] and not fp[status]:
            continue
        precision = format_ratio(tp[status], tp[status] + fp[status])
        recall = format_ratio(tp[status], gold[status])
        abstentions = format_ratio(abstained[status], gold[status])
        print(f"{status:<12} {precision:<18} {recall:<18} {abstentions}")
    print(f"TOTAL        gold={sum(gold.values())} tp={sum(tp.values())} fp={sum(fp.values())} "
          f"abstentions={sum(abstained.values())}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="*", type=Path, help="Report JSON files")
    parser.add_argument("--labels", type=Path, default=LABELS)
    parser.add_argument("--validate-labels", action="store_true")
    args = parser.parse_args()
    labels = load_labels(args.labels)
    counts = Counter(row["kind"] for row in labels)
    print(f"Validated {len(labels)} labels: {counts['real']} real, {counts['synthetic']} synthetic; "
          "all fixture hashes, clause refs and quotes resolve")
    if not args.reports:
        if args.validate_labels:
            return
        parser.error("provide at least one Report JSON, or --validate-labels")
    reports = []
    for path in args.reports:
        data = json.loads(path.read_text(encoding="utf-8"))
        if "payload" in data:
            data = data["payload"]
        if not isinstance(data, dict) or not isinstance(data.get("documents"), list) or not isinstance(data.get("findings"), list):
            raise ValueError(f"Not a Report JSON: {path}")
        reports.append(data)
    matched = {"real": [], "synthetic": []}
    for report in reports:
        applicable = [(row, aliases) for row in labels
                      if (aliases := report_aliases(row, report)) is not None]
        if not applicable:
            raise ValueError("No labels match a report's document hashes")
        for row, aliases in applicable:
            matched[row["kind"]].append((report, row, aliases))
    for kind in ("real", "synthetic"):
        score_group(kind, matched[kind])


if __name__ == "__main__":
    main()
