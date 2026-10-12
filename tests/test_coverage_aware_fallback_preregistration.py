import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN = (
    ROOT
    / "configs/coverage_aware_average_strategy_fallback_validation_2026-10-12.json"
)


def plan():
    return json.loads(PLAN.read_text())


def test_fallback_experiment_is_separate_frozen_and_retains_failure():
    value = plan()
    assert value["frozen_before_training"] is True
    assert value["retained_failed_experiment"].endswith(
        "average_strategy_estimator_validation_2026-10-11.json"
    )
    assert value["candidate_algorithm_id"] == (
        "coverage_aware_reach_weighted_external_sampling_mccfr_v1"
    )


def test_fallback_rule_is_exact_and_cannot_fabricate_observation_evidence():
    rule = plan()["fallback_rule"]
    assert rule["positive_cumulative_observation_weight"].startswith(
        "normalized_reach_weighted"
    )
    assert rule["zero_cumulative_observation_weight"] == (
        "current_regret_matching_strategy"
    )
    assert rule["changes_regret_updates"] is False
    assert rule["changes_sampling"] is False
    assert rule["creates_observation_evidence"] is False
    assert rule["fallback_use_must_be_exported_per_information_set"] is True


def test_small_game_budgets_and_fallback_limits_are_fixed():
    games = plan()["games"]
    assert games["canonical_kuhn_poker"]["iterations"] == 50_000
    assert games["canonical_kuhn_poker"]["maximum_fallback_fraction"] == 0
    assert games["one_die_stepwise_liars_dice"]["iterations"] == 100_000
    assert games["one_die_stepwise_liars_dice"]["maximum_fallback_fraction"] == 0.5
    for game in games.values():
        assert game["seed"] == 20261012
        assert game["maximum_independent_exploitability"] == 0.01


def test_five_die_remains_blocked_until_every_small_game_gate_passes():
    value = plan()
    assert value["shared_gates"][
        "fallback_exactly_equals_zero_weight_information_sets"
    ] is True
    assert value["shared_gates"][
        "all_games_must_pass_before_five_die_preregistration"
    ] is True
    assert value["five_die_boundary"][
        "train_five_die_candidate_in_this_experiment"
    ] is False
    assert value["five_die_boundary"][
        "do_not_extend_any_prior_five_die_budget"
    ] is True
