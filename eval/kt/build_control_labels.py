"""Freeze source-authored Stage 3 proposals, never read product predictions.

Existing gold is never rewritten. Delete nothing: a changed proposal needs a new
version plus an explicit adjudication entry rather than rerunning this command.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
from pathlib import Path
import re

from score import clause_text, label_sha256

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "seeds/kt/eval"
CONTROL = BASE / "control"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    destination = CONTROL / "labels.jsonl"
    if destination.exists():
        raise ValueError("Control labels already frozen; make an explicit versioned adjudication")
    texts = {side + "-1": (CONTROL / (side + ".txt")).read_text(encoding="utf-8") for side in ("before", "after")}
    documents = []
    for side in ("before", "after"):
        path = CONTROL / (side + ".txt")
        documents.append({"doc": side + "-1", "edition": side, "file": path.relative_to(ROOT).as_posix(),
                          "sha256": sha(path), "representations": [
                              {"file": p.relative_to(ROOT).as_posix(), "sha256": sha(p)}
                              for ext in ("docx", "pdf", "xlsx") if (p := CONTROL / (side + "." + ext)).exists()]})

    def ref(side, cid, unit=False):
        return {"doc": side + "-1", "unit_id" if unit else "clause_id": cid}

    def citation(side, cid):
        return {**ref(side, cid), "quote": clause_text(texts[side + "-1"], cid)}

    def unit_evidence(r):
        text = clause_text(texts[r["doc"]], r["unit_id"])
        return {**r, "name": re.sub(r"\s*\([^)]*\)\.$", "", text), "kind": "unit",
                "citations": [{"doc": r["doc"], "clause_id": r["unit_id"], "quote": text}]}

    def base(identifier, target, reason):
        return {"id": "ctrl-" + identifier, "kind": "synthetic", "target": target,
                "documents": documents, "rationale": reason,
                "annotator": "Source-first AI proposal; Alibi human confirmation pending", "mutation": None}

    rows = []
    for identifier, status, before, after, order in [
        ("unit-archive", "retained", ["а"], ["а"], "2.1"),
        ("unit-finance", "retained", ["е"], ["е"], "2.1"),
        ("unit-technical", "retained", ["ж"], ["ж"], "2.1"),
        ("unit-rename", "reorganised", ["б"], ["б"], "2.2"),
        ("unit-split", "reorganised", ["в"], ["в", "г"], "2.3"),
        ("unit-merge", "reorganised", ["г", "д"], ["д"], "2.4"),
        ("unit-created", "created", [], ["з"], "2.5"),
    ]:
        b = [ref("before", "1.1/" + letter, True) for letter in before]
        a = [ref("after", "1.1/" + letter, True) for letter in after]
        evidence = [unit_evidence(r) for r in b + a]
        citations = [c for u in evidence for c in u["citations"]] + [citation("after", order)]
        if status == "created":
            citations += [citation("before", "9.1"), citation("after", "11.1")]
        rows.append({**base(identifier, "unit_change", "Explicit supplied organisational order; identity is not inferred from abbreviations alone."),
                     "before": b, "after": a, "expected_status": status,
                     "unit_evidence": evidence, "citations": citations})

    for identifier, kind, clauses, letters in [
        ("risk-duplication", "potential_duplication", ["4.1", "10.1"], ["б", "з"]),
        ("risk-self-control", "potential_conflict_of_interest", ["7.2", "7.4"], ["д"]),
        ("risk-cooperation-negative", "none", ["8.1", "9.1"], ["е", "ж"]),
    ]:
        units = [ref("after", "1.1/" + letter, True) for letter in letters]
        evidence = [unit_evidence(r) for r in units]
        citations = [citation("after", c) for c in clauses] + [c for u in evidence for c in u["citations"]]
        rows.append({**base(identifier, "risk", {
            "potential_duplication": "Distinct units register all the same requests in one journal without channel, customer or stage separation.",
            "potential_conflict_of_interest": "Supplier choice and approval of that same unit's own choice combine execution and self-review. Advisory potential risk only, not misconduct or legal breach.",
            "none": "Financial budget review and technical design have explicitly distinct scopes; cooperation alone is neither duplicate nor self-control."
        }[kind]), "before": [], "after": [ref("after", c) for c in clauses],
            "refs": [ref("after", c) for c in clauses], "units": units, "unit_evidence": evidence,
            "expected_kind": kind, "citations": citations})

    for identifier, status, before, after, context in [
        ("function-loss", "missing", ["2.2"], [], [("before", "9.1"), ("after", "11.1")]),
        ("function-duplicate", "duplicate", ["3.1"], ["4.1", "10.1"], [("after", "2.2")]),
        ("function-split-intake", "moved", ["4.1"], ["5.1"], [("after", "2.3")]),
        ("function-split-survey", "moved", ["4.2"], ["6.1"], [("after", "2.3")]),
        ("function-merge-contracts", "moved", ["5.1"], ["7.1"], [("after", "2.4")]),
        ("function-merge-stock", "moved", ["6.1"], ["7.3"], [("after", "2.4")]),
        ("function-archive-preserved", "moved", ["2.1"], ["3.1"], [("after", "2.1")]),
        ("function-cooperation-finance", "changed", ["7.2"], ["8.1"], []),
        ("function-cooperation-technical", "changed", ["8.1"], ["9.1"], []),
    ]:
        citations = [citation(side, c) for side, cs in (("before", before), ("after", after)) for c in cs]
        citations += [citation(side, c) for side, c in context]
        rows.append({**base(identifier, "function", {
            "missing": "Annual retention check and act absent throughout complete after set; limited to supplied documents.",
            "duplicate": "Pre-existing request registration now belongs to two units without supplied scope separation; retain both after refs.",
            "moved": "Preserved action transferred/renumbered by explicit order; not a missing function.",
            "changed": "Preserved principal action with new explicit exclusion of the other unit's scope; not duplicate or missing."
        }[status]), "before": [ref("before", c) for c in before], "after": [ref("after", c) for c in after],
            "expected_status": status, "citations": citations})
    destination.write_text("".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n" for r in rows), encoding="utf-8", newline="\n")
    at = dt.datetime.now(dt.timezone.utc).isoformat()
    split = json.loads((BASE / "split.json").read_text(encoding="utf-8"))
    reviews = json.loads((BASE / "reviews.json").read_text(encoding="utf-8"))
    split["datasets"][destination.relative_to(ROOT).as_posix()] = sha(destination)
    for document in documents:
        for item in [document] + document["representations"]:
            split["fixtures"][item["file"]] = item["sha256"]
    for row in rows:
        if row["id"] in split["cases"] or row["id"] in reviews["cases"]:
            raise ValueError("Control ID already exists")
        split["cases"][row["id"]] = {"partition": "development", "kind": "synthetic", "target": row["target"],
            "review_status": "pending_human", "selection": "source-first synthetic Stage3 control", "label_sha256": label_sha256(row)}
        reviews["cases"][row["id"]] = {"status": "pending_human", "label_sha256": label_sha256(row),
            "proposed_by": "Alibi source-first AI", "human_reviewer": None, "human_decision": None,
            "disagreements": [], "events": [{"type": "source_first_proposal", "at_utc": at, "human_source_confirmation": False}]}
    for name, value in (("split.json", split), ("reviews.json", reviews)):
        (BASE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Frozen {len(rows)} provisional source-first labels; existing rows unchanged")


if __name__ == "__main__":
    main()
