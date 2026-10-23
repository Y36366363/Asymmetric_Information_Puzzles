#!/usr/bin/env python3
"""Freeze before requests, run once, independently replay provider evidence."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess

from aip.benchmark.completion import load_dotenv_value
from aip.benchmark.gamespec_smoke import write_json
from aip.benchmark.gamespec_smoke_v2 import (
    V2SmokeRunner, diagnostic_required, independent_replay, materialize_manifest, v2_bundle,
)

ROOT = Path(__file__).resolve().parents[1]
SPEC = "configs/llm_gamespec_smoke_v2_2026-10-23.json"
LOCK = ROOT / "configs/gamespec_smoke_v2_lock_2026-10-23.json"
OUTPUT = ROOT / "research/results/gamespec_model_smoke_v2_2026-10-23/report.json"
SOURCES = [SPEC, "configs/llm_gamespec_smoke_execution_2026-10-21.json",
           "src/aip/benchmark/gamespec_smoke.py", "src/aip/benchmark/gamespec_smoke_v2.py",
           "src/aip/core/game_spec.py", "src/aip/core/game_spec_pilot.py",
           "src/aip/core/game_spec_smoke.py", "scripts/run_gamespec_smoke_v2.py"]


def package(diagnostic=False):
    spec = json.loads((ROOT / SPEC).read_text())
    base = json.loads((ROOT / spec["inherits"]).read_text())
    manifest = materialize_manifest(base, spec, diagnostic)
    return manifest, v2_bundle(base, manifest)


def hashes():
    return {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCES}


class DiagnosticClient:
    """Explicitly record/supply effort=none; all other transport settings shared."""
    def __init__(self, client):
        self.client = client
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        return self.client.chat.completions.create(**kwargs, reasoning_effort="none")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "check", "run", "replay"))
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    output = OUTPUT.with_name("diagnostic_report.json") if args.diagnostic else OUTPUT
    manifest, bundle = package(args.diagnostic)
    if args.mode == "prepare":
        write_json(LOCK, {"version": "gamespec-v2-lock", "sha256": hashes(),
                          "baseline_sha256": sha256((ROOT / manifest["v2_specification"]["reporting"]["baseline"]).read_bytes()).hexdigest(),
                          "provider_calls_executed": 0})
        print("Prepared lock; commit before running.")
        return
    lock = json.loads(LOCK.read_text())
    if lock["sha256"] != hashes():
        raise ValueError("frozen sources changed")
    baseline = ROOT / manifest["v2_specification"]["reporting"]["baseline"]
    if sha256(baseline.read_bytes()).hexdigest() != lock["baseline_sha256"]:
        raise ValueError("v1 baseline changed")
    if args.mode == "replay":
        report = json.loads(output.read_text())
        analysis = independent_replay(manifest, bundle, report)
        write_json(output.with_name("diagnostic_replay.json" if args.diagnostic else "independent_replay.json"), analysis)
        print(json.dumps(analysis, indent=2))
        return
    for name in SOURCES + [str(LOCK.relative_to(ROOT))]:
        if subprocess.check_output(["git", "show", f"HEAD:{name}"], cwd=ROOT) != (ROOT / name).read_bytes():
            raise ValueError(f"uncommitted source: {name}")
    if args.mode == "check":
        print("Frozen v2 sources and unchanged v1 baseline verified; no provider calls.")
        return
    if output.exists():
        raise FileExistsError("output exists; use replay, not repeat calls")
    if args.diagnostic:
        primary = json.loads(OUTPUT.read_text())
        primary_manifest, primary_bundle = package()
        independent_replay(primary_manifest, primary_bundle, primary)
        if not diagnostic_required(primary):
            raise ValueError("preregistered stronger-model trigger not met")
    key = os.environ.get("OPENAI_API_KEY") or load_dotenv_value(ROOT / ".env", "OPENAI_API_KEY")
    if not key:
        raise RuntimeError("API credential unavailable; no requests")
    from openai import OpenAI
    import tiktoken
    client = OpenAI(api_key=key, base_url="https://api.openai.com/v1",
                    timeout=manifest["model"]["timeout_seconds"], max_retries=0)
    if args.diagnostic:
        client = DiagnosticClient(client)
    encoding = tiktoken.encoding_for_model(manifest["model"]["model_id"])
    runner = V2SmokeRunner(manifest, bundle, client, output, lambda text: len(encoding.encode(text)))
    runner.report["execution_parameters"] = manifest["model"]
    result = runner.run()
    print(json.dumps({"status": result["status"], "stop_reason": result["stop_reason"],
                      "analysis": result["analysis"]}, indent=2))
    if result["status"] != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
