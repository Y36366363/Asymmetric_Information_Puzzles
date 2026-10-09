import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "research/results/five_die_stepwise_coverage_2026-10-09.json"
BASELINE = ROOT / "research/results/five_die_stepwise_candidate_2026-10-08.json"


def test_coverage_experiment_retains_baseline_and_all_frozen_checkpoints():
    report = json.loads(RESULT.read_text())
    baseline = json.loads(BASELINE.read_text())
    assert report["retained_negative_control"]["independent_exploitability"] == (
        baseline["independent_evaluation"]["exploitability"]
    )
    assert report["retained_negative_control"]["passed"] is False
    assert [point["iterations"] for point in report["checkpoints"]] == [
        5_000,
        12_600,
        25_200,
    ]
    assert all(
        point["independent_evaluation"]["action_value_information_sets"]
        == 87_192
        for point in report["checkpoints"]
    )


def test_real_coverage_passes_but_independent_exploitability_still_fails():
    report = json.loads(RESULT.read_text())
    final = report["checkpoints"][-1]
    assert final["initialized_information_sets"] == 87_192
    assert final["visited_information_sets"] == 44_140
    assert final["visited_coverage"] == pytest.approx(0.5062391045050004)
    assert final["independent_evaluation"]["exploitability"] == pytest.approx(
        0.1465006764898036
    )
    assert report["gates"]["visited_coverage_passed"] is True
    assert report["gates"]["improved_over_retained_baseline"] is True
    assert report["gates"]["independent_exploitability_passed"] is False
    assert report["gates"]["candidate_passed"] is False


def test_failed_candidate_cannot_enable_runtime_epsilon_gto():
    report = json.loads(RESULT.read_text())
    assert report["audit_completed"] is True
    assert report["structural_audit"]["histories"] == 140_000
    assert report["structural_audit"]["complete"] is False
    assert report["promotion"]["runtime_epsilon_gto_allowed"] is False
    assert report["passed"] is False
