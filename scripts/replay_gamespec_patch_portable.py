#!/usr/bin/env python3
"""Portable offline scoring replay: no SDK, API credentials or host runtime match.

The original dispatcher still enforces its exact runtime lock before API calls.
This post-run utility checks frozen source/request bytes and recomputes scores.
"""
from hashlib import sha256
import json

from aip.benchmark.gamespec_patch_diagnostic import replay
from aip.benchmark.gamespec_smoke import digest
from run_gamespec_patch_diagnostic import ROOT, LOCK, OUT, hashes, package, requests


def verify():
    lock = json.loads((ROOT / LOCK).read_text()); m, b = package()
    if hashes() != lock["sha256"] or requests() != lock["requests"] or digest(requests()) != lock["requests_sha256"]:
        raise ValueError("frozen sources or requests changed")
    if digest(m) != lock["manifest_sha256"] or digest(b) != lock["bundle_sha256"]:
        raise ValueError("manifest or bundle changed")
    comparison = json.loads((OUT / "comparison.json").read_text())
    for p, h in comparison["sha256"].items():
        if sha256((ROOT / p).read_bytes()).hexdigest() != h: raise ValueError("result input hash changed")
    result = replay(m, b, json.loads((OUT / "luna6.json").read_text()))
    if result != json.loads((OUT / "luna6_rescored.json").read_text()) or result["analysis"] != comparison["analysis"]:
        raise ValueError("saved score or comparison changed")
    return {"raw_rescoring_agrees": True, "requests_verified": 72,
        "sdk_or_network_required": False, "historical_runtime_match_rechecked": False,
        "historical_runtime_lock_present": True, "dispatch_authority": False,
        "reason": "Portable replay verifies scoring, not authority to execute a request under this machine's runtime."}


if __name__ == "__main__": print(json.dumps(verify()))
