import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN = (
    ROOT
    / "configs/five_die_stepwise_joint_stratification_preregistration_2026-10-10.json"
)


def plan():
    return json.loads(PLAN.read_text())


def test_joint_experiment_is_separate_frozen_and_retains_both_failures():
    value = plan()
    assert value["frozen_before_training"] is True
    assert value["experiment_id"] == "five_die_stepwise_joint_stratification_v1"
    assert value["retained_experiments"] == [
        "research/results/five_die_stepwise_candidate_2026-10-08.json",
        "research/results/five_die_stepwise_coverage_2026-10-09.json",
    ]
    assert value["comparison_baseline"]["passed_gate"] is False
    assert value["comparison_baseline"]["independent_exploitability"] == (
        0.1465006764898036
    )


def test_budget_is_fixed_in_complete_true_distribution_epochs():
    algorithm = plan()["algorithm"]
    assert algorithm["algorithm_id"] == (
        "joint_marginal_stratified_external_sampling_mccfr_v1"
    )
    assert algorithm["seed"] == 20261010
    assert algorithm["epoch_size"] == 6**5 == 7_776
    assert algorithm["epochs"] == 8
    assert algorithm["iterations"] == algorithm["epoch_size"] * algorithm["epochs"]
    assert algorithm["checkpoints"] == [7_776, 31_104, 62_208]
    assert algorithm["average_strategy_estimator"] == (
        "unchanged_uniform_iteration_weighting"
    )


def test_preregistration_does_not_confuse_marginal_strata_with_joint_enumeration():
    value = plan()
    algorithm = value["algorithm"]
    assert algorithm["marginal_distribution_guarantee"].startswith(
        "each_hand_exactly_matches_true"
    )
    assert algorithm["joint_distribution_claim"].startswith(
        "unbiased_random_pairing_not_exhaustive"
    )
    assert value["schedule_validation"][
        "exact_histogram_multiplicities_for_each_hand_each_epoch"
    ] is True
    assert value["schedule_validation"]["reject_mid_experiment_parameter_changes"] is True


def test_independent_and_real_coverage_gates_are_fixed():
    value = plan()
    endpoints = value["primary_endpoints"]
    assert endpoints["final_independent_exploitability"]["maximum"] == 0.05
    assert endpoints["visited_information_set_coverage"]["minimum"] == 0.6
    assert endpoints["visited_information_set_coverage"][
        "uses_positive_visit_count_not_initialized_policy_presence"
    ] is True
    assert value["convergence_trace"][
        "independent_best_response_at_every_checkpoint"
    ] is True
    assert value["promotion"]["runtime_epsilon_gto_allowed_during_this_experiment"] is False
