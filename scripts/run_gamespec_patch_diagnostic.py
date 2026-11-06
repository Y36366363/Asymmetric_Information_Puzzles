#!/usr/bin/env python3
"""Freeze exact patch/rewrite requests and dependencies before one Luna dispatch."""
import argparse
from hashlib import sha256
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import subprocess
import sys

from packaging.requirements import Requirement

from aip.benchmark.completion import load_dotenv_value
from aip.benchmark.gamespec_attribution import derive_proposal
from aip.benchmark.gamespec_cell_audit import difference_patch
from aip.benchmark.gamespec_patch_diagnostic import (
    PatchClient, PatchRunner, evaluate, materialize, messages_for, parameters, replay, input_table,
)
from aip.benchmark.gamespec_smoke import digest, write_json
from run_gamespec_feedback_repair import (
    SOURCES as OLD_SOURCES, package as old_package, preserve_json, validate as validate_old,
)

ROOT = Path(__file__).resolve().parents[1]
SPEC = "configs/gamespec_patch_diagnostic_v12_2026-11-05.json"
ADDENDUM = "configs/gamespec_patch_execution_addendum_2026-11-06.json"
LOCK = "configs/gamespec_patch_execution_lock_2026-11-06.json"
OUT = ROOT / "research/results/gamespec_patch_diagnostic_v12_2026-11-06"
SOURCES = list(dict.fromkeys(OLD_SOURCES + [SPEC, ADDENDUM, "pyproject.toml",
    "src/aip/benchmark/gamespec_cell_audit.py", "tests/test_gamespec_cell_audit.py",
    "scripts/audit_gamespec_cells.py", "scripts/audit_gamespec_copy.py",
    "src/aip/benchmark/gamespec_patch_diagnostic.py", "scripts/run_gamespec_patch_diagnostic.py",
    "tests/test_gamespec_patch_diagnostic.py"]))


def package():
    spec = json.loads((ROOT / SPEC).read_text()); addendum = json.loads((ROOT / ADDENDUM).read_text())
    if sha256((ROOT / SPEC).read_bytes()).hexdigest() != addendum["base_sha256"]:
        raise ValueError("base protocol changed")
    for p, h in spec["sources_sha256"].items():
        if sha256((ROOT / p).read_bytes()).hexdigest() != h: raise ValueError("preregistered source changed")
    p = addendum["copy_audit"]["path"]
    if sha256((ROOT / p).read_bytes()).hexdigest() != addendum["copy_audit"]["sha256"]:
        raise ValueError("copy audit changed")
    m, b = old_package("luna6")
    return materialize(m, b, spec, addendum)


def runtime_dependencies():
    # Exact installed transitive runtime graph; no new dependency installation.
    todo, found = ["openai", "packaging"], {}
    while todo:
        name = todo.pop().lower().replace("_", "-")
        if name in found: continue
        dist = metadata.distribution(name)
        files = {}
        for entry in dist.files or []:
            if "__pycache__" in entry.parts or str(entry).endswith((".pyc", ".pyo")): continue
            path = dist.locate_file(entry)
            if path.is_file(): files[str(entry)] = sha256(path.read_bytes()).hexdigest()
        found[name] = {"version": dist.version, "installed_files_sha256": files}
        for requirement in dist.requires or []:
            r = Requirement(requirement)
            if r.marker is None or r.marker.evaluate({"extra": ""}): todo.append(r.name)
    return {"python_version": sys.version, "python_executable_sha256": sha256(Path(sys.executable).read_bytes()).hexdigest(),
            "distributions": found}


def requests():
    m, b = package()
    return [{"trial": p, "messages": messages_for(m, b, p), "parameters": parameters(m, b, p)} for p in b["plan"]]


def hashes():
    return {p: sha256((ROOT / p).read_bytes()).hexdigest() for p in SOURCES}


def preflight():
    validate_old(); m, b = package()
    for p in b["plan"]:
        item = b["cases"][p["case_id"]]; table = item["visibility_contexts"]
        fields = tuple(item["case"]["fields"])
        payload = {"proposal": derive_proposal(table, fields)}
        payload["edits" if p["representation"] == "patch" else "stage_table"] = (
            difference_patch(input_table(b, p), table, fields) if p["representation"] == "patch" else table)
        result = evaluate(json.dumps(payload), m, b, p)
        if not result["metrics"]["joint_correct"]: raise ValueError("reference roundtrip failed")
        estimate = sum(len(msg["content"].encode()) + 10 for msg in messages_for(m, b, p)) + 32
        if estimate > m["model"]["maximum_input_tokens"]: raise ValueError("input bound exceeded")
    reserve = (m["model"]["maximum_input_tokens"] * m["model"]["input_usd_per_million"] +
               m["model"]["maximum_output_tokens"] * m["model"]["output_usd_per_million"]) / 1e6
    if reserve > m["gates"]["maximum_call_usd"] or reserve * 72 > m["gates"]["maximum_total_usd"]:
        raise ValueError("anomaly protection blocks schedule")
    return {"reference_roundtrips": 72, "bounded_requests": 72, "Sol_calls": 0,
            "model_calls_executed": 0, "no_new_dependency": True}


def validate(committed=False):
    validate_old(); lock = json.loads((ROOT / LOCK).read_text()); m, b = package()
    if hashes() != lock["sha256"] or requests() != lock["requests"] or digest(requests()) != lock["requests_sha256"]:
        raise ValueError("frozen sources or requests changed")
    if runtime_dependencies() != lock["runtime_dependencies"]: raise ValueError("runtime dependency changed")
    if digest(m) != lock["manifest_sha256"] or digest(b) != lock["bundle_sha256"]:
        raise ValueError("bundle changed")
    if committed:
        for p in SOURCES + [LOCK]:
            if subprocess.check_output(["git", "show", f"HEAD:{p}"], cwd=ROOT) != (ROOT / p).read_bytes():
                raise ValueError("uncommitted frozen source")


def compare():
    validate(); m, b = package(); rawpath = OUT / "luna6.json"
    raw = json.loads(rawpath.read_text()); rescored = replay(m, b, raw)
    preserve_json(OUT / "luna6_rescored.json", rescored)
    result = {"schema_version": "aip-gamespec-patch-comparison-v12", "status": raw["status"],
        "actual_generation_calls": len(raw["attempts"]), "Sol_generation_calls": 0,
        "all_offline_rescores_agree": True, "analysis": rescored["analysis"],
        "old_scores_changed": False, "formal_trial_started": False, "new_runtime_epsilon_gto_allowed": False,
        "adaptive_opponent_line_released": False,
        "sha256": {p: sha256((ROOT / p).read_bytes()).hexdigest() for p in (SPEC, ADDENDUM, LOCK,
            str(rawpath.relative_to(ROOT)), str((OUT / "luna6_rescored.json").relative_to(ROOT)))}}
    preserve_json(OUT / "comparison.json", result)
    print(json.dumps({k: result["analysis"][k] for k in ("conditions", "primary_patch_minus_rewrite", "resources", "sol_reentry")}, indent=2))


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("mode", choices=("prepare", "check", "run", "compare"))
    args = parser.parse_args()
    if args.mode == "prepare":
        if (ROOT / LOCK).exists() or OUT.exists(): raise FileExistsError("already frozen or dispatched")
        for p in (SPEC, ADDENDUM):
            if subprocess.check_output(["git", "show", f"HEAD:{p}"], cwd=ROOT) != (ROOT / p).read_bytes():
                raise ValueError("commit protocol and addendum first")
        m, b = package(); reqs = requests()
        write_json(ROOT / LOCK, {"preregistration_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip(),
            "sha256": hashes(), "requests": reqs, "requests_sha256": digest(reqs),
            "manifest_sha256": digest(m), "bundle_sha256": digest(b),
            "runtime_dependencies": runtime_dependencies(), "preflight": preflight(), "generation_calls_executed": 0})
        print("Frozen 72 Luna requests, runtime dependency bytes and exact source hashes. Commit before dispatch.")
        return
    validate(committed=args.mode in ("check", "run"))
    if args.mode == "check": print("Committed request/source/dependency locks agree; no API call."); return
    if args.mode == "compare": compare(); return
    output = OUT / "luna6.json"
    if output.exists() or (OUT / "oracle_stop.json").exists(): raise FileExistsError("preserve existing run; no resume")
    key = os.environ.get("OPENAI_API_KEY") or load_dotenv_value(ROOT / ".env", "OPENAI_API_KEY")
    if not key: raise RuntimeError("API credential unavailable")
    from openai import OpenAI
    client = PatchClient(OpenAI(api_key=key, base_url="https://api.openai.com/v1", timeout=60, max_retries=0))
    m, b = package(); runner = PatchRunner(m, b, client, output, lambda text: len(text.encode()), halt_path=OUT / "oracle_stop.json")
    client.runner = runner
    report = runner.run()
    print(json.dumps({"status": report["status"], "stop_reason": report["stop_reason"], "resources": report["analysis"]["resources"]}))
    if report["status"] != "completed": raise SystemExit(1)


if __name__ == "__main__": main()
