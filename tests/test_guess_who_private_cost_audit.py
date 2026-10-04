import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = (
    ROOT / "research/results/guess_who_private_cost_signaling_2026-10-04.json"
)


def test_private_cost_primary_endpoint_is_independently_valid_zero_result():
    report = json.loads(AUDIT.read_text())
    endpoint = report["primary_endpoint"]
    assert endpoint["classification"] == "zero_result"
    assert endpoint["value"] <= endpoint["null_result_threshold"]
    assert endpoint["reversed_enumeration_value"] <= endpoint[
        "null_result_threshold"
    ]
    assert report["checks"]["frozen_rules_match"] is True
    assert report["checks"]["tree_audit"] is True
    assert report["checks"]["independent_exploitability_gate"] is True
    assert report["checks"]["endpoint_enumeration_invariance"] is True
    assert report["runtime_epsilon_gto_allowed"] is False


def test_preregistered_5000_iteration_cross_checks_all_pass():
    report = json.loads(AUDIT.read_text())
    algorithms = report["regret_minimization_cross_check"]
    assert set(algorithms) == {"vanilla_cfr", "cfr_plus", "dcfr"}
    assert all(record["iterations"] == 5_000 for record in algorithms.values())
    assert all(
        record["independent_evaluation"]["passed"]
        for record in algorithms.values()
    )
    assert report["checks"]["all_cfr_cross_checks"] is True
    assert report["undertrained_negative_control"]["passed_gate"] is False
    assert report["passed"] is True


def test_private_costs_change_secondary_timing_without_claiming_signal():
    report = json.loads(AUDIT.read_text())
    behavior = report["equilibrium_behavior"]
    assert behavior["expected_question_cost_by_seat"]["player_0"] > 0
    assert behavior["expected_question_cost_by_seat"]["player_1"] > 0
    assert behavior["blind_guess_action_mass"] == 0
    assert behavior["ambiguous_terminal_guess_probability"] > 0.8
    assert behavior["maximum_root_policy_l1_by_private_secret"] <= 1e-8
