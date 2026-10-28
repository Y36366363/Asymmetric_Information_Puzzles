#!/usr/bin/env python3
"""Preregister/dispatch developmental witness probes; validate separate review intake."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess

from aip.benchmark.completion import load_dotenv_value
from aip.benchmark.gamespec_interface import ParameterClient
from aip.benchmark.gamespec_smoke import digest, write_json
from aip.benchmark.gamespec_prospective import ProspectiveRunner
from aip.benchmark.gamespec_witness_diagnostic import diagnostic_package, diagnostic_analysis, review_intake
from run_gamespec_prospective import SOURCES as V5_SOURCES
from run_gamespec_interface import package as v4_package

ROOT = Path(__file__).resolve().parents[1]
SPEC = "configs/gamespec_witness_diagnostic_v6_2026-10-28.json"
LOCK = "configs/gamespec_witness_diagnostic_v6_lock_2026-10-28.json"
OUT = ROOT / "research/results/gamespec_witness_diagnostic_v6_2026-10-28"
SOURCES = list(dict.fromkeys(V5_SOURCES + [SPEC, "src/aip/benchmark/gamespec_witness_diagnostic.py",
    "scripts/run_gamespec_witness_diagnostic.py", "tests/test_gamespec_witness_diagnostic.py"]))


def specification():
    return json.loads((ROOT / SPEC).read_text())


def package(tag):
    if tag not in ("luna6", "sol61"):
        raise ValueError("only frozen Luna candidate and Sol reference allowed")
    return diagnostic_package(*v4_package(tag), specification())


def hashes():
    return {p: sha256((ROOT / p).read_bytes()).hexdigest() for p in SOURCES}


def validate():
    lock = json.loads((ROOT / LOCK).read_text())
    if hashes() != lock["sha256"]:
        raise ValueError("frozen sources changed")
    for p, h in lock["baseline_sha256"].items():
        if sha256((ROOT / p).read_bytes()).hexdigest() != h:
            raise ValueError("historical evidence changed")
    if {t: digest(package(t)[1]) for t in ("luna6", "sol61")} != lock["bundle_sha256"]:
        raise ValueError("frozen bundles changed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "check", "run", "compare", "review-intake"))
    parser.add_argument("--model", choices=("luna6", "sol61"))
    parser.add_argument("--record", type=Path)
    args = parser.parse_args()
    if args.mode == "review-intake":
        if args.record is None: parser.error("review-intake requires --record")
        print(json.dumps(review_intake(json.loads(args.record.read_text()), args.record.parent), indent=2))
        return
    if args.mode == "prepare":
        if OUT.exists() or (ROOT / LOCK).exists():
            raise FileExistsError("already frozen; do not refreeze")
        write_json(ROOT / LOCK, {"sha256": hashes(), "generation_calls_executed": 0,
            "baseline_sha256": {p: sha256((ROOT / p).read_bytes()).hexdigest() for p in specification()["immutable_baselines"]},
            "bundle_sha256": {t: digest(package(t)[1]) for t in ("luna6", "sol61")},
            "reference_audit": package("luna6")[1]["reference_preflight"]})
        print("Development diagnostic frozen; commit before any calls. Independent reviewer panel pending.")
        return
    validate()
    if args.mode == "compare":
        summaries = {}
        for tag in ("luna6", "sol61"):
            report = json.loads((OUT / f"{tag}.json").read_text())
            summaries[tag] = diagnostic_analysis(*package(tag), report)
        result = {"models": summaries, "development_diagnostic": True, "independent_panel_evaluated": False,
                  "old_failures_reinterpreted": False, "formal_trial_started": False,
                  "adaptive_opponent_line_released": False, "new_runtime_epsilon_gto_allowed": False}
        write_json(OUT / "comparison.json", result)
        print(json.dumps(result, indent=2))
        return
    for p in SOURCES + [LOCK]:
        if subprocess.check_output(["git", "show", f"HEAD:{p}"], cwd=ROOT) != (ROOT / p).read_bytes():
            raise ValueError(f"uncommitted dispatch source: {p}")
    if args.mode == "check":
        print("Committed plan and historical evidence verified; zero calls.")
        return
    if args.model is None: parser.error("run requires explicit --model")
    output = OUT / f"{args.model}.json"
    if output.exists(): raise FileExistsError("raw evidence exists; no resampling or overwriting")
    manifest, bundle = package(args.model)
    key = os.environ.get("OPENAI_API_KEY") or load_dotenv_value(ROOT / ".env", "OPENAI_API_KEY")
    if not key: raise RuntimeError("API credential unavailable")
    from openai import OpenAI
    client = ParameterClient(OpenAI(api_key=key, base_url="https://api.openai.com/v1", timeout=60, max_retries=0))
    runner = ProspectiveRunner(manifest, bundle, client, output, lambda text: len(text.encode("utf-8")))
    client.runner = runner
    report = runner.run()
    print(json.dumps({"status": report["status"], "stop_reason": report["stop_reason"],
        "diagnostic": diagnostic_analysis(manifest, bundle, report)}, indent=2))
    if report["status"] != "completed": raise SystemExit(1)


if __name__ == "__main__":
    main()
