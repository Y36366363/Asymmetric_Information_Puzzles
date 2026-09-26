"""Cross-game tests for independently scored strategic intermediates."""

import json

import math

import pytest

from aip.benchmark.goofspiel import (
    GoofspielValueDecompositionOracle,
    build_goofspiel_oracle_probes,
)
from aip.benchmark.liar_transfer import (
    LiarValueDecompositionOracle,
    build_consensus_reference_profiles,
    select_profile_invariant_probes,
)
from aip.benchmark.love_letter import (
    LoveLetterValueDecompositionOracle,
    love_letter_action_id,
)
from aip.core import CFRGameProperties, compile_sequence_form, solve_sequence_form
from aip.puzzles.love_letter import LoveLetterCFRGame, LoveLetterIndependentEvaluator
from aip.benchmark.value_decomposition import (
    ValueDecomposition,
    parse_value_decomposition,
    score_value_decomposition,
)


def test_liar_decomposition_reconstructs_every_invariant_probe_value():
    probes = select_profile_invariant_probes(
        build_consensus_reference_profiles(), count=30
    )[0]
    oracle = LiarValueDecompositionOracle()
    for probe in probes:
        decomposition = oracle.decompose(probe)
        assert decomposition.posterior == probe.exact_posterior
        assert decomposition.immediate_action_values["challenge"] == pytest.approx(
            probe.exact_action_values["challenge"]
        )
        assert decomposition.continuation_action_values["challenge"] == 0
        assert decomposition.maximum_additivity_residual == pytest.approx(0)
        for action, value in probe.exact_action_values.items():
            assert decomposition.total_action_values[action] == pytest.approx(value)
        score = score_value_decomposition(decomposition, decomposition)
        assert score.to_artifact()["posteriorBrier"] == 0
        assert score.final_action_regret == pytest.approx(0)


def test_goofspiel_decomposition_reconstructs_all_30_exact_probe_values():
    oracle = GoofspielValueDecompositionOracle()
    for probe in build_goofspiel_oracle_probes():
        decomposition = oracle.decompose(probe)
        assert decomposition.maximum_additivity_residual < 1e-12
        assert decomposition.posterior == pytest.approx({
            label: float(probability)
            for label, probability in probe.opponent_bid_belief.items()
        })
        for action, value in probe.exact_action_values.items():
            assert decomposition.total_action_values[action] == pytest.approx(
                float(value), abs=1e-12
            )
        assert score_value_decomposition(
            decomposition, decomposition
        ).final_action_regret == pytest.approx(0)


def test_love_letter_subgame_decomposes_all_60_information_sets():
    game = LoveLetterCFRGame.late_round_subgame()
    solution = solve_sequence_form(
        compile_sequence_form(
            game,
            game_properties=CFRGameProperties(2, True, True, True),
            sparse=True,
        ),
        backend="scipy_highs",
    )
    evaluator = LoveLetterIndependentEvaluator(game)
    exact_values = evaluator.action_values(solution.policy)
    panel = LoveLetterValueDecompositionOracle(game).decompose_all(
        solution.policy
    )
    decompositions = panel.decompositions
    assert panel.total_information_sets == 60
    assert len(decompositions) + len(panel.zero_reach_information_sets) == 60
    assert panel.zero_reach_information_sets
    assert set(decompositions).union(panel.zero_reach_information_sets) == set(exact_values)
    assert any(
        abs(value) > 1e-12
        for decomposition in decompositions.values()
        for value in decomposition.immediate_action_values.values()
    )
    assert any(
        abs(value) > 1e-12
        for decomposition in decompositions.values()
        for value in decomposition.continuation_action_values.values()
    )
    for key, decomposition in decompositions.items():
        assert sum(decomposition.posterior.values()) == pytest.approx(1)
        assert decomposition.maximum_additivity_residual < 1e-12
        expected = {
            love_letter_action_id(action): value
            for action, value in exact_values[key].items()
        }
        assert decomposition.total_action_values == pytest.approx(expected)


def test_scorer_localizes_posterior_continuation_additivity_and_action_errors():
    reference = ValueDecomposition(
        posterior_target="hidden_move",
        posterior={"left": 0.75, "right": 0.25},
        immediate_action_values={"stop": 0.5, "continue": 0.0},
        continuation_action_values={"stop": 0.0, "continue": 1.0},
        total_action_values={"stop": 0.5, "continue": 1.0},
        chosen_action_id="continue",
    )
    candidate = ValueDecomposition(
        posterior_target="hidden_move",
        posterior={"left": 0.5, "right": 0.5},
        immediate_action_values={"stop": 0.5, "continue": 0.0},
        continuation_action_values={"stop": 0.0, "continue": 0.5},
        total_action_values={"stop": 0.5, "continue": 1.0},
        chosen_action_id="stop",
    )
    score = score_value_decomposition(candidate, reference)
    assert score.posterior_brier == pytest.approx(0.125)
    assert score.immediate_value_mae == 0
    assert score.continuation_value_mae == pytest.approx(0.25)
    assert score.total_value_mae == 0
    assert score.maximum_additivity_residual == pytest.approx(0.5)
    assert score.final_action_regret == pytest.approx(0.5)
    assert score.optimal_action_agreement is False
    assert score.decision_consistent_with_reported_values is False


def test_value_decomposition_rejects_malformed_nonfinite_or_mismatched_outputs():
    with pytest.raises(ValueError, match="sum to 1"):
        ValueDecomposition(
            "state", {"a": 0.2}, {"x": 0.0}, {"x": 0.0}, {"x": 0.0}, "x"
        )
    with pytest.raises(ValueError, match="finite"):
        ValueDecomposition(
            "state", {"a": 1.0}, {"x": math.nan}, {"x": 0.0}, {"x": 0.0}, "x"
        )
    reference = ValueDecomposition(
        "state", {"a": 1.0}, {"x": 0.0}, {"x": 0.0}, {"x": 0.0}, "x"
    )
    candidate = ValueDecomposition(
        "state", {"b": 1.0}, {"x": 0.0}, {"x": 0.0}, {"x": 0.0}, "x"
    )
    with pytest.raises(ValueError, match="labels differ"):
        score_value_decomposition(candidate, reference)


def test_strict_parser_accepts_complete_rows_and_rejects_duplicates():
    payload = {
        "posterior": {
            "target": "opponent_move",
            "probabilities": [
                {"state": "left", "probability": 0.25},
                {"state": "right", "probability": 0.75},
            ],
        },
        "action_values": [
            {
                "action_id": "stop",
                "immediate_value": 0.5,
                "continuation_value": 0.0,
                "total_value": 0.5,
            },
            {
                "action_id": "continue",
                "immediate_value": 0.0,
                "continuation_value": 1.0,
                "total_value": 1.0,
            },
        ],
        "chosen_action_id": "continue",
    }
    parsed = parse_value_decomposition(json.dumps(payload))
    assert parsed.chosen_action_id == "continue"
    assert parsed.maximum_additivity_residual == 0
    payload["action_values"].append(dict(payload["action_values"][0]))
    with pytest.raises(ValueError, match="unique"):
        parse_value_decomposition(json.dumps(payload))
