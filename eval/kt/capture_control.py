"""Public HTTP capture for the existing evaluator; no model replay or gold access.

Invoked by make_mutations.py --capture-control. Raw synthetic responses are retained.
The operator must attest the server revision/configuration; local Git cannot prove
which code a separately running HTTP server serves.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import mimetypes
import re
from pathlib import Path
import subprocess
import urllib.request
import uuid
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]
CONTROL = ROOT / "seeds/kt/eval/control"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot():
    paths = sorted((ROOT / "apps/api/app").rglob("*.py"))
    return {p.relative_to(ROOT).as_posix(): digest(p) for p in paths}


def revision_snapshot(revision):
    """Hash raw tracked Git blobs, never checkout bytes or normalized line endings."""
    resolved = subprocess.check_output(
        ["git", "rev-parse", "--verify", "--end-of-options", revision + "^{commit}"],
        cwd=ROOT, text=True, stderr=subprocess.PIPE).strip()
    names = subprocess.check_output(
        ["git", "ls-tree", "-rz", "--name-only", resolved, "--", "apps/api/app/"],
        cwd=ROOT, stderr=subprocess.PIPE).split(b"\0")
    hashes = {}
    for raw_name in names:
        if not raw_name or not raw_name.endswith(b".py"):
            continue
        name = raw_name.decode("utf-8")
        blob = subprocess.check_output(["git", "cat-file", "blob", resolved + ":" + name],
                                       cwd=ROOT, stderr=subprocess.PIPE)
        hashes[name] = hashlib.sha256(blob).hexdigest()
    return resolved, hashes


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def pinned_inputs(extension):
    manifest = json.loads((CONTROL / "manifest.json").read_text(encoding="utf-8"))
    inputs = [(side, CONTROL / f"{side}.{extension}") for side in ("before", "after")]
    frozen = {item["path"]: item["sha256"] for item in manifest["files"]}
    for _, path in inputs:
        if frozen.get(path.name) != digest(path):
            raise ValueError(f"Input differs from frozen control manifest: {path.name}")
    return inputs


def check_report_inputs(report, inputs):
    wanted = Counter((side, digest(path)) for side, path in inputs)
    actual = Counter((d.get("edition"), d.get("sha256")) for d in report.get("documents", []))
    if actual != wanted:
        raise ValueError("Report document hashes/editions differ from uploaded bytes")


def actual_value(value):
    if isinstance(value, dict):
        return bool(value) and all(actual_value(v) for v in value.values())
    if isinstance(value, str):
        return bool(value.strip()) and "FILL" not in value.upper()
    return value is not None


def complete_input_pair(input_hashes):
    paths = [Path(name) for name in input_hashes]
    return (Counter(p.stem for p in paths) == Counter({"before": 1, "after": 1})
            and len({p.suffix for p in paths}) == 1)


def sse_events(raw):
    events = []
    for block in raw.replace("\r\n", "\n").split("\n\n"):
        data = "\n".join(line[5:].lstrip() for line in block.splitlines() if line.startswith("data:"))
        if data:
            events.append(json.loads(data))
    return events


def multipart(inputs, use_llm):
    boundary = "alibi-" + uuid.uuid4().hex
    body = bytearray()
    for side, path in inputs:
        body.extend((f"--{boundary}\r\nContent-Disposition: form-data; name=\"{side}_files\"; "
                     f"filename=\"{path.name}\"\r\nContent-Type: {mimetypes.guess_type(path)[0] or 'application/octet-stream'}\r\n\r\n").encode())
        body.extend(path.read_bytes())
        body.extend(b"\r\n")
    body.extend((f"--{boundary}\r\nContent-Disposition: form-data; name=\"use_llm\"\r\n\r\n"
                 f"{str(use_llm).lower()}\r\n--{boundary}--\r\n").encode())
    return bytes(body), "multipart/form-data; boundary=" + boundary


def trace_summary(report, events):
    calls = [e for e in events if e.get("type") == "tool_call"]
    results = [e for e in events if e.get("type") == "tool_result"]
    findings = report.get("findings", [])
    unresolved = [f for f in findings if f.get("status") == "unresolved"]
    refs = {(r["doc"], r["clause_id"]) for f in unresolved for r in f.get("before", []) + f.get("after", [])}
    investigated = set((report.get("agent") or {}).get("investigated_finding_ids", []))
    return {
        "mode": report.get("mode"), "agent": report.get("agent"),
        "findings": len(findings), "unresolved_findings": len(unresolved), "unresolved_distinct_refs": len(refs),
        "investigated_finding_ids": sorted(investigated),
        "not_listed_as_investigated": sum(f["id"] not in investigated for f in findings),
        "tool_call_events": len(calls), "tool_result_events": len(results),
        "tool_names": [e.get("data", {}).get("name") for e in calls],
        "result_dependent_actions": "not established by event counts; inspect saved ordered arguments/results independently",
        "model_inference_proven": False,
        "inference_note": "Report status and tool events alone do not prove provider inference; attach provider/server evidence and independent trace review",
    }


def capture(output: Path, base_url: str, extension: str, mode: str, attestation_path: Path):
    """Same file bytes and attested server configuration for both real HTTP modes."""
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use a new empty output directory; never overwrite a capture")
    attestation = json.loads(attestation_path.read_text(encoding="utf-8"))
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    core = snapshot()
    if attestation.get("core_hashes") != core or attestation.get("revision") != revision:
        raise ValueError("Server attestation must match current revision and all apps/api/app Python hashes")
    if not attestation.get("server_started_from_this_revision") or not attestation.get("configuration"):
        raise ValueError("Server revision/configuration attestation required")
    if not re.fullmatch(r"[0-9a-f]{7,40}", attestation.get("schema_revision", "")) or not actual_value(attestation["configuration"]):
        raise ValueError("Replace schema/configuration template placeholders with actual agreed values")
    inputs = pinned_inputs(extension)
    input_hashes = {p.relative_to(ROOT).as_posix(): digest(p) for _, p in inputs}
    if mode in ("agent", "both"):
        approval = attestation.get("inference_approval", {})
        for key in ("approved_by", "provider", "model", "spend_limit", "approved_input_sha256"):
            if key not in approval or not actual_value(approval[key]):
                raise ValueError(f"Real inference requires explicit approval: {key}")
        if approval["approved_input_sha256"] != input_hashes:
            raise ValueError("Inference permission does not cover these exact synthetic bytes")
        if not attestation.get("spend_limit_enforced_by"):
            raise ValueError("Record provider/operator spend-cap enforcement; this capture tool cannot enforce token billing")
    output.mkdir(parents=True, exist_ok=True)
    manifest = {"started_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "revision": revision,
                "core_hashes": core, "input_sha256": input_hashes, "transport": "public HTTP API",
                "attestation_sha256": digest(attestation_path), "configuration": attestation["configuration"],
                "schema_revision": attestation.get("schema_revision"), "control_manifest_sha256": digest(CONTROL / "manifest.json"),
                "mode_requested": mode, "runs": [], "status": "running"}
    write_json(output / "capture-manifest.json", manifest)
    try:
        for run_mode in (["deterministic", "agent"] if mode == "both" else [mode]):
            if snapshot() != core or {p.relative_to(ROOT).as_posix(): digest(p) for _, p in inputs} != input_hashes:
                raise RuntimeError("Core or input bytes changed during capture")
            body, content_type = multipart(inputs, run_mode == "agent")
            request = urllib.request.Request(base_url.rstrip("/") + "/audits", data=body, headers={"Content-Type": content_type})
            with urllib.request.urlopen(request, timeout=300) as response:
                raw = response.read().decode("utf-8")
            (output / f"{run_mode}.sse").write_text(raw, encoding="utf-8")
            events = sse_events(raw)
            terminals = [e for e in events if e["type"] in ("final", "error")]
            if len(terminals) != 1 or terminals[0]["type"] != "final" or events[-1] is not terminals[0]:
                raise RuntimeError("Expected exactly one successful terminal event; inspect raw SSE")
            report = terminals[0]["data"]["payload"]
            write_json(output / f"{run_mode}.json", report)
            check_report_inputs(report, inputs)
            if run_mode == "deterministic" and report.get("mode") != "deterministic":
                raise ValueError("Deterministic request returned a different mode")
            run_id = report["run_id"]
            with urllib.request.urlopen(base_url.rstrip("/") + "/audits/" + run_id, timeout=30) as response:
                reopened = json.load(response)
            write_json(output / f"{run_mode}-reopened.json", reopened)
            if reopened != report:
                raise RuntimeError("Reopened Report differs from final SSE payload")
            with urllib.request.urlopen(base_url.rstrip("/") + "/runs/" + run_id + "/trace", timeout=30) as response:
                trace = json.load(response)
            write_json(output / f"{run_mode}-trace.json", trace)
            summary = trace_summary(report, events)
            summary.update({"requested": run_mode, "run_id": run_id, "reopened_equal": True,
                            "report_sha256": digest(output / f"{run_mode}.json")})
            summary["genuine_agent_acceptance"] = ("pending independent provider/action review"
                if run_mode == "agent" and report.get("mode") == "llm_assisted"
                and (report.get("agent") or {}).get("status") == "completed" else "not demonstrated")
            manifest["runs"].append(summary)
            write_json(output / "capture-manifest.json", manifest)
        if snapshot() != core or subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() != revision:
            raise RuntimeError("Revision/core changed during capture; not a controlled comparison")
        if {p.relative_to(ROOT).as_posix(): digest(p) for _, p in inputs} != input_hashes:
            raise RuntimeError("Input bytes changed during capture; not a controlled comparison")
        manifest["status"] = "captured"
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["failure"] = type(exc).__name__ + ": " + str(exc)
        raise
    finally:
        manifest["finished_at_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
        manifest["artifacts"] = {p.name: digest(p) for p in sorted(output.iterdir()) if p.is_file() and p.name != "capture-manifest.json"}
        write_json(output / "capture-manifest.json", manifest)


def prepare_attestation(path, extension):
    if path.exists():
        raise ValueError("Attestation already exists; do not overwrite")
    inputs = pinned_inputs(extension)
    write_json(path, {
        "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "core_hashes": snapshot(), "schema_revision": "FILL_ACTUAL_SCHEMA_COMMIT",
        "server_started_from_this_revision": False,
        "configuration": {"provider": "FILL", "model": "FILL", "temperature": "FILL", "seed": "FILL_OR_UNSUPPORTED",
                          "timeout_s": "FILL", "turn_limit": "FILL", "tool_call_limit": "FILL", "audit_timeout_s": "FILL"},
        "inference_approval": {"approved_by": "FILL", "provider": "FILL", "model": "FILL", "spend_limit": "FILL",
                              "approved_input_sha256": {p.relative_to(ROOT).as_posix(): digest(p) for _, p in inputs}},
        "spend_limit_enforced_by": "", "instruction": "Batyrkhan fills from actual agreed runtime/access; no keys, tokens or sensitive URLs"})


def verify_package(directory: Path, core_revision: str | None = None):
    """Independent custody checks, not proof that a remote provider performed inference."""
    manifest = json.loads((directory / "capture-manifest.json").read_text(encoding="utf-8"))
    errors, checked = [], 0
    def check(condition, message):
        nonlocal checked
        checked += 1
        if not condition:
            errors.append(message)
    check(manifest.get("status") == "captured", "Capture did not finish successfully")
    check(bool(re.fullmatch(r"[0-9a-f]{7,40}", manifest.get("schema_revision", ""))), "Actual schema revision absent")
    check(bool(re.fullmatch(r"[0-9a-f]{40}", manifest.get("revision", ""))), "Actual full core revision absent")
    check(bool(manifest.get("core_hashes")), "Core file hashes absent")
    check(actual_value(manifest.get("configuration")), "Effective nonsecret configuration absent/placeholders")
    artifacts = manifest.get("artifacts", {})
    for name, expected in artifacts.items():
        path = (directory / name).resolve()
        check(path.parent == directory.resolve() and path.is_file() and digest(path) == expected, "Artifact hash mismatch: " + name)
    frozen = {"seeds/kt/eval/control/" + i["path"]: i["sha256"] for i in json.loads((CONTROL / "manifest.json").read_text(encoding="utf-8"))["files"]}
    for name, expected in manifest.get("input_sha256", {}).items():
        check(frozen.get(name) == expected, "Input is not from frozen synthetic bundle: " + name)
    check(len(manifest.get("input_sha256", {})) == 2, "Expected both input editions")
    check(complete_input_pair(manifest.get("input_sha256", {})),
          "Expected exactly one before and one after representation of the same format")
    runs = manifest.get("runs", [])
    check([r.get("requested") for r in runs] == ["deterministic", "agent"], "Paired deterministic + agent requests required")
    summaries = []
    for run in runs:
        mode = run.get("requested")
        if mode not in ("deterministic", "agent"):
            check(False, "Invalid requested mode")
            continue
        names = [f"{mode}.json", f"{mode}.sse", f"{mode}-reopened.json", f"{mode}-trace.json"]
        if not all(n in artifacts and (directory / n).is_file() for n in names):
            check(False, f"Missing pinned artifacts for {mode}")
            continue
        report = json.loads((directory / names[0]).read_text(encoding="utf-8"))
        reopened = json.loads((directory / names[2]).read_text(encoding="utf-8"))
        trace = json.loads((directory / names[3]).read_text(encoding="utf-8"))
        events = sse_events((directory / names[1]).read_text(encoding="utf-8"))
        terminals = [e for e in events if e.get("type") in ("final", "error")]
        check(len(terminals) == 1 and terminals[0].get("type") == "final" and events[-1] is terminals[0] and terminals[0].get("data", {}).get("payload") == report,
              f"{mode}: terminal payload mismatch")
        check(report == reopened, f"{mode}: saved/reopened report differs")
        check(run.get("run_id") == report.get("run_id") == trace.get("run_id"), f"{mode}: run_id mismatch")
        check(all(e.get("run_id") == report.get("run_id") for e in events), f"{mode}: SSE run_id mismatch")
        check([e.get("seq") for e in events] == list(range(1, len(events) + 1)), f"{mode}: SSE sequence gap/duplicate")
        normalize = lambda es: [(e.get("seq"), e.get("type"), e.get("data")) for e in es]
        check(normalize(events) == normalize(trace.get("events", [])), f"{mode}: persisted trace differs from SSE")
        expected_docs = Counter(("before" if Path(n).stem == "before" else "after", h) for n, h in manifest["input_sha256"].items())
        check(Counter((d.get("edition"), d.get("sha256")) for d in report.get("documents", [])) == expected_docs,
              f"{mode}: Report input bytes/editions differ")
        check(run.get("report_sha256") == digest(directory / names[0]), f"{mode}: Report digest differs")
        if mode == "deterministic":
            check(report.get("mode") == "deterministic", "Deterministic baseline mode mismatch")
        summaries.append({"requested": mode, **trace_summary(report, events)})
    local_revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    local_core = snapshot()
    core_verification = {"source": "working_checkout", "revision": local_revision,
                         "files_checked": len(local_core),
                         "exact_manifest_matches": manifest.get("core_hashes") == local_core}
    if core_revision is None:
        check(manifest.get("core_hashes") == local_core, "Captured core hashes differ from integrated checkout; obtain/check out actual captured revision before scoring")
    else:
        core_verification = {"source": "raw_git_blobs", "requested_revision": core_revision,
                             "revision": None, "files_checked": 0, "exact_manifest_matches": False}
        try:
            resolved, revision_core = revision_snapshot(core_revision)
        except (subprocess.CalledProcessError, UnicodeDecodeError, ValueError) as exc:
            check(False, "Cannot read requested core revision as raw Git blobs: " + type(exc).__name__)
        else:
            captured_core = manifest.get("core_hashes") or {}
            missing = sorted(set(revision_core) - set(captured_core))
            unexpected = sorted(set(captured_core) - set(revision_core))
            mismatched = sorted(name for name in set(revision_core) & set(captured_core)
                                if revision_core[name] != captured_core[name])
            check(resolved == manifest.get("revision"), "Requested core revision differs from captured manifest revision")
            check(bool(revision_core), "Requested core revision contains no tracked apps/api/app Python files")
            check(not missing and not unexpected, "Captured core file membership differs from requested Git revision")
            check(not mismatched, "Captured core hashes differ from raw Git blobs at requested revision")
            core_verification.update({"revision": resolved, "files_checked": len(revision_core),
                "manifest_revision_matches": resolved == manifest.get("revision"),
                "missing_manifest_files": missing, "unexpected_manifest_files": unexpected,
                "hash_mismatches": mismatched, "exact_manifest_matches": captured_core == revision_core})
    return {"integrity_checks": checked, "integrity_failures": len(errors), "errors": errors,
            "revision": manifest.get("revision"), "runs": summaries,
            "local_revision": local_revision, "local_core_hashes_equal": manifest.get("core_hashes") == local_core,
            "core_verification": core_verification,
            "inference_proof": "not established by this validator; independently review provider evidence and result-dependent tool arguments/results",
            "semantic_accuracy": "run score.py separately against frozen labels; pending_human stays provisional"}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-attestation", type=Path)
    parser.add_argument("--format", choices=["txt", "docx", "pdf", "xlsx"], default="docx")
    parser.add_argument("--verify-package", type=Path)
    parser.add_argument("--core-revision", help="Verify all captured core files against raw Git blobs at this exact manifest revision; default checks working checkout")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    if args.prepare_attestation:
        prepare_attestation(args.prepare_attestation, args.format)
    elif args.verify_package:
        result = verify_package(args.verify_package, core_revision=args.core_revision)
        if args.json_out:
            write_json(args.json_out, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(bool(result["integrity_failures"]))
    else:
        parser.error("Choose --prepare-attestation or --verify-package")
