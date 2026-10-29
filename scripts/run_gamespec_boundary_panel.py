#!/usr/bin/env python3
"""Freeze/run/replay new authored boundary instances with the existing trainer-free interface."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess

from aip.benchmark.completion import load_dotenv_value
from aip.benchmark.gamespec_boundary_panel import analyze, package as build_package, preflight
from aip.benchmark.gamespec_interface import ParameterClient
from aip.benchmark.gamespec_prospective import ProspectiveRunner
from aip.benchmark.gamespec_smoke import digest, write_json
from run_gamespec_interface import package as v4_package
from run_gamespec_witness_diagnostic import SOURCES as V6_SOURCES

ROOT = Path(__file__).resolve().parents[1]
SPEC = "configs/gamespec_boundary_panel_v7_2026-10-29.json"
LOCK = "configs/gamespec_boundary_panel_v7_lock_2026-10-29.json"
OUT = ROOT / "research/results/gamespec_boundary_panel_v7_2026-10-29"
SOURCES = list(dict.fromkeys(V6_SOURCES + [SPEC, "src/aip/benchmark/gamespec_boundary_panel.py",
    "scripts/run_gamespec_boundary_panel.py", "tests/test_gamespec_boundary_panel.py"]))


def specification():
    return json.loads((ROOT / SPEC).read_text())


def package(tag):
    if tag not in ("luna6", "sol61"):
        raise ValueError("only frozen Luna and Sol permitted")
    return build_package(*v4_package(tag), specification())


def hashes():
    return {p: sha256((ROOT / p).read_bytes()).hexdigest() for p in SOURCES}


def validate():
    lock = json.loads((ROOT / LOCK).read_text())
    if hashes() != lock["sha256"]:
        raise ValueError("frozen sources changed")
    for p, h in lock["baseline_sha256"].items():
        if sha256((ROOT / p).read_bytes()).hexdigest() != h:
            raise ValueError("historical failures changed")
    if {t: digest(package(t)[1]) for t in ("luna6", "sol61")} != lock["bundle_sha256"]:
        raise ValueError("frozen bundle changed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "check", "run", "compare"))
    parser.add_argument("--model", choices=("luna6", "sol61"))
    args = parser.parse_args()
    if args.mode == "prepare":
        if OUT.exists() or (ROOT / LOCK).exists():
            raise FileExistsError("already frozen; never refreeze")
        audit = preflight(package("luna6")[1])
        write_json(ROOT / LOCK, {"sha256": hashes(), "generation_calls_executed": 0,
            "baseline_sha256": {p: sha256((ROOT / p).read_bytes()).hexdigest() for p in specification()["immutable_baselines"]},
            "bundle_sha256": {t: digest(package(t)[1]) for t in ("luna6", "sol61")},
            "exhaustive_answer_preflight": audit})
        print("New authored panel audited; commit and freeze before generation. External review deferred.")
        return
    validate()
    if args.mode == "compare":
        result = {"models": {t: analyze(*package(t), json.loads((OUT / f"{t}.json").read_text())) for t in ("luna6", "sol61")},
            "independent_panel_evaluated": False, "old_failures_reinterpreted": False,
            "formal_trial_started": False, "new_game_or_cfr_variant": False,
            "adaptive_opponent_line_released": False, "new_runtime_epsilon_gto_allowed": False}
        write_json(OUT / "comparison.json", result)
        print(json.dumps(result, indent=2))
        return
    for p in SOURCES + [LOCK]:
        if subprocess.check_output(["git", "show", f"HEAD:{p}"], cwd=ROOT) != (ROOT / p).read_bytes():
            raise ValueError(f"uncommitted dispatch source: {p}")
    if args.mode == "check":
        print("Committed sources, complete plan and unchanged historical evidence verified; no generation.")
        return
    if not args.model: parser.error("run requires --model")
    output = OUT / f"{args.model}.json"
    if output.exists(): raise FileExistsError("evidence already exists; no retry or overwrite")
    manifest, bundle = package(args.model)
    key = os.environ.get("OPENAI_API_KEY") or load_dotenv_value(ROOT / ".env", "OPENAI_API_KEY")
    if not key: raise RuntimeError("API credential unavailable")
    from openai import OpenAI
    client = ParameterClient(OpenAI(api_key=key, base_url="https://api.openai.com/v1", timeout=60, max_retries=0))
    runner = ProspectiveRunner(manifest, bundle, client, output, lambda text: len(text.encode("utf-8")))
    client.runner = runner
    report = runner.run()
    print(json.dumps({"status": report["status"], "stop_reason": report["stop_reason"],
                      "analysis": analyze(manifest, bundle, report)}, indent=2))
    if report["status"] != "completed": raise SystemExit(1)


if __name__ == "__main__":
    main()
