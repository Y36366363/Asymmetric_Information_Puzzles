import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RESULT = (
    ROOT / "research/results/average_strategy_estimator_validation_2026-10-11.json"
)


def report():
    return json.loads(RESULT.read_text())


def test_kuhn_passes_every_frozen_estimator_gate():
    kuhn = report()["games"]["canonical_kuhn_poker"]
    assert kuhn["passed"] is True
    assert all(kuhn["gates"].values())
    assert kuhn["candidate_evaluation"]["exploitability"] == pytest.approx(
        0.002889173226058822
    )
    assert kuhn["diagnostics"]["average_strategy_observation_count_coverage"] == 1
    assert kuhn["diagnostics"]["average_strategy_observation_weight_coverage"] == 1


def test_one_die_exact_best_response_passes_but_observation_coverage_fails():
    liar = report()["games"]["one_die_stepwise_liars_dice"]
    assert liar["candidate_evaluation"]["passed"] is True
    assert liar["candidate_evaluation"]["exploitability"] == pytest.approx(
        0.0014140878242663302
    )
    assert liar["gates"]["independent_exploitability"] is True
    assert liar["gates"]["observation_coverage"] is False
    assert liar["passed"] is False
    diagnostics = liar["diagnostics"]
    assert diagnostics["positive_observation_count_information_sets"] == 293
    assert diagnostics["positive_observation_weight_information_sets"] == 189
    assert diagnostics["average_strategy_observation_count_coverage"] == pytest.approx(
        293 / 348
    )
    assert diagnostics["average_strategy_observation_weight_coverage"] == pytest.approx(
        189 / 348
    )


def test_regret_semantics_match_legacy_but_five_die_remains_blocked():
    value = report()
    for game in value["games"].values():
        assert game["diagnostics"]["regret_trace_parity_with_comparison"] is True
        assert game["diagnostics"]["visit_trace_parity_with_comparison"] is True
        assert game["gates"]["fixed_seed_reproducible"] is True
    assert value["all_small_game_gates_passed"] is False
    assert value["five_die_preregistration_allowed"] is False
    assert value["five_die_training_performed"] is False
    assert value["audit_completed"] is True
    assert value["passed"] is False
