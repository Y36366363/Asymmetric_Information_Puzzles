"""Offline regression over the retained real v2 run; never issues API calls."""
import importlib.util
import json
from pathlib import Path

from aip.benchmark.gamespec_smoke_v2 import independent_replay

ROOT = Path(__file__).resolve().parents[1]


def test_real_v2_primary_preserves_scope_failures_despite_main_ceiling():
    spec = importlib.util.spec_from_file_location("v2_dispatch", ROOT / "scripts/run_gamespec_smoke_v2.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    manifest, bundle = module.package()
    report = json.loads(module.OUTPUT.read_text())
    result = independent_replay(manifest, bundle, report)
    assert report["status"] == "completed"
    assert all(g["final_coverage"] == 20 for g in result["groups"].values())
    assert result["correct_oos"] == 0
    assert len(result["final_failures"]) == 15
    assert result["overall_scientific_pass"] is None
    assert result["false_certifications"] == 0
    assert report["stronger_model_diagnostic_required"]
    assert not report["runtime_epsilon_gto_allowed"]
    assert not report["adaptive_opponent_line_released"]
