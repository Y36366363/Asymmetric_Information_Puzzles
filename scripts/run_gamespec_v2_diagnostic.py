#!/usr/bin/env python3
"""Mechanical diagnostic startup repair; original primary dispatch stays frozen."""
import argparse
import json
import os
import subprocess

from aip.benchmark.completion import load_dotenv_value
from aip.benchmark.gamespec_smoke_v2 import V2SmokeRunner, diagnostic_required, independent_replay
from run_gamespec_smoke_v2 import DiagnosticClient, OUTPUT, ROOT, package

AMENDMENT = "configs/gamespec_v2_diagnostic_execution_amendment_2026-10-23.json"


def byte_upper_bound(text):
    return len(text.encode("utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("check", "run"))
    args = parser.parse_args()
    subprocess.run([os.sys.executable, "scripts/run_gamespec_smoke_v2.py", "check"], cwd=ROOT, check=True)
    for name in (AMENDMENT, "scripts/run_gamespec_v2_diagnostic.py"):
        if subprocess.check_output(["git", "show", f"HEAD:{name}"], cwd=ROOT) != (ROOT / name).read_bytes():
            raise ValueError("diagnostic startup amendment is not committed")
    primary_manifest, primary_bundle = package()
    primary = json.loads(OUTPUT.read_text())
    independent_replay(primary_manifest, primary_bundle, primary)
    if not diagnostic_required(primary):
        raise ValueError("diagnostic trigger not met")
    manifest, bundle = package(True)
    if args.mode == "check":
        # Worst existing primary request, with explicit chat overhead, is still in cap.
        largest = max(sum(byte_upper_bound(m["content"]) + 10 for m in a["messages"]) + 32
                      for a in primary["attempts"])
        print(json.dumps({"maximum_primary_request_byte_bound": largest,
                          "input_token_cap": manifest["model"]["maximum_input_tokens"],
                          "provider_calls": 0}))
        return
    output = OUTPUT.with_name("diagnostic_report.json")
    if output.exists():
        raise FileExistsError("diagnostic output exists; replay only")
    key = os.environ.get("OPENAI_API_KEY") or load_dotenv_value(ROOT / ".env", "OPENAI_API_KEY")
    if not key:
        raise RuntimeError("credential unavailable")
    from openai import OpenAI
    client = DiagnosticClient(OpenAI(api_key=key, base_url="https://api.openai.com/v1",
                                     timeout=manifest["model"]["timeout_seconds"], max_retries=0))
    runner = V2SmokeRunner(manifest, bundle, client, output, byte_upper_bound)
    runner.report["execution_parameters"] = manifest["model"]
    runner.report["execution_amendment"] = AMENDMENT
    runner.report["input_preflight"] = "UTF-8 byte upper bound plus original chat overhead"
    result = runner.run()
    print(json.dumps({"status": result["status"], "stop_reason": result["stop_reason"],
                      "analysis": result["analysis"]}, indent=2))
    if result["status"] != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
