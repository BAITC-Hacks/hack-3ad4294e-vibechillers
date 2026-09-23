"""Verify and independently rescore a saved synthetic capture; never call a provider.

Archive inputs are immutable. Metrics always come from the existing score.py.
Trace semantics remain a separate source-backed review, not inferred from counts.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import sys
from zipfile import ZipFile

from capture_control import ROOT, verify_package, write_json


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def extract_verified(archive, expected_sha, destination):
    if sha(archive) != expected_sha.lower():
        raise ValueError("Archive SHA differs from independently supplied expected SHA")
    destination = destination.resolve()
    with ZipFile(archive) as package:
        members = package.infolist()
        paths = {}
        resolved_paths = set()
        records = []
        # Validate all members before any writes; existing bytes are never overwritten.
        for member in members:
            if member.orig_filename != member.filename:
                raise ValueError("Unsafe archive member")
            name = member.filename[:-1] if member.is_dir() else member.filename
            parts = name.split("/")
            reserved = {"CON", "PRN", "AUX", "NUL"} | {f"{kind}{n}" for kind in ("COM", "LPT") for n in range(1, 10)}
            if ("\\" in name or ":" in name or any(part in ("", ".", "..")
                    or part.endswith((".", " ")) or part.split(".")[0].upper() in reserved for part in parts)):
                raise ValueError("Unsafe archive member")
            key = name.casefold()
            if key in paths:
                raise ValueError("Duplicate or aliased ZIP member")
            paths[key] = member.is_dir()
            path = (destination / member.filename).resolve()
            kind = stat.S_IFMT(member.external_attr >> 16)
            if (not path.is_relative_to(destination) or kind not in (0, stat.S_IFREG, stat.S_IFDIR)
                    or str(path).casefold() in resolved_paths):
                raise ValueError("Unsafe archive member")
            resolved_paths.add(str(path).casefold())
            for parent in (destination, *path.parents):
                if parent.exists() and not parent.is_dir():
                    raise ValueError("Existing extraction parent is not a directory")
            if member.is_dir():
                if path.exists() and not path.is_dir():
                    raise ValueError("Existing extraction differs; choose a fresh destination")
                continue
            data = package.read(member)
            if path.exists() and (not path.is_file() or path.read_bytes() != data):
                raise ValueError("Existing extraction differs; choose a fresh destination")
            records.append((path, data, member.filename))
        for name in paths:
            parts = name.split("/")
            if any(paths.get("/".join(parts[:n])) is False for n in range(1, len(parts))):
                raise ValueError("ZIP file is also used as a parent directory")
        for path, data, _ in records:
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with path.open("xb") as stream:
                    stream.write(data)
            except FileExistsError:
                if not path.is_file() or path.read_bytes() != data:
                    raise ValueError("Existing extraction differs; choose a fresh destination")
    return {name: hashlib.sha256(data).hexdigest() for _, data, name in records}


def tool_pairs_valid(events):
    """Every call/result ID is unique, paired once, and ordered by event sequence."""
    try:
        calls = [e for e in events if e["type"] == "tool_call"]
        results = [e for e in events if e["type"] == "tool_result"]
        call_ids = [e["data"]["call_id"] for e in calls]
        result_ids = [e["data"]["call_id"] for e in results]
        if (any(not isinstance(i, str) or not i for i in call_ids + result_ids)
                or len(set(call_ids)) != len(calls) or len(set(result_ids)) != len(results)
                or set(call_ids) != set(result_ids)):
            return False
        paired = {e["data"]["call_id"]: e for e in results}
        return all(isinstance(e["seq"], int) and isinstance(paired[e["data"]["call_id"]]["seq"], int)
                   and paired[e["data"]["call_id"]]["seq"] > e["seq"]
                   and paired[e["data"]["call_id"]]["data"]["name"] == e["data"]["name"] for e in calls)
    except (KeyError, TypeError):
        return False


def review(archive, archive_sha, extract_to, output, core_revision):
    archive, output, extract_to = archive.resolve(), output.resolve(), extract_to.resolve()
    if output.is_relative_to(extract_to):
        raise ValueError("Review output must be outside immutable archive extraction")
    members = extract_verified(archive, archive_sha, extract_to)
    manifests = [extract_to / name for name in members if Path(name).name == "capture-manifest.json"]
    if len(manifests) != 1:
        raise ValueError("Expected exactly one capture manifest")
    capture_dir = manifests[0].parent
    manifest = read(manifests[0])
    required = {"server-attestation.json", "control-deterministic-score.json", "control-agent-score.json"}
    prefix = capture_dir.relative_to(extract_to)
    required.update((prefix / name).as_posix() for name in manifest.get("artifacts", {}))
    if not required <= set(members):
        raise ValueError("Required capture/attestation/scorer bytes are absent from verified archive")
    attestation_path = extract_to / "server-attestation.json"
    attestation = read(attestation_path)
    output.mkdir(parents=True, exist_ok=True)
    integrity = verify_package(capture_dir, core_revision=core_revision)
    write_json(output / "integrity-git.json", integrity)
    checks = {
        "attestation_sha256": sha(attestation_path) == manifest["attestation_sha256"],
        "attested_core_revision": attestation["revision"] == manifest["revision"],
        "attested_schema_revision": attestation["schema_revision"] == manifest["schema_revision"],
        "attested_core_hashes": attestation["core_hashes"] == manifest["core_hashes"],
        "attested_configuration": attestation["configuration"] == manifest["configuration"],
        "attested_server_started": attestation.get("server_started_from_this_revision") is True,
        "approved_input_bytes": attestation["inference_approval"]["approved_input_sha256"] == manifest["input_sha256"],
        "frozen_control_manifest": sha(ROOT / "seeds/kt/eval/control/manifest.json") == manifest["control_manifest_sha256"],
    }
    label_path = ROOT / "seeds/kt/eval/control/labels.jsonl"
    for relative in ("seeds/kt/eval/control/labels.jsonl", "seeds/kt/eval/split.json", "seeds/kt/eval/reviews.json", "eval/kt/score.py"):
        captured_blob = subprocess.check_output(["git", "show", manifest["revision"] + ":" + relative], cwd=ROOT)
        checks["captured_revision_bytes:" + relative] = (ROOT / relative).read_bytes() == captured_blob
    if integrity["integrity_failures"] or not all(checks.values()):
        write_json(output / "supplemental-custody.json", checks)
        raise ValueError("Custody check failed; preserve diagnostics before any scoring")
    summaries, scores, reports = [], {}, {}
    for mode in ("deterministic", "agent"):
        report_path = capture_dir / f"{mode}.json"
        reports[mode] = read(report_path)
        score_path = output / f"{mode}-score.json"
        result = subprocess.run([sys.executable, "-B", str(ROOT / "eval/kt/score.py"),
            "--labels", str(label_path), "--partition", "development", "--json-out", str(score_path), str(report_path)],
            cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8")
        (output / f"{mode}-score.log").write_text(result.stdout, encoding="utf-8", newline="\n")
        scores[mode] = read(score_path)
        supplied = read(extract_to / f"control-{mode}-score.json")
        checks[f"supplied_metrics:{mode}"] = scores[mode]["groups"] == supplied["groups"]
        summaries.append({"requested": mode, "run_id": reports[mode]["run_id"], "mode": reports[mode]["mode"],
            "execution": reports[mode]["agent"], "groups": scores[mode]["groups"],
            "citations": scores[mode]["provenance"][0], "metrics_sha256": sha(score_path)})
    agent, baseline = reports["agent"], reports["deterministic"]
    events = read(capture_dir / "agent-trace.json")["events"]
    calls = [e for e in events if e["type"] == "tool_call"]
    results = [e for e in events if e["type"] == "tool_result"]
    checks["tool_pairs_ids_names_order"] = tool_pairs_valid(events)
    fn_ids = {f["id"] for f in agent["findings"]}
    investigated = set(agent["agent"]["investigated_finding_ids"])
    checks["investigated_ids_exist"] = investigated <= fn_ids
    coverage = {"findings": len(fn_ids), "listed_as_investigated": len(investigated),
                "not_listed_as_investigated": sorted(fn_ids - investigated),
                "unresolved_findings": sum(f["status"] == "unresolved" for f in agent["findings"]),
                "coverage_unresolved_refs": agent["coverage"]["unresolved"]}
    summary = {
        "archive": archive.relative_to(ROOT).as_posix() if archive.is_relative_to(ROOT) else str(archive), "archive_sha256": sha(archive),
        "archive_members_sha256": members, "capture_revision": manifest["revision"],
        "schema_revision": manifest["schema_revision"], "configuration": manifest["configuration"],
        "labels_sha256": sha(label_path), "evaluator_sha256": sha(ROOT / "eval/kt/score.py"),
        "integrity_checks": integrity["integrity_checks"], "integrity_failures": integrity["integrity_failures"],
        "supplemental_checks": checks, "supplemental_failures": sum(not v for v in checks.values()),
        "runs": summaries,
        "different_top_level_report_fields": [k for k in sorted(set(agent) | set(baseline)) if agent.get(k) != baseline.get(k)],
        "identical_product_sections": {k: agent[k] == baseline[k] for k in ("documents", "clauses", "units", "findings", "unit_changes", "risks", "conclusion", "coverage")},
        "observed_tools": dict(Counter(e["data"]["name"] for e in calls)),
        "tool_calls": len(calls), "tool_results": len(results), "tool_results_ok": sum(e["data"].get("ok") is True for e in results),
        "inspection_scope": coverage,
        "full_agent_acceptance": False, "F1_acceptance": False,
        "review_status": "19 pending_human; provisional agreement; no holdout scored",
        "inference_provenance": "Batyrkhan supplied actual HTTP/SSE/persisted tool trace and nonsecret server attestation; no upstream provider transcript or token usage in ZIP. No model call was executed during this independent review.",
        "interpretation": "Read trace-review and source-errors for action dependencies and semantic errors; tool counts alone establish neither decisions nor model quality."
    }
    write_json(output / "summary.json", summary)
    print(json.dumps({"integrity": [integrity["integrity_checks"], integrity["integrity_failures"]],
                      "supplemental": [len(checks), summary["supplemental_failures"]],
                      "report_different_fields": summary["different_top_level_report_fields"]}, indent=2))
    if summary["supplemental_failures"]:
        raise ValueError("Supplemental check mismatch; inspect saved summary")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--extract-to", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--core-revision", required=True)
    args = parser.parse_args()
    review(args.archive, args.sha256, args.extract_to, args.output, args.core_revision)
