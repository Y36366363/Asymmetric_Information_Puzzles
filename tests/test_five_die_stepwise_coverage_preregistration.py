import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "configs/five_die_stepwise_coverage_preregistration_2026-10-09.json"


def test_coverage_experiment_is_frozen_and_keeps_failed_baseline():
    plan = json.loads(PLAN.read_text())
    assert plan["frozen_before_training"] is True
    assert plan["rules_id"] == "five_die_liar_two_player_stepwise_v1"
    assert plan["retained_negative_control"].endswith(
        "five_die_stepwise_candidate_2026-10-08.json"
    )
    assert plan["baseline"]["iterations"] == 5_000
    assert plan["baseline"]["sampled_information_sets"] == 25_945
    assert plan["baseline"]["passed_gate"] is False


def test_stratified_budget_seed_and_checkpoints_are_fixed():
    algorithm = json.loads(PLAN.read_text())["algorithm"]
    assert algorithm["algorithm_id"] == (
        "stratified_private_hand_external_sampling_mccfr_v1"
    )
    assert algorithm["seed"] == 20261009
    assert algorithm["iterations"] == 25_200
    assert algorithm["checkpoints"] == [5_000, 12_600, 25_200]
    assert algorithm["information_set_initialization"].startswith("all_87192")
    assert algorithm["training_regret_is_not_a_certificate"] is True


def test_coverage_and_independent_gates_cannot_be_replaced_by_initialization():
    plan = json.loads(PLAN.read_text())
    endpoints = plan["primary_endpoints"]
    assert endpoints["final_independent_exploitability"]["maximum"] == 0.05
    assert endpoints["visited_information_set_coverage"]["minimum"] == 0.5
    assert endpoints["visited_information_set_coverage"][
        "uses_positive_visit_count_not_initialized_policy_presence"
    ] is True
    assert plan["convergence_trace"][
        "independent_best_response_at_every_checkpoint"
    ] is True
    assert plan["promotion"][
        "runtime_epsilon_gto_requires_final_exploitability_and_complete_structural_audit"
    ] is True
    assert plan["promotion"]["runtime_epsilon_gto_allowed_during_this_experiment"] is False
