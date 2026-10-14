import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RESULT = (
    ROOT / "research/results/five_die_coverage_aware_joint_2026-10-14.json"
)


def report():
    return json.loads(RESULT.read_text())


def test_frozen_run_completed_all_checkpoints_and_improved_exploitability():
    value = report()
    checkpoints = value["checkpoints"]
    assert value["audit_completed"] is True
    assert [point["iterations"] for point in checkpoints] == [
        62_208,
        93_312,
        124_416,
    ]
    assert checkpoints[-1]["independent_evaluation"]["exploitability"] == (
        pytest.approx(0.04000262629639495)
    )
    assert value["gates"]["independent_exploitability"] is True
    assert value["gates"]["improved_over_retained_joint_result"] is True
    assert value["convergence"]["exploitability_nonincreasing"] is True


def test_coverage_and_fallback_gates_fail_without_relabeling_evidence():
    value = report()
    final = value["checkpoints"][-1]
    assert final["visited_information_sets"] == 51_996
    assert final["visited_coverage"] == pytest.approx(51_996 / 87_192)
    assert final["fallback_information_sets"] == 61_475
    assert final["fallback_fraction"] == pytest.approx(61_475 / 87_192)
    assert final["raw_observation_weight_coverage"] == pytest.approx(
        1 - 61_475 / 87_192
    )
    assert final["fallback_exactly_equals_zero_weight_set"] is True
    assert value["gates"]["positive_visit_coverage"] is False
    assert value["gates"]["fallback_fraction"] is False
    assert value["candidate_passed"] is False


def test_failed_candidate_and_incomplete_tree_keep_runtime_closed():
    value = report()
    assert value["gates"]["complete_structural_audit_passed"] is False
    assert value["structural_audit"]["complete"] is False
    assert value["promotion"]["runtime_epsilon_gto_allowed"] is False
    assert value["promotion"]["status"] == "coverage_aware_joint_candidate_failed"
    assert value["passed"] is False
    assert all(item["passed"] is False for item in value["retained_failed_experiments"])
