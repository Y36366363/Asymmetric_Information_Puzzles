import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "configs/five_die_stepwise_mccfr_preregistration_2026-10-08.json"


def test_mccfr_candidate_budget_seed_and_gate_are_frozen():
    plan = json.loads(PLAN.read_text())
    assert plan["frozen_before_training"] is True
    assert plan["rules_id"] == "five_die_liar_two_player_stepwise_v1"
    assert plan["algorithm"] == {
        "algorithm_id": "external_sampling_mccfr",
        "seed": 20261008,
        "iterations": 5000,
        "unvisited_information_set_completion": "uniform_and_explicitly_labeled",
        "training_regret_is_not_a_certificate": True,
    }
    assert plan["candidate_gate"]["maximum_independent_exploitability"] == 0.05
    assert plan["candidate_gate"]["required_information_sets"] == 87_192


def test_runtime_promotion_is_blocked_until_both_independent_gates_pass():
    plan = json.loads(PLAN.read_text())
    assert plan["structural_gate"]["expected_complete_histories"] == 43_818_013
    assert plan["structural_gate"]["expected_information_sets"] == 87_192
    assert plan["structural_gate"][
        "complete_resumable_tree_audit_required_for_promotion"
    ] is True
    assert plan["promotion"][
        "runtime_epsilon_gto_requires_both_candidate_and_structural_gates"
    ] is True
    assert plan["promotion"]["runtime_epsilon_gto_allowed_during_this_pilot"] is False
