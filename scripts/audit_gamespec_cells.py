#!/usr/bin/env python3
"""Replay frozen v11, export cell differences and prepare an offline patch contract."""
from hashlib import sha256
import json
from pathlib import Path

from aip.benchmark.gamespec_cell_audit import audit_reports
from aip.benchmark.gamespec_feedback_repair import replay
from run_gamespec_feedback_repair import package, validate, preserve_json, OUT as SOURCE

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research/results/gamespec_cell_audit_v12_2026-11-05.json"


def build():
    validate()
    reports = {}
    for tag in ("luna6", "sol61"):
        m, b = package(tag)
        reports[tag] = json.loads((SOURCE / f"{tag}.json").read_text())
        replay(m, b, reports[tag])
    result = audit_reports(reports, b)
    paths = [SOURCE / f"{tag}.json" for tag in reports] + [
        ROOT / "configs/gamespec_boundary_panel_v7_2026-10-29.json",
        ROOT / "configs/gamespec_feedback_repair_v11_lock_2026-11-03.json",
        ROOT / "src/aip/benchmark/gamespec_cell_audit.py", Path(__file__)]
    result["sha256"] = {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in paths}
    result["both_original_replays_agree"] = True
    return result


if __name__ == "__main__":
    result = build()
    preserve_json(OUT, result)
    print(json.dumps({k: result[k] for k in ("all_output_count", "selected_count", "selected_classes", "selected_input_kinds", "selected_unchanged_tables", "both_original_replays_agree")}))
