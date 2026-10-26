#!/usr/bin/env python3
"""Freeze/check/run one preregistered model, replay, or compare all models."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess

from aip.benchmark.completion import load_dotenv_value
from aip.benchmark.gamespec_smoke import digest, write_json
from aip.benchmark.gamespec_interface import InterfaceRunner, ParameterClient, materialize, replay
from run_gamespec_scope_ablation import package as v3_package

ROOT = Path(__file__).resolve().parents[1]
SPEC = "configs/gamespec_interface_v4_2026-10-26.json"
LOCK = "configs/gamespec_interface_v4_lock_2026-10-26.json"
OUT = ROOT / "research/results/gamespec_interface_v4_2026-10-26"
SOURCES = [SPEC, "src/aip/benchmark/gamespec_interface.py", "scripts/run_gamespec_interface.py",
           "tests/test_gamespec_interface.py", "src/aip/benchmark/gamespec_scope_ablation.py",
           "src/aip/benchmark/gamespec_smoke.py", "src/aip/benchmark/gamespec_smoke_v2.py",
           "src/aip/core/game_spec.py", "src/aip/core/game_spec_pilot.py", "src/aip/core/game_spec_smoke.py",
           "scripts/run_gamespec_scope_ablation.py", "configs/gamespec_scope_ablation_v3_2026-10-25.json",
           "configs/llm_gamespec_smoke_execution_2026-10-21.json", "configs/llm_gamespec_smoke_v2_2026-10-23.json"]


def specification():
    return json.loads((ROOT / SPEC).read_text())


def package(tag):
    return materialize(*v3_package(), specification(), tag)


def hashes():
    return {p: sha256((ROOT / p).read_bytes()).hexdigest() for p in SOURCES}


def validate():
    lock = json.loads((ROOT / LOCK).read_text())
    if lock["sha256"] != hashes():
        raise ValueError("frozen sources changed")
    for p, h in lock["historical_sha256"].items():
        if sha256((ROOT / p).read_bytes()).hexdigest() != h:
            raise ValueError("historical baseline changed")
    for model in specification()["models"]:
        if digest(package(model["tag"])[1]) != lock["bundle_sha256"][model["tag"]]:
            raise ValueError("bundle changed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "check", "run", "replay", "compare"))
    parser.add_argument("--model", choices=("mini41", "luna6", "sol61"))
    args = parser.parse_args()
    spec = specification()
    if args.mode == "prepare":
        if OUT.exists():
            raise FileExistsError("run directory exists; no refreeze after dispatch")
        write_json(ROOT / LOCK, {"sha256": hashes(), "provider_generation_calls": 0,
            "historical_sha256": {p: sha256((ROOT / p).read_bytes()).hexdigest() for p in spec["historical_baselines"]},
            "bundle_sha256": {m["tag"]: digest(package(m["tag"])[1]) for m in spec["models"]}})
        print("Prepared 112 trials per model; commit before generation calls.")
        return
    validate()
    if args.mode in ("compare", "replay"):
        tags = [args.model] if args.model else [m["tag"] for m in spec["models"]]
        summaries = {}
        for tag in tags:
            manifest, bundle = package(tag)
            report = json.loads((OUT / f"{tag}.json").read_text())
            summary = replay(manifest, bundle, report)
            write_json(OUT / f"{tag}_replay.json", summary)
            # Surface probes remain dependent diagnostics, never pooled with four primary pairs.
            probes = [{"trial_id": t["trial_id"], "arm": t["arm"], "case_id": t["case_id"],
                       "correct": t.get("evaluation", {}).get("correct", False),
                       "errors": t.get("evaluation", {}).get("errors", ["incomplete"])}
                      for t in report["trials"] if t["task"] == "surface_probe"]
            summaries[tag] = {"execution_status": report["status"], "stop_reason": report["stop_reason"],
                              "model_parameters": manifest["model"], "analysis": summary, "surface_probes": probes}
        if args.mode == "compare":
            write_json(OUT / "comparison.json", {"schema_version": "gamespec-interface-v4-comparison",
                "models": summaries, "historical_results_reinterpreted": False,
                "generalization_or_no_overfit_proven": False, "formal_trial_allowed": False,
                "model_parameter_caveat": spec["model_comparison_limits"]})
        print(json.dumps({tag: {"status": s["execution_status"], "cells": s["analysis"]["cells"],
                               "cost_usd": s["analysis"]["cost_usd"]} for tag, s in summaries.items()}, indent=2))
        return
    for p in SOURCES + [LOCK]:
        if subprocess.check_output(["git", "show", f"HEAD:{p}"], cwd=ROOT) != (ROOT / p).read_bytes():
            raise ValueError(f"source not committed: {p}")
    if args.mode == "check":
        print("Committed frozen sources, bundles and v3 failure baseline verified; no calls.")
        return
    if not args.model:
        parser.error("run requires one explicit --model")
    output = OUT / f"{args.model}.json"
    if output.exists():
        raise FileExistsError("output exists; replay only, no retry or overwrite")
    manifest, bundle = package(args.model)
    key = os.environ.get("OPENAI_API_KEY") or load_dotenv_value(ROOT / ".env", "OPENAI_API_KEY")
    if not key:
        raise RuntimeError("API credential unavailable")
    from openai import OpenAI
    client = ParameterClient(OpenAI(api_key=key, base_url="https://api.openai.com/v1",
                                   timeout=60, max_retries=0))
    runner = InterfaceRunner(manifest, bundle, client, output, lambda text: len(text.encode("utf-8")))
    client.runner = runner
    report = runner.run()
    print(json.dumps({"status": report["status"], "stop_reason": report["stop_reason"],
                      "cells": report["analysis"]["cells"]}, indent=2))
    if report["status"] != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
