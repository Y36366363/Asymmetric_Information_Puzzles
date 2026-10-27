#!/usr/bin/env python3
"""Freeze/replay prospective authored rule instances with unchanged v4 f1_s1."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess

from aip.benchmark.completion import load_dotenv_value
from aip.benchmark.gamespec_smoke import digest, write_json
from aip.benchmark.gamespec_interface import ParameterClient
from aip.benchmark.gamespec_prospective import ProspectiveRunner, materialize, replay
from run_gamespec_interface import SOURCES as V4_SOURCES, package as v4_package

ROOT = Path(__file__).resolve().parents[1]
SPEC = "configs/gamespec_prospective_v5_2026-10-27.json"
LOCK = "configs/gamespec_prospective_v5_lock_2026-10-27.json"
OUT = ROOT / "research/results/gamespec_prospective_v5_2026-10-27"
SOURCES = list(dict.fromkeys(V4_SOURCES + [SPEC, "src/aip/benchmark/gamespec_prospective.py",
                   "scripts/run_gamespec_prospective.py", "tests/test_gamespec_prospective.py"]))


def specification():
    return json.loads((ROOT / SPEC).read_text())


def package(tag):
    if tag not in ("luna6", "sol61"):
        raise ValueError("only frozen Luna and Sol allowed, no 4.1-mini generation")
    return materialize(*v4_package(tag), specification())


def hashes():
    return {p: sha256((ROOT / p).read_bytes()).hexdigest() for p in SOURCES}


def validate():
    lock = json.loads((ROOT / LOCK).read_text())
    if hashes() != lock["sha256"]:
        raise ValueError("frozen source mismatch")
    for p, checksum in lock["baseline_sha256"].items():
        if sha256((ROOT / p).read_bytes()).hexdigest() != checksum:
            raise ValueError("historical baseline changed")
    for tag in ("luna6", "sol61"):
        if digest(package(tag)[1]) != lock["bundle_sha256"][tag]:
            raise ValueError("frozen bundle mismatch")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "check", "run", "replay", "compare"))
    parser.add_argument("--model", choices=("luna6", "sol61"))
    args = parser.parse_args()
    if args.mode == "prepare":
        if OUT.exists():
            raise FileExistsError("output directory exists, cannot refreeze")
        write_json(ROOT / LOCK, {"sha256": hashes(), "generation_calls_executed": 0,
            "baseline_sha256": {p: sha256((ROOT / p).read_bytes()).hexdigest() for p in specification()["immutable_baselines"]},
            "bundle_sha256": {t: digest(package(t)[1]) for t in ("luna6", "sol61")},
            "reference_audit": package("luna6")[1]["reference_preflight"]})
        print("Prepared and audited new instances; commit before calls.")
        return
    validate()
    if args.mode in ("replay", "compare"):
        result = {}
        for tag in ([args.model] if args.model else ["luna6", "sol61"]):
            manifest, bundle = package(tag)
            report = json.loads((OUT / f"{tag}.json").read_text())
            analysis = replay(manifest, bundle, report)
            write_json(OUT / f"{tag}_replay.json", analysis)
            result[tag] = {"status": report["status"], "stop_reason": report["stop_reason"],
                           "model_parameters": manifest["model"], "analysis": analysis}
        if args.mode == "compare":
            reports = {tag: json.loads((OUT / f"{tag}.json").read_text()) for tag in result}
            correct = {tag: {t["trial_id"]: t.get("evaluation", {}).get("correct", False) for t in r["trials"]} for tag, r in reports.items()}
            plan = package("luna6")[1]["plan"]
            disagreements = [{"trial_id": p["trial_id"], "luna_correct": correct["luna6"].get(p["trial_id"], False),
                              "sol_correct": correct["sol61"].get(p["trial_id"], False)} for p in plan
                             if correct["luna6"].get(p["trial_id"], False) != correct["sol61"].get(p["trial_id"], False)]
            write_json(OUT / "comparison.json", {"schema_version": "gamespec-prospective-v5-comparison", "models": result,
                "correctness_disagreements": disagreements, "historical_failures_reinterpreted": False,
                "external_blind_holdout": False, "formal_trial_started": False,
                "runtime_epsilon_gto_allowed": False, "adaptive_opponent_line_released": False})
        print(json.dumps(result, indent=2))
        return
    for p in SOURCES + [LOCK]:
        if subprocess.check_output(["git", "show", f"HEAD:{p}"], cwd=ROOT) != (ROOT / p).read_bytes():
            raise ValueError(f"dispatch source not committed: {p}")
    if args.mode == "check":
        print("Committed configuration, direct-table reference audit and unchanged historical failures verified; zero calls.")
        return
    if not args.model:
        parser.error("run requires explicit model")
    output = OUT / f"{args.model}.json"
    if output.exists():
        raise FileExistsError("output exists; replay only, no overwrite or retry")
    manifest, bundle = package(args.model)
    key = os.environ.get("OPENAI_API_KEY") or load_dotenv_value(ROOT / ".env", "OPENAI_API_KEY")
    if not key:
        raise RuntimeError("API credential unavailable")
    from openai import OpenAI
    client = ParameterClient(OpenAI(api_key=key, base_url="https://api.openai.com/v1", timeout=60, max_retries=0))
    runner = ProspectiveRunner(manifest, bundle, client, output, lambda text: len(text.encode("utf-8")))
    client.runner = runner
    report = runner.run()
    print(json.dumps({"status": report["status"], "stop_reason": report["stop_reason"], "analysis": report["analysis"]}, indent=2))
    if report["status"] != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
