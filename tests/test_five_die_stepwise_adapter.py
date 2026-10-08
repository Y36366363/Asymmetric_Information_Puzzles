import json
import math
from pathlib import Path

import pytest

from aip.puzzles.liars_dice import (
    FIVE_DIE_BIDS,
    FIVE_DIE_HISTOGRAMS,
    FiveDieStepwiseLiarGame,
    FiveDieStepwiseState,
    complete_five_die_policy,
    required_five_die_information_sets,
    train_five_die_external_sampling,
)


ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "configs/five_die_liar_stepwise_rules_v1.json"


def test_adapter_matches_frozen_rules_and_histogram_chance():
    rules = json.loads(RULES.read_text())
    game = FiveDieStepwiseLiarGame()
    assert game.RULES_ID == rules["rules_id"]
    assert len(FIVE_DIE_HISTOGRAMS) == math.comb(10, 5) == 252
    assert len(FIVE_DIE_BIDS) == 60
    outcomes = game.chance_outcomes(game.initial_state())
    assert len(outcomes) == 252
    assert sum(probability for _, probability in outcomes) == pytest.approx(1)
    assert len({histogram for histogram, _ in outcomes}) == 252
    assert all(sum(histogram) == 5 for histogram, _ in outcomes)


def test_adapter_deals_two_private_histograms_then_uses_stepwise_actions():
    game = FiveDieStepwiseLiarGame()
    first = (5, 0, 0, 0, 0, 0)
    second = (0, 0, 0, 0, 0, 5)
    state = game.next_state(game.initial_state(), first)
    assert game.current_player(state) is None
    assert len(game.chance_outcomes(state)) == 252
    state = game.next_state(state, second)
    assert game.current_player(state) == 0
    assert game.information_set(state) == (first, ())
    assert game.legal_actions(state) == tuple((1, face) for face in range(1, 7))
    state = game.next_state(state, (1, 6))
    assert game.current_player(state) == 1
    assert game.legal_actions(state) == ("challenge", (2, 1))


def test_wild_one_challenge_utility_is_zero_sum_and_rule_correct():
    game = FiveDieStepwiseLiarGame()
    hands = ((2, 0, 0, 0, 0, 3), (0, 0, 0, 0, 5, 0))
    true_claim = FiveDieStepwiseState(hands, ((5, 6),), challenger=1)
    false_claim = FiveDieStepwiseState(hands, ((6, 6),), challenger=1)
    assert game.utility_player_zero(true_claim) == 1
    assert game.utility_player_zero(false_claim) == -1


def test_required_information_sets_and_uniform_completion_are_exact():
    required = required_five_die_information_sets()
    assert len(required) == 252 * 346 == 87_192
    completed = complete_five_die_policy({})
    assert set(completed) == set(required)
    assert all(sum(distribution.values()) == pytest.approx(1) for distribution in completed.values())


def test_external_sampling_is_seeded_and_candidate_completion_is_explicit():
    first = train_five_die_external_sampling(25, seed=20261008)
    second = train_five_die_external_sampling(25, seed=20261008)
    assert first.policy == second.policy
    assert first.algorithm.seed == 20261008
    assert first.algorithm.algorithm_id == "external_sampling_mccfr"
    assert 0 < len(first.policy) < len(required_five_die_information_sets())
    completed = complete_five_die_policy(first.policy)
    assert len(completed) == 87_192
