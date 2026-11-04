#!/usr/bin/env python3
"""Preregister, freeze, dispatch and offline-replay v11 feedback repairs."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess

from aip.benchmark.completion import load_dotenv_value
from aip.benchmark.gamespec_attribution import derive_proposal, replay as replay_v8
from aip.benchmark.gamespec_feedback_repair import (
    RepairClient, RepairRunner, evaluate, materialize, messages_for, parameters, replay,
)
from aip.benchmark.gamespec_smoke import digest, write_json
from run_gamespec_attribution import package as old_package
from run_gamespec_targeted_c import SOURCES as V10_SOURCES, validate as validate_v10

ROOT = Path(__file__).resolve().parents[1]
SPEC = "configs/gamespec_feedback_repair_v11_2026-11-03.json"
LOCK = "configs/gamespec_feedback_repair_v11_lock_2026-11-03.json"
OUT = ROOT / "research/results/gamespec_feedback_repair_v11_2026-11-03"
SOURCES = list(dict.fromkeys(V10_SOURCES + [SPEC, "scripts/run_gamespec_feedback_repair.py",
    "src/aip/benchmark/gamespec_feedback_repair.py", "tests/test_gamespec_feedback_repair.py"]))


def specification():
    spec = json.loads((ROOT / SPEC).read_text())
    for key in ("audit", "raw", "reference"):
        if sha256((ROOT / spec["sources"][key]).read_bytes()).hexdigest() != spec["sources"][key + "_sha256"]:
            raise ValueError("frozen seed source changed")
    return spec


def package(tag):
    spec = specification(); m, b = old_package(tag)
    return materialize(m, b, spec, json.loads((ROOT / spec["sources"]["audit"]).read_text()),
                       json.loads((ROOT / spec["sources"]["raw"]).read_text()))


def hashes():
    return {p: sha256((ROOT / p).read_bytes()).hexdigest() for p in SOURCES}


def requests():
    return {tag: [{"trial": p, "messages": messages_for(m, b, p), "parameters": parameters(m, b, p)}
        for p in b["plan"]] for tag in ("luna6", "sol61") for m, b in [package(tag)]}


def preflight():
    spec = specification()
    om, ob = old_package("luna6")
    replay_v8(om, ob, json.loads((ROOT / spec["sources"]["raw"]).read_text()))
    m, b = package("luna6")
    for p in b["plan"]:
        item = b["cases"][p["case_id"]]; table = item["visibility_contexts"]
        correct = {"stage_table": table, "proposal": derive_proposal(table, tuple(item["case"]["fields"]))}
        result = evaluate(json.dumps(correct), m, b, p)
        if not result["metrics"]["joint_correct"]: raise ValueError("reference roundtrip failed")
    for tag, reqs in requests().items():
        m, _ = package(tag)
        for request in reqs:
            estimate = sum(len(msg["content"].encode()) + 10 for msg in request["messages"]) + 32
            if estimate > m["model"]["maximum_input_tokens"]: raise ValueError("conservative input bound exceeded")
        reserved = (m["model"]["maximum_input_tokens"] * m["model"]["input_usd_per_million"] +
                    m["model"]["maximum_output_tokens"] * m["model"]["output_usd_per_million"]) / 1e6
        if reserved > m["gates"]["maximum_call_usd"] or reserved * 72 > m["gates"]["maximum_total_usd"]:
            raise ValueError("anomaly cap prevents the preregistered schedule")
    return {"unchanged_reference_roundtrips": 72, "raw_v8_replay_agrees": True,
            "requests_within_caps": 144, "seed_records": 12, "canonical_patterns": 3, "rule_instances": 2}


def validate(committed=False):
    validate_v10()
    lock = json.loads((ROOT / LOCK).read_text())
    if hashes() != lock["sha256"] or digest(requests()) != lock["requests_sha256"]:
        raise ValueError("frozen implementation or requests changed")
    for tag in ("luna6", "sol61"):
        if digest(package(tag)[1]) != lock["bundle_sha256"][tag]: raise ValueError("seed bundle changed")
    if committed:
        for p in SOURCES + [LOCK]:
            if subprocess.check_output(["git", "show", f"HEAD:{p}"], cwd=ROOT) != (ROOT / p).read_bytes():
                raise ValueError("uncommitted frozen source")


def preserve_json(path, value):
    if path.exists():
        if json.loads(path.read_text()) != value: raise ValueError("existing result differs; preserve it")
    else: write_json(path, value)


def compare():
    models = {}
    for tag in ("luna6", "sol61"):
        m, b = package(tag); raw = json.loads((OUT / f"{tag}.json").read_text())
        result = replay(m, b, raw)
        preserve_json(OUT / f"{tag}_rescored.json", result)
        models[tag] = result["analysis"]
    m, b = package("luna6")
    sources = [SPEC, LOCK] + [str((OUT / f"{t}{suffix}.json").relative_to(ROOT))
                             for t in models for suffix in ("", "_rescored")]
    notes = {"semantic_feedback_is_new_rule_information": False,
        "meaning": "All arms see full rules; semantic treatment adds excerpt salience with source offsets. Local feedback never says semantic failure.",
        "units": {"provenance_seed_records": 12, "canonical_error_patterns": 3, "independent_rules": 2,
                  "correct_reference_tables": 2},
        "source_limit": "Developer-authored frozen truth, not independent human audit or held-out generalization",
        "local_coverage_boundary": "Prior real outputs: 12 residual wrong tables /19 wrong among 240 B/C tables in 360 replies. Separate mutation controls: 151/192 unflagged wrong tables. Neither is a new sample size for this repair study.",
        "no_retrospective_A_attribution": True, "no_overall_pass_or_deployment": True,
        "no_formal_feedback_efficacy_inference": True}
    preserve_json(OUT / "measurement_notes.json", notes)
    preserve_json(OUT / "seed_catalog.json", {"seeds": b["seeds"], "evidence_registry": b["evidence_registry"],
                  "units": notes["units"]})
    comparison = {"schema_version": "aip-gamespec-feedback-repair-v11", "models": models,
        "all_offline_rescores_agree": True, "measurement_notes": notes,
        "actual_generation_calls": sum(a["resources"]["attempts"] for a in models.values()),
        "total_cost_usd_estimate": sum(a["resources"]["cost_usd_estimate"] for a in models.values()),
        "ceiling_all_wrong_seeds_repaired_every_arm": all(a["conditions"][arm]["wrong"]["joint_correct"] == 12
             for a in models.values() for arm in ("none", "local", "semantic")),
        "old_scores_changed": False, "formal_trial_started": False, "new_manual_reference": False,
        "new_runtime_epsilon_gto_allowed": False, "adaptive_opponent_line_released": False,
        "sha256": {p: sha256((ROOT / p).read_bytes()).hexdigest() for p in sources}}
    preserve_json(OUT / "comparison.json", comparison)
    print(json.dumps({tag: {"conditions": a["conditions"], "resources": a["resources"],
        "semantic_minus_local_joint_repair": a["semantic_minus_local_joint_repair"],
        "cross_checks": a["cross_checks"]} for tag, a in models.items()}, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "check", "run", "compare"))
    parser.add_argument("--model", choices=("luna6", "sol61"))
    args = parser.parse_args()
    if args.mode == "prepare":
        if (ROOT / LOCK).exists() or OUT.exists(): raise FileExistsError("already frozen")
        validate_v10()
        prereg = subprocess.check_output(["git", "log", "-1", "--format=%H", "--", SPEC], cwd=ROOT).decode().strip()
        if not prereg or subprocess.check_output(["git", "show", f"{prereg}:{SPEC}"], cwd=ROOT) != (ROOT / SPEC).read_bytes():
            raise ValueError("commit preregistration first")
        m, b = package("luna6")
        write_json(ROOT / LOCK, {"preregistration_commit": prereg, "generation_calls_executed": 0,
            "sha256": hashes(), "requests_sha256": digest(requests()), "requests": requests(),
            "bundle_sha256": {tag: digest(package(tag)[1]) for tag in ("luna6", "sol61")},
            "seeds": b["seeds"], "evidence_registry": b["evidence_registry"], "preflight": preflight()})
        print("Frozen 144 requests, twelve exact seeds, controls, three patterns and rule excerpt offsets. Commit before generation.")
        return
    validate(committed=args.mode in ("check", "run"))
    if args.mode == "check":
        print("Committed sources, requests, excerpts and seed provenance verified. This check makes no API calls.")
        return
    if args.mode == "compare": compare(); return
    if not args.model: parser.error("run requires --model")
    output = OUT / f"{args.model}.json"
    if output.exists(): raise FileExistsError("preserve old run; no automatic resume")
    if (OUT / "oracle_stop.json").exists(): raise RuntimeError("global oracle stop exists")
    key = os.environ.get("OPENAI_API_KEY") or load_dotenv_value(ROOT / ".env", "OPENAI_API_KEY")
    if not key: raise RuntimeError("API credential unavailable")
    from openai import OpenAI
    client = RepairClient(OpenAI(api_key=key, base_url="https://api.openai.com/v1", timeout=60, max_retries=0))
    m, b = package(args.model)
    runner = RepairRunner(m, b, client, output, lambda text: len(text.encode()), halt_path=OUT / "oracle_stop.json")
    client.runner = runner; report = runner.run()
    print(json.dumps({"status": report["status"], "stop_reason": report["stop_reason"],
                      "conditions": report["analysis"]["conditions"]}, indent=2))
    if report["status"] != "completed": raise SystemExit(1)


if __name__ == "__main__": main()
