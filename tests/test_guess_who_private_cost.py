import json
from pathlib import Path

import pytest

from aip.puzzles.guess_who import (
    DEFAULT_QUESTIONS,
    DEFAULT_ROSTER,
    PrivateCostStrategicGuessWhoGame,
)


ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "configs/strategic_guess_who_private_cost_rules_v2.json"
PREREGISTRATION = (
    ROOT / "configs/guess_who_private_cost_signaling_preregistration_2026-10-04.json"
)


def load_game():
    preregistration = json.loads(PREREGISTRATION.read_text())
    roster = tuple(
        DEFAULT_ROSTER[index]
        for index in preregistration["target"]["roster_indices"]
    )
    question_by_id = {question.id: question for question in DEFAULT_QUESTIONS}
    questions = tuple(
        question_by_id[question_id]
        for question_id in preregistration["target"]["question_ids"]
    )
    costs = tuple(
        tuple(row) for row in preregistration["private_question_costs"]
        ["matrix_by_roster_and_question_order"]
    )
    return PrivateCostStrategicGuessWhoGame(roster, questions, costs)


def test_v2_rules_and_preregistration_are_frozen_before_results():
    rules = json.loads(RULES.read_text())
    preregistration = json.loads(PREREGISTRATION.read_text())
    assert rules == PrivateCostStrategicGuessWhoGame.rules_contract()
    assert preregistration["frozen_before_outcome_evaluation"] is True
    assert preregistration["rules_id"] == rules["rules_id"]
    assert preregistration["primary_endpoint"]["name"] == (
        "maximum_within_seat_root_policy_l1_by_private_secret"
    )
    assert preregistration["solver"]["maximum_exploitability"] == 1e-10
    assert preregistration["solver"]["cfr_iterations"] == 5_000


def test_committed_question_cost_is_charged_when_opponent_guesses():
    game = load_game()
    state = game.next_state(game.initial_state(), 0)  # Player 0 protects Ada.
    state = game.next_state(state, 1)  # Player 1 protects Bruno.
    state = game.next_state(state, ("ask", 1))  # Ada's cost is 0.02.
    state = game.next_state(state, ("guess", 0))  # Player 1 guesses Ada.
    assert game.utility_player_zero(state) == pytest.approx(-1.02)
    assert state.question_costs_paid == pytest.approx((0.02, 0.0))


def test_opponent_cost_enters_player_zero_utility_with_positive_sign():
    game = load_game()
    state = game.next_state(game.initial_state(), 0)
    state = game.next_state(state, 1)
    state = game.next_state(state, ("guess", 2))  # Wrong unilateral guess.
    state = game.next_state(state, ("ask", 3))  # Bruno pays 0.01.
    assert game.utility_player_zero(state) == pytest.approx(-0.99)
    assert state.question_costs_paid == pytest.approx((0.0, 0.01))


@pytest.mark.parametrize(
    "costs",
    (
        ((0.0,),),
        ((0.0, 0.0, 0.0, 0.0),) * 2,
        ((0.0, 0.0, 0.0, -0.01),) * 3,
        ((0.0, 0.0, 0.0, float("inf")),) * 3,
    ),
)
def test_invalid_private_cost_matrices_are_rejected(costs):
    preregistration = json.loads(PREREGISTRATION.read_text())
    roster = tuple(DEFAULT_ROSTER[index] for index in (0, 1, 6))
    by_id = {question.id: question for question in DEFAULT_QUESTIONS}
    questions = tuple(
        by_id[question_id]
        for question_id in preregistration["target"]["question_ids"]
    )
    with pytest.raises(ValueError):
        PrivateCostStrategicGuessWhoGame(roster, questions, costs)
