from copy import deepcopy
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_auditor():
    spec = importlib.util.spec_from_file_location(
        "gamespec_provider_result_auditor",
        ROOT / "scripts/audit_gamespec_model_smoke_results.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inputs():
    return tuple(json.loads((ROOT / path).read_text()) for path in (
        "configs/llm_gamespec_smoke_execution_2026-10-21.json",
        "configs/gamespec_smoke_dispatch_bundle_2026-10-22.json",
        "research/results/gamespec_model_smoke_2026-10-22/report.json",
    ))


def test_real_negative_run_replays_raw_responses_and_preserves_failed_gates():
    manifest, bundle, report = inputs()
    result = load_auditor().audit(manifest, bundle, report)
    assert result["raw_response_replay_passed"]
    assert result["execution_status"] == "completed"
    assert result["frozen_gate_result"]["status"] == "fail"
    assert result["observations"]["false_certifications"] == 0
    assert not result["interpretation"]["formal_trial_execution_allowed"]
    assert not result["interpretation"]["adaptive_opponent_line_released"]
    assert result["provider_attempts"] <= manifest["schedule"]["maximum_calls"]


def test_raw_response_replay_detects_score_and_cost_tampering():
    manifest, bundle, report = inputs()
    changed = deepcopy(report)
    changed["trials"][0]["score"]["true_model_candidate_coverage"] = False
    changed["attempts"][0]["cost_usd"] = 0
    result = load_auditor().audit(manifest, bundle, changed)
    assert not result["raw_response_replay_passed"]
    assert "cost:0" in result["discrepancies"]
    assert any(error.startswith("final_score:") for error in result["discrepancies"])
