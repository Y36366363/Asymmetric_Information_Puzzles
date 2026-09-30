"""Exact normal-form audit of a *restricted* simultaneous Guess Who duel.

Both players privately choose a character and commit to a question priority order.
They ask truthful yes/no questions simultaneously; once one candidate remains, a
final guess costs a round. This is not the adaptive, alternating full game.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isclose

from aip.core.linear_program import maximize_linear_program

from .models import Character, Question
from .solver import GuessWhoSolver


@dataclass(frozen=True, slots=True)
class DuelAction:
    secret: str
    question_order: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DuelEquilibrium:
    actions: tuple[DuelAction, ...]
    player_0_strategy: tuple[float, ...]
    player_1_strategy: tuple[float, ...]
    value: float
    player_0_deviation_gain: float
    player_1_deviation_gain: float
    maximum_unilateral_deviation_gain: float
    nash_conv: float
    exploitability: float


class GuessWhoDuel:
    """Finite commitment game; exact within its supplied action catalogue."""

    def __init__(
        self,
        roster: tuple[Character, ...],
        questions: tuple[Question, ...],
        question_orders: tuple[tuple[str, ...], ...],
    ) -> None:
        self.detective = GuessWhoSolver(roster, questions)
        question_ids = {question.id for question in questions}
        if not question_orders or len(set(question_orders)) != len(question_orders):
            raise ValueError("question orders must be nonempty and unique")
        if any(len(order) != len(questions) or set(order) != question_ids for order in question_orders):
            raise ValueError("each question order must be a permutation of the question bank")
        self.actions = tuple(
            DuelAction(character.name, order)
            for character in roster
            for order in question_orders
        )
        self._question_index = {question.id: index for index, question in enumerate(questions)}

    def discovery_turns(self, secret: str, order: tuple[str, ...]) -> int:
        if secret not in self.detective._name_to_index:
            raise ValueError(f"unknown secret character: {secret}")
        if len(order) != len(self.detective.questions) or set(order) != set(self._question_index):
            raise ValueError("question order must cover the question bank")
        secret_bit = 1 << self.detective._name_to_index[secret]
        candidates = self.detective.full_candidate_mask
        turns = 1  # Final identity guess.
        for question_id in order:
            if candidates.bit_count() == 1:
                return turns
            question_index = self._question_index[question_id]
            yes, no = self.detective._split(candidates, question_index)
            if not yes or not no:
                continue  # A precommitted priority list skips known-uninformative questions.
            candidates = yes if yes & secret_bit else no
            turns += 1
        if candidates.bit_count() != 1:
            raise AssertionError("the validated question bank did not identify the secret")
        return turns

    def payoff_matrix(self) -> tuple[tuple[float, ...], ...]:
        turns = {
            (secret.name, order): self.discovery_turns(secret.name, order)
            for secret in self.detective.roster
            for order in {action.question_order for action in self.actions}
        }
        return tuple(
            tuple(
                float(
                    (turns[(opponent.secret, own.question_order)]
                     < turns[(own.secret, opponent.question_order)])
                    - (turns[(opponent.secret, own.question_order)]
                       > turns[(own.secret, opponent.question_order)])
                )
                for opponent in self.actions
            )
            for own in self.actions
        )

    @staticmethod
    def _maximin(matrix: tuple[tuple[float, ...], ...]) -> tuple[float, ...]:
        rows, columns = len(matrix), len(matrix[0])
        shift = 1.0 - min(min(row) for row in matrix)
        solution = maximize_linear_program(
            (0.0,) * rows + (1.0,),
            tuple(
                tuple(-(matrix[row][column] + shift) for row in range(rows)) + (1.0,)
                for column in range(columns)
            ) + ((1.0,) * rows + (0.0,), (-1.0,) * rows + (0.0,)),
            (0.0,) * columns + (1.0, -1.0),
        )
        probabilities = tuple(max(0.0, value) for value in solution.variables[:rows])
        total = sum(probabilities)
        if not isclose(total, 1.0, abs_tol=1e-7):
            raise ValueError("LP returned a non-normalized strategy")
        return tuple(value / total for value in probabilities)

    def solve(self) -> DuelEquilibrium:
        matrix = self.payoff_matrix()
        row_strategy = self._maximin(matrix)
        column_strategy = self._maximin(
            tuple(tuple(-matrix[row][column] for row in range(len(matrix)))
                  for column in range(len(matrix[0])))
        )
        value = sum(
            row_strategy[row] * matrix[row][column] * column_strategy[column]
            for row in range(len(matrix)) for column in range(len(matrix[0]))
        )
        # Independent pure best-response enumeration, not training regrets.
        row_best = max(
            sum(matrix[row][column] * column_strategy[column] for column in range(len(matrix)))
            for row in range(len(matrix))
        )
        column_best = min(
            sum(row_strategy[row] * matrix[row][column] for row in range(len(matrix)))
            for column in range(len(matrix))
        )
        gain_0 = max(0.0, row_best - value)
        gain_1 = max(0.0, value - column_best)
        nash_conv = gain_0 + gain_1
        return DuelEquilibrium(
            self.actions, row_strategy, column_strategy, value,
            gain_0, gain_1, max(gain_0, gain_1), nash_conv, nash_conv / 2,
        )
