import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RESULT = (
    ROOT
    / "research/results/five_die_stepwise_joint_stratification_2026-10-10.json"
)
PRIOR = ROOT / "research/results/five_die_stepwise_coverage_2026-10-09.json"


def test_joint_audit_retains_prior_failure_and_all_fixed_checkpoints():
    report = json.loads(RESULT.read_text())
    prior = json.loads(PRIOR.read_text())
    assert report["retained_experiments"][-1]["independent_exploitability"] == (
        prior["checkpoints"][-1]["independent_evaluation"]["exploitability"]
    )
    assert report["retained_experiments"][-1]["passed"] is False
    assert [point["iterations"] for point in report["checkpoints"]] == [
        7_776,
        31_104,
        62_208,
    ]
    assert [point["completed_chance_epochs"] for point in report["checkpoints"]] == [
        1,
        4,
        8,
    ]


def test_schedule_audit_proves_true_marginals_without_false_joint_claim():
    schedule = json.loads(RESULT.read_text())["schedule_audit"]
    assert schedule["epochs"] == 8
    assert schedule["hand_schedules_checked"] == 32
    assert schedule["microstates_per_hand_schedule"] == 7_776
    assert schedule["histograms_per_hand_schedule"] == 252
    assert schedule["exact_true_marginals"] is True
    assert schedule["exhaustive_joint_histogram_pairs_claimed"] is False


def test_final_result_improves_but_fails_both_preregistered_primary_gates():
    report = json.loads(RESULT.read_text())
    final = report["checkpoints"][-1]
    assert final["visited_information_sets"] == 47_473
    assert final["visited_coverage"] == pytest.approx(0.544465088540233)
    assert final["independent_evaluation"]["exploitability"] == pytest.approx(
        0.06383412635222224
    )
    assert report["gates"]["improved_over_comparison_baseline"] is True
    assert report["gates"]["visited_coverage_passed"] is False
    assert report["gates"]["independent_exploitability_passed"] is False
    assert report["gates"]["candidate_passed"] is False


def test_failed_joint_candidate_remains_runtime_ineligible():
    report = json.loads(RESULT.read_text())
    assert report["audit_completed"] is True
    assert report["average_strategy_estimator_changed"] is False
    assert report["structural_audit"]["histories"] == 200_000
    assert report["structural_audit"]["complete"] is False
    assert report["promotion"]["runtime_epsilon_gto_allowed"] is False
    assert report["passed"] is False
