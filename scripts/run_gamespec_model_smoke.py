#!/usr/bin/env python3
"""Prepare, integrity-check, run and replay the frozen provider smoke."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess

from aip.benchmark.completion import load_dotenv_value
from aip.benchmark.gamespec_smoke import SmokeRunner, analyze, make_bundle, write_json

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "configs/llm_gamespec_smoke_execution_2026-10-21.json"
BUNDLE = ROOT / "configs/gamespec_smoke_dispatch_bundle_2026-10-22.json"
LOCK = ROOT / "configs/gamespec_smoke_dispatch_lock_2026-10-22.json"
DEFAULT_OUTPUT = ROOT / "research/results/gamespec_model_smoke_2026-10-22/report.json"
SOURCES = [
    "configs/llm_gamespec_smoke_execution_2026-10-21.json",
    "configs/gamespec_smoke_error_taxonomy_v1.json",
    "configs/gamespec_smoke_dispatch_bundle_2026-10-22.json",
    "src/aip/benchmark/gamespec_smoke.py",
    "src/aip/core/game_spec_pilot.py", "src/aip/core/game_spec_smoke.py",
    "src/aip/core/game_spec.py", "scripts/run_gamespec_model_smoke.py",
]


def hashes():
    return {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCES}


def prepare():
    manifest = json.loads(MANIFEST.read_text())
    write_json(BUNDLE, make_bundle(manifest))
    write_json(LOCK, {"version": "gamespec-dispatch-lock-v1", "sha256": hashes(),
                      "provider_calls_executed": 0,
                      "authorization": "2026-10-22 user explicitly requested fixed GPT-4.1-mini smoke within frozen caps",
                      "execution_note": "Verify lock and all listed files committed before provider client creation. Never resume/replay an existing report with provider requests."})
    print("Dispatch bundle and integrity lock prepared; commit before execution.")


def validate_lock():
    lock = json.loads(LOCK.read_text())
    if lock["sha256"] != hashes():
        raise ValueError("dispatch package differs from the frozen lock")
    for name in SOURCES + [str(LOCK.relative_to(ROOT))]:
        committed = subprocess.check_output(["git", "show", f"HEAD:{name}"], cwd=ROOT)
        if committed != (ROOT / name).read_bytes():
            raise ValueError(f"dispatch file not committed at HEAD: {name}")
    manifest = json.loads(MANIFEST.read_text())
    bundle = json.loads(BUNDLE.read_text())
    if bundle != make_bundle(manifest):
        raise ValueError("materialized evidence bundle no longer matches fixed rules")
    return manifest, bundle


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "check", "run", "replay"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.mode == "prepare":
        prepare()
        return 0
    if args.mode == "replay":
        manifest = json.loads(MANIFEST.read_text())
        report = json.loads(args.output.read_text())
        replay = analyze(manifest, report)
        if replay != report["analysis"]:
            raise ValueError("saved analysis differs from journal replay")
        print(json.dumps(replay, indent=2))
        return 0
    manifest, bundle = validate_lock()
    if args.mode == "check":
        print("Committed dispatch lock and separate evidence files verified; no API calls.")
        return 0
    if args.output.exists():
        raise FileExistsError("output exists; use replay instead of making duplicate calls")
    key = os.environ.get("OPENAI_API_KEY") or load_dotenv_value(ROOT / ".env", "OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is unavailable; no requests dispatched")
    from openai import OpenAI
    import tiktoken
    encoding = tiktoken.encoding_for_model(manifest["model"]["model_id"])
    client = OpenAI(api_key=key, base_url="https://api.openai.com/v1",
                    timeout=manifest["model"]["timeout_seconds"], max_retries=0)
    runner = SmokeRunner(manifest, bundle, client, args.output,
                         lambda text: len(encoding.encode(text)))
    result = runner.run()
    print(json.dumps({"status": result["status"], "stop_reason": result["stop_reason"],
                      "analysis": result["analysis"]}, indent=2))
    return 0 if result["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
