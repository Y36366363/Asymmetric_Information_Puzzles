import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "configs/average_strategy_estimator_validation_2026-10-11.json"


def plan():
    return json.loads(PLAN.read_text())


def test_small_game_estimator_validation_is_frozen_before_training():
    value = plan()
    assert value["frozen_before_training"] is True
    assert value["candidate_algorithm_id"] == (
        "reach_weighted_external_sampling_mccfr_v1"
    )
    assert value["comparison_algorithm_id"] == "external_sampling_mccfr"
    assert value["estimator"]["regret_update_semantics_changed"] is False
    assert value["estimator"]["legacy_external_sampling_semantics_changed"] is False


def test_exact_small_game_budgets_and_independent_gates_are_fixed():
    games = plan()["games"]
    assert games["canonical_kuhn_poker"]["iterations"] == 50_000
    assert games["canonical_kuhn_poker"]["required_information_sets"] == 12
    assert games["one_die_stepwise_liars_dice"]["iterations"] == 100_000
    assert games["one_die_stepwise_liars_dice"]["required_information_sets"] == 348
    for game in games.values():
        assert game["seed"] == 20261011
        assert game["maximum_independent_exploitability"] == 0.01


def test_five_die_is_blocked_until_every_small_game_gate_passes():
    value = plan()
    assert value["shared_gates"][
        "all_games_must_pass_before_five_die_preregistration"
    ] is True
    assert value["five_die_boundary"][
        "train_five_die_candidate_in_this_experiment"
    ] is False
    assert value["five_die_boundary"]["do_not_extend_2026_10_10_budget"] is True
