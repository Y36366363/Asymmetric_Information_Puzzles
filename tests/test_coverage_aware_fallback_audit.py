import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RESULT = (
    ROOT
    / "research/results/coverage_aware_average_strategy_fallback_validation_2026-10-12.json"
)


def report():
    return json.loads(RESULT.read_text())


def test_fallback_is_exact_and_does_not_relabel_raw_coverage():
    value = report()
    kuhn = value["games"]["canonical_kuhn_poker"]
    liar = value["games"]["one_die_stepwise_liars_dice"]
    for game in (kuhn, liar):
        diagnostics = game["diagnostics"]
        assert diagnostics["fallback_exactly_equals_zero_weight_set"] is True
        assert diagnostics["fallback_creates_no_observation_evidence"] is True
        assert diagnostics["policy_changes_confined_to_fallback_set"] is True
        assert diagnostics["resolved_policy_coverage"] == 1
        assert all(diagnostics["trace_parity_with_reach_weighted"].values())
    assert kuhn["diagnostics"]["fallback_information_sets"] == 0
    assert liar["diagnostics"]["fallback_information_sets"] == 154
    assert liar["diagnostics"]["raw_observation_weight_coverage"] == pytest.approx(
        194 / 348
    )


def test_both_independent_exploitability_gates_pass():
    value = report()
    kuhn = value["games"]["canonical_kuhn_poker"]
    liar = value["games"]["one_die_stepwise_liars_dice"]
    assert kuhn["evaluations"]["candidate"]["exploitability"] == pytest.approx(
        0.0057514964132233965
    )
    assert liar["evaluations"]["candidate"]["exploitability"] == pytest.approx(
        0.0037455105474351047
    )
    assert kuhn["gates"]["independent_exploitability"] is True
    assert liar["gates"]["independent_exploitability"] is True


def test_retained_comparison_failure_keeps_five_die_closed():
    value = report()
    for game in value["games"].values():
        assert game["gates"]["not_materially_worse_than_reach_weighted"] is True
        assert game["gates"]["not_materially_worse_than_legacy"] is False
        assert game["passed"] is False
    assert value["retained_failure_unchanged"] is True
    assert value["all_small_game_gates_passed"] is False
    assert value["five_die_preregistration_allowed"] is False
    assert value["five_die_preregistration_created"] is False
    assert value["five_die_training_performed"] is False
    assert value["audit_completed"] is True
    assert value["passed"] is False
