"""Archive actual deterministic domain captures and scorer degradation evidence.

No HTTP/provider call. Uses score.py for every metric, not another evaluator.
"""
import copy
import hashlib
import json
from pathlib import Path
import shutil
from score import load_labels, report_aliases, score_group

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "seeds/kt/eval"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    target = BASE / "results/stage3-domain-reports"
    target.mkdir(exist_ok=True)
    rows = load_labels(BASE / "control/labels.jsonl")
    records = []
    for extension in ("txt", "docx", "pdf", "xlsx"):
        source_dir = BASE / "data" / ("stage3-domain-" + extension)
        manifest = json.loads((source_dir / "capture-manifest.json").read_text(encoding="utf-8"))
        original = ROOT / manifest["reports"][0]["file"]
        archived = target / (extension + ".json")
        if archived.exists() and archived.read_bytes() != original.read_bytes():
            raise ValueError("Refuse to overwrite archived raw run")
        shutil.copyfile(original, archived)
        metrics_path = BASE / "results" / ("stage3-domain-" + extension + ".json")
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        records.append({"format": extension, "capture": manifest, "archived_report": archived.relative_to(ROOT).as_posix(),
            "archived_report_sha256": sha(archived), "metrics_file": metrics_path.relative_to(ROOT).as_posix(),
            "metrics_sha256": sha(metrics_path), "groups": [{k: g[k] for k in ("group", "tp", "fp", "fn", "semantic_gold", "counts")} for g in metrics["groups"]],
            "provenance": [{"citations_checked": p["citations_checked"], "failures": p["failures"],
                            "source_checked": p["source_backed"]["citations_checked"], "source_failures": p["source_backed"]["failures"]} for p in metrics["provenance"]]})
    report = json.loads((target / "txt.json").read_text(encoding="utf-8"))
    altered = copy.deepcopy(report)
    missing = next(f for f in altered["findings"] if f["status"] == "missing" and f["before"] == [{"doc": "before-1", "clause_id": "2.2"}])
    missing["status"] = "changed"
    labels = [r for r in rows if r["target"] == "function"]
    def evaluate(value, name):
        return score_group(name, [(value, row, report_aliases(row, value)) for row in labels])
    baseline = evaluate(report, "real captured baseline for scorer control")
    damaged = evaluate(altered, "deliberately corrupted scorer control, NOT product output")
    assert (baseline["tp"], baseline["fp"], baseline["fn"]) == (4, 6, 5)
    assert (damaged["tp"], damaged["fp"], damaged["fn"]) == (3, 7, 6)
    result = {"scope": "Local public deterministic domain API; no HTTP, no model/agent run; Stage2 core only",
        "labels_sha256": sha(BASE / "control/labels.jsonl"), "evaluator_sha256": sha(ROOT / "eval/kt/score.py"),
        "capture_script_sha256": sha(ROOT / "eval/kt/make_mutations.py"), "records": records,
        "scorer_degradation_control": {"description": "In-memory copy of real TXT Report: missing before 2.2 status deliberately replaced by changed",
            "product_prediction": False, "baseline": {k: baseline[k] for k in ("tp", "fp", "fn", "semantic_gold")},
            "damaged": {k: damaged[k] for k in ("tp", "fp", "fn", "semantic_gold")}},
        "real_agent_comparison": "pending external capture/schema package from Batyrkhan",
        "human_confirmation": "pending_human; 19/19 control labels"}
    (BASE / "results/stage3-local-evidence.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
