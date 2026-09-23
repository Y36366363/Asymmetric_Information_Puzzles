"""Tests for the exact four-card Goofspiel horizontal decision adapter."""

from fractions import Fraction

import pytest

from aip.benchmark.goofspiel import (
    build_goofspiel_oracle_probes,
    candidate_goofspiel_probes,
)
from aip.benchmark.types import AgentDecision, BeliefOutput


def test_candidate_enumeration_covers_all_nonterminal_multiaction_states():
    probes = candidate_goofspiel_probes()
    assert len(probes) == 4 + 192 + 432
    assert {len(probe.player_cards) for probe in probes} == {2, 3, 4}
    assert len({probe.probe_id for probe in probes}) == len(probes)


def test_frozen_panel_is_deterministic_stage_stratified_and_nontrivial():
    probes = build_goofspiel_oracle_probes()
    assert probes == build_goofspiel_oracle_probes()
    assert len(probes) == 30
    assert sum(len(probe.player_cards) == 4 for probe in probes) == 4
    assert sum(len(probe.player_cards) == 3 for probe in probes) == 13
    assert sum(len(probe.player_cards) == 2 for probe in probes) == 13
    assert all(
        max(probe.exact_action_values.values())
        > min(probe.exact_action_values.values())
        for probe in probes
    )


def test_probe_scores_exact_best_response_and_equilibrium_belief():
    probe = build_goofspiel_oracle_probes()[0]
    best = max(probe.exact_action_values, key=probe.exact_action_values.get)
    belief = BeliefOutput(
        "opponent_current_bid",
        {label: float(probability) for label, probability in probe.opponent_bid_belief.items()},
    )
    result = probe.evaluate(AgentDecision(best, 1.0, belief=belief))
    assert result["actionRegret"] == pytest.approx(0)
    assert result["beliefBrierToEquilibriumOpponent"] == pytest.approx(0)
    assert 0 <= result["equilibriumActionProbability"] <= 1


def test_probe_artifact_preserves_exact_solver_provenance_and_normalization():
    for probe in build_goofspiel_oracle_probes():
        artifact = probe.to_artifact()
        assert artifact["oracle"] == "exact_backward_induction_plus_zero_sum_matrix"
        assert sum(probe.equilibrium_policy.values()) == Fraction(1)
        assert sum(probe.opponent_bid_belief.values()) == Fraction(1)
        assert tuple(
            int(action.action_id.removeprefix("bid:"))
            for action in probe.decision_input().legal_actions
        ) == probe.player_cards


def test_panel_size_is_frozen_to_30_states():
    with pytest.raises(ValueError, match="exactly 30"):
        build_goofspiel_oracle_probes(12)
