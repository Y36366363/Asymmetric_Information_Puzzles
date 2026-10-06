import math

import pytest

from aip.benchmark.love_letter import build_private_hand_full_support_policy
from aip.puzzles.love_letter import (
    LoveLetterCFRGame,
    complete_information_set_actions,
)


def test_private_hand_policy_is_deterministic_normalized_and_full_support():
    game = LoveLetterCFRGame.late_round_subgame()
    actions = complete_information_set_actions(game)
    first = build_private_hand_full_support_policy(game)
    second = build_private_hand_full_support_policy(game)
    assert first == second
    assert set(first) == set(actions)
    assert len(first) == 60
    for key, distribution in first.items():
        assert set(distribution) == set(actions[key])
        assert sum(distribution.values()) == pytest.approx(1)
        assert all(probability > 0 for probability in distribution.values())


def test_private_hand_policy_uses_the_frozen_weight_formula():
    game = LoveLetterCFRGame.late_round_subgame()
    profile = build_private_hand_full_support_policy(game)
    key = next(
        key
        for key, distribution in profile.items()
        if len(key[1][2]) == 2
        and {action.card for action in distribution} == {1, 4}
    )
    distribution = profile[key]
    play_four = next(action for action in distribution if action.card == 4)
    play_one_guess_two = next(
        action
        for action in distribution
        if action.card == 1 and action.guess == 2
    )
    raw_four = 1 + 0.75 * 1 + 0.05 * 4
    raw_guard = 1 + 0.75 * 4 + 0.05 * 1 + 0.02 * 2
    assert distribution[play_one_guess_two] / distribution[play_four] == pytest.approx(
        raw_guard / raw_four
    )


@pytest.mark.parametrize(
    "kwargs",
    (
        {"floor": 0.0},
        {"floor": -1.0},
        {"kept_card_coefficient": -0.1},
        {"played_card_coefficient": math.inf},
        {"guard_guess_coefficient": math.nan},
    ),
)
def test_private_hand_policy_rejects_invalid_parameters(kwargs):
    with pytest.raises(ValueError):
        build_private_hand_full_support_policy(
            LoveLetterCFRGame.late_round_subgame(), **kwargs
        )
