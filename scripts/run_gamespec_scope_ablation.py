#!/usr/bin/env python3
"""Prepare/commit/execute/replay the v3 paired engineering check, once only."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess

from aip.benchmark.completion import load_dotenv_value
from aip.benchmark.gamespec_smoke import write_json
from aip.benchmark.gamespec_scope_ablation import ScopeAblationRunner, materialize, replay

ROOT = Path(__file__).resolve().parents[1]
SPEC = "configs/gamespec_scope_ablation_v3_2026-10-25.json"
BUNDLE = "configs/gamespec_scope_ablation_v3_bundle_2026-10-25.json"
LOCK = "configs/gamespec_scope_ablation_v3_lock_2026-10-25.json"
OUTPUT = ROOT / "research/results/gamespec_scope_ablation_v3_2026-10-25/report.json"
SOURCES = [SPEC, BUNDLE, "configs/gamespec_scope_v3_preflight_counterexample_2026-10-25.json", "src/aip/benchmark/gamespec_scope_ablation.py",
           "src/aip/benchmark/gamespec_smoke.py", "src/aip/benchmark/gamespec_smoke_v2.py",
           "src/aip/core/game_spec.py", "src/aip/core/game_spec_pilot.py", "src/aip/core/game_spec_smoke.py",
           "configs/llm_gamespec_smoke_execution_2026-10-21.json",
           "configs/llm_gamespec_smoke_v2_2026-10-23.json", "scripts/run_gamespec_scope_ablation.py",
           "tests/test_gamespec_scope_ablation.py"]


def package():
    spec = json.loads((ROOT / SPEC).read_text())
    base = json.loads((ROOT / spec["base_manifest"]).read_text())
    v2 = json.loads((ROOT / spec["v2_specification"]).read_text())
    return materialize(base, v2, spec)


def hashes():
    return {p: sha256((ROOT / p).read_bytes()).hexdigest() for p in SOURCES}


def validate():
    manifest, bundle = package()
    lock = json.loads((ROOT / LOCK).read_text())
    if hashes() != lock["sha256"] or bundle != json.loads((ROOT / BUNDLE).read_text()):
        raise ValueError("frozen execution package mismatch")
    for p, checksum in lock["historical_baselines_sha256"].items():
        if sha256((ROOT / p).read_bytes()).hexdigest() != checksum:
            raise ValueError("historical failure baseline changed")
    return manifest, bundle


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "check", "run", "replay"))
    args = parser.parse_args()
    manifest, bundle = package()
    if args.mode == "prepare":
        if OUTPUT.exists():
            raise FileExistsError("provider journal exists; cannot refreeze")
        write_json(ROOT / BUNDLE, bundle)
        write_json(ROOT / LOCK, {"version": "gamespec-v3-lock", "sha256": hashes(),
                                "provider_calls_executed": 0,
                                "historical_baselines_sha256": {
                                    p: sha256((ROOT / p).read_bytes()).hexdigest()
                                    for p in manifest["ablation"]["historical_baselines"]}})
        print("Prepared 144-trial package; commit before requests.")
        return
    manifest, bundle = validate()
    if args.mode == "replay":
        report = json.loads(OUTPUT.read_text())
        result = replay(manifest, bundle, report)
        write_json(OUTPUT.with_name("independent_replay.json"), result)
        print(json.dumps(result, indent=2))
        return
    for p in SOURCES + [LOCK]:
        if subprocess.check_output(["git", "show", f"HEAD:{p}"], cwd=ROOT) != (ROOT / p).read_bytes():
            raise ValueError(f"dispatch source not committed: {p}")
    if args.mode == "check":
        print("Committed execution package and historical failures verified; no API requests.")
        return
    if OUTPUT.exists():
        raise FileExistsError("output exists; replay only, never overwrite/resend")
    key = os.environ.get("OPENAI_API_KEY") or load_dotenv_value(ROOT / ".env", "OPENAI_API_KEY")
    if not key:
        raise RuntimeError("API credential unavailable")
    from openai import OpenAI
    import tiktoken
    encoding = tiktoken.encoding_for_model(manifest["model"]["model_id"])
    client = OpenAI(api_key=key, base_url="https://api.openai.com/v1",
                    timeout=manifest["model"]["timeout_seconds"], max_retries=0)
    runner = ScopeAblationRunner(manifest, bundle, client, OUTPUT, lambda text: len(encoding.encode(text)))
    report = runner.run()
    print(json.dumps({"status": report["status"], "stop_reason": report["stop_reason"],
                      "analysis": report["analysis"]}, indent=2))
    if report["status"] != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
