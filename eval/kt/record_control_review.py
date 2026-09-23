"""One-time, versioned source review intake; never confirms human gold."""
import datetime as dt
import hashlib
import json
from pathlib import Path
from score import label_sha256

BASE = Path(__file__).resolve().parents[2] / "seeds/kt/eval"
CONTROL = BASE / "control"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def main():
    record = CONTROL / "review/intake.json"
    if record.exists():
        raise ValueError("Review intake exists; preserve history and make a new amendment")
    labels = CONTROL / "labels.jsonl"
    old_bytes = labels.read_bytes()
    rows = [json.loads(s) for s in old_bytes.decode("utf-8").splitlines()]
    split, reviews = read(BASE / "split.json"), read(BASE / "reviews.json")
    before_sha = sha(labels)
    at = dt.datetime.now(dt.timezone.utc).isoformat()
    # Physical probes established from authored one-paragraph-per-block/cell
    # construction and independent pypdf page inspection, not product output.
    probes = [("ctrl-unit-archive", "before", "1.1/а", 5, 1),
              ("ctrl-unit-archive", "after", "1.1/а", 5, 1),
              ("ctrl-risk-self-control", "after", "7.4", 32, 2)]
    for identifier, side, cid, ordinal, page in probes:
        row = next(r for r in rows if r["id"] == identifier)
        for ext, location in [("docx", {"block": ordinal}), ("pdf", {"page": page}),
                              ("xlsx", {"sheet": "Приложение", "cell_range": f"A{ordinal}"})]:
            row.setdefault("source_locations", []).append({"doc": side + "-1", "clause_id": cid,
                "document_sha256": sha(CONTROL / f"{side}.{ext}"), "location": location})
    labels.write_text("".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n" for r in rows), encoding="utf-8", newline="\n")
    split["datasets"]["seeds/kt/eval/control/labels.jsonl"] = sha(labels)
    review_files = {name: sha(CONTROL / "review" / name) for name in ["structure-and-real.json", "duties-and-risks.json"]}
    for row in rows:
        identifier = row["id"]
        previous = split["cases"][identifier]["label_sha256"]
        split["cases"][identifier]["label_sha256"] = label_sha256(row)
        review = reviews["cases"][identifier]
        review["label_sha256"] = label_sha256(row)
        review["events"].append({"at_utc": at, "type": "independent_AI_source_review_intake",
            "previous_label_sha256": previous, "label_sha256": label_sha256(row),
            "human_source_confirmation": False, "status": "pending_human", "record": "seeds/kt/eval/control/review/intake.json"})
    disagreements = [
        {"id": "dev-real-shared-information", "current_proposal": "changed", "independent_proposal": "moved",
         "evidence": "v8 5.3.5 -> v9 5.3.6 with governing 5.3; separate 5.4.3 already present in both editions",
         "decision": "Keep versioned challenge unchanged pending human decision about preserved duty with changed owner scope."},
        {"id": "dev-real-audit-goals", "current_proposal": "moved", "independent_proposal": "changed",
         "evidence": "v8 9.36/з -> v9 9.36/е; 9.37 changes possible delegate while Chief Auditor remains accountable",
         "decision": "Keep versioned challenge unchanged pending human decision about governing-context boundary."},
    ]
    for dispute in disagreements:
        reviews["cases"][dispute["id"]]["disagreements"].append({**dispute, "at_utc": at,
            "review_file": "seeds/kt/eval/control/review/structure-and-real.json", "human_source_confirmation": False})
    split.setdefault("amendments", []).append({"at_utc": at, "ids": sorted({p[0] for p in probes}),
        "dataset_sha256_before": before_sha, "dataset_sha256_after": sha(labels),
        "decision_file": "seeds/kt/eval/control/review/intake.json", "holdout_unchanged": True,
        "reason": "Add independent physical source-location probes; no status/ref/quote/source bytes changed"})
    (CONTROL / "review/labels-v1-before-location-probes.jsonl").write_bytes(old_bytes)
    write(record, {"at_utc": at, "review_artifact_sha256": review_files,
        "gold_status": "pending_human", "human_confirmed": 0, "control_labels": 19,
        "independence": "Separate built-in Codex reviewers saw source/contract before expectations or product output; procedural shared repo, not technically blind",
        "reviewer_disclosure": "Duties reviewer accidentally read entire stage-3.md; no gold/reports read. Root had authored gold; root is not an independent vote.",
        "source_conclusions": "Structural seven transitions and duty/risk proposals support control expectations; this is label review, not product accuracy.",
        "disagreements": disagreements, "existing_challenge_labels_changed": False,
        "location_probes": {"physical_refs": 3, "format_specific_expectations": 9,
            "method": "DOCX XML block order and XLSX source cell rows; PDF pages separately read using pypdf",
            "added_after_local_domain_capture": True, "local_product_outputs_not_used_to_choose_coordinates": True,
            "no_semantic_labels_changed": True},
        "labels_sha256_before": before_sha, "labels_sha256_after": sha(labels),
        "agent_product_accuracy": "unmeasured; external capture package pending"})
    write(BASE / "split.json", split)
    write(BASE / "reviews.json", reviews)
    print("Recorded review and 9 physical coordinate expectations; all 19 labels pending_human")


if __name__ == "__main__":
    main()
