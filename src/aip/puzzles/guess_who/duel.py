"""Exact normal-form audit of a *restricted* simultaneous Guess Who duel.

Both players privately choose a character and commit to a question priority order.
They ask truthful yes/no questions simultaneously; once one candidate remains, a
final guess costs a round. This is not the adaptive, alternating full game.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import isclose, isfinite
from typing import Hashable

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


@dataclass(frozen=True, slots=True)
class AdaptiveDuelState:
    """State for simultaneous-round play represented as hidden sequential moves."""

    stage: str = "player_0_secret"
    secrets: tuple[int | None, int | None] = (None, None)
    candidates: tuple[int, int] = (0, 0)
    transcript: tuple[tuple[int, bool, int, bool], ...] = ()
    pending_player_0_question: int | None = None
    utility: float | None = None


class AdaptiveGuessWhoGame:
    """Tiny adaptive duel with simultaneous secret and question choices.

    Sequential nodes encode simultaneous choices by hiding player 0's pending
    choice from player 1. Questions and truthful answers become public only
    after both players commit for the round.
    """

    def __init__(
        self,
        roster: tuple[Character, ...],
        questions: tuple[Question, ...],
    ) -> None:
        self.detective = GuessWhoSolver(roster, questions)
        self.roster = roster
        self.questions = questions
        self._full_mask = self.detective.full_candidate_mask

    def initial_state(self) -> AdaptiveDuelState:
        return AdaptiveDuelState()

    def is_terminal(self, state: AdaptiveDuelState) -> bool:
        return state.stage == "terminal"

    def utility_player_zero(self, state: AdaptiveDuelState) -> float:
        if not self.is_terminal(state) or state.utility is None:
            raise ValueError("utility is defined only at terminal adaptive duel states")
        return state.utility

    def current_player(self, state: AdaptiveDuelState) -> int | None:
        return {
            "player_0_secret": 0,
            "player_1_secret": 1,
            "player_0_question": 0,
            "player_1_question": 1,
            "terminal": None,
        }[state.stage]

    def chance_outcomes(
        self, state: AdaptiveDuelState
    ) -> tuple[tuple[Hashable, float], ...]:
        return ()

    def _valid_questions(self, candidates: int) -> tuple[int, ...]:
        valid = []
        for index in range(len(self.questions)):
            yes, no = self.detective._split(candidates, index)
            if yes and no:
                valid.append(index)
        return tuple(valid)

    def legal_actions(self, state: AdaptiveDuelState) -> tuple[Hashable, ...]:
        if state.stage in {"player_0_secret", "player_1_secret"}:
            return tuple(range(len(self.roster)))
        if state.stage == "player_0_question":
            return self._valid_questions(state.candidates[0])
        if state.stage == "player_1_question":
            return self._valid_questions(state.candidates[1])
        return ()

    def information_set(self, state: AdaptiveDuelState) -> Hashable:
        if state.stage == "player_0_secret":
            return "select_secret"
        if state.stage == "player_1_secret":
            # Player 0's earlier secret selection is deliberately hidden.
            return "select_secret"
        player = self.current_player(state)
        if player not in (0, 1):
            raise ValueError("terminal adaptive duel state has no information set")
        own_secret = state.secrets[player]
        # At player 1's node the pending player-0 question is deliberately
        # omitted, which implements simultaneous question selection.
        return "ask", own_secret, state.transcript

    def next_state(
        self, state: AdaptiveDuelState, action: Hashable
    ) -> AdaptiveDuelState:
        if action not in self.legal_actions(state):
            raise ValueError(f"illegal adaptive Guess Who action: {action!r}")
        choice = int(action)
        if state.stage == "player_0_secret":
            return AdaptiveDuelState(
                stage="player_1_secret", secrets=(choice, None)
            )
        if state.stage == "player_1_secret":
            return AdaptiveDuelState(
                stage="player_0_question",
                secrets=(state.secrets[0], choice),
                candidates=(self._full_mask, self._full_mask),
            )
        if state.stage == "player_0_question":
            return AdaptiveDuelState(
                stage="player_1_question",
                secrets=state.secrets,
                candidates=state.candidates,
                transcript=state.transcript,
                pending_player_0_question=choice,
            )
        if state.stage != "player_1_question":
            raise ValueError("terminal adaptive duel state has no transition")
        question_zero = state.pending_player_0_question
        if question_zero is None or state.secrets[0] is None or state.secrets[1] is None:
            raise ValueError("adaptive duel round is missing committed private state")
        answer_zero = bool(self.detective._yes_masks[question_zero] & (1 << state.secrets[1]))
        answer_one = bool(self.detective._yes_masks[choice] & (1 << state.secrets[0]))
        split_zero = self.detective._split(state.candidates[0], question_zero)
        split_one = self.detective._split(state.candidates[1], choice)
        candidates = (
            split_zero[0] if answer_zero else split_zero[1],
            split_one[0] if answer_one else split_one[1],
        )
        transcript = state.transcript + ((question_zero, answer_zero, choice, answer_one),)
        solved_zero = candidates[0].bit_count() == 1
        solved_one = candidates[1].bit_count() == 1
        if solved_zero or solved_one:
            utility = float(solved_zero and not solved_one) - float(solved_one and not solved_zero)
            return AdaptiveDuelState(
                stage="terminal", secrets=state.secrets, candidates=candidates,
                transcript=transcript, utility=utility,
            )
        return AdaptiveDuelState(
            stage="player_0_question", secrets=state.secrets,
            candidates=candidates, transcript=transcript,
        )


@dataclass(frozen=True, slots=True)
class StrategicGuessState:
    """Adaptive duel state with explicit, fallible identity guesses."""

    stage: str = "player_0_secret"
    secrets: tuple[int | None, int | None] = (None, None)
    candidates: tuple[int, int] = (0, 0)
    transcript: tuple[tuple[int, bool, int, bool], ...] = ()
    pending_player_0_action: tuple[str, int] | None = None
    question_costs_paid: tuple[float, float] = (0.0, 0.0)
    utility: float | None = None


class StrategicGuessWhoGame:
    """Tiny duel where public question choices can inform later guesses.

    A guess is always available for every publicly feasible opponent identity.
    A correct unilateral guess wins and an incorrect unilateral guess loses.
    If both players guess in the same round, equal correctness is a draw; only
    one correct guess wins. This convention is explicit because changing the
    wrong-guess penalty changes the equilibrium.
    """

    RULES_ID = "strategic_guess_who_simultaneous_v1"

    @classmethod
    def rules_contract(cls) -> dict[str, object]:
        """Return the frozen semantic contract used by certified artifacts."""

        return {
            "rules_id": cls.RULES_ID,
            "players": 2,
            "utility": "zero_sum_win_plus_1_draw_0_loss_minus_1",
            "secret_selection": "simultaneous_private_encoded_by_hidden_sequential_nodes",
            "round_actions": ["ask_truthful_binary_question", "guess_publicly_feasible_identity"],
            "round_timing": "simultaneous_encoded_by_hidden_sequential_nodes",
            "question_and_answer_reveal": "after_both_round_actions_commit",
            "correct_unilateral_guess": "immediate_win",
            "incorrect_unilateral_guess": "immediate_loss",
            "both_guess_one_correct": "correct_guesser_wins",
            "both_guess_equal_correctness": "draw",
            "automatic_singleton_terminal": False,
            "question_cost": 0.0,
            "repeated_uninformative_questions": "illegal",
        }

    def __init__(
        self,
        roster: tuple[Character, ...],
        questions: tuple[Question, ...],
    ) -> None:
        self.detective = GuessWhoSolver(roster, questions)
        self.roster = roster
        self.questions = questions
        self._full_mask = self.detective.full_candidate_mask

    def initial_state(self) -> StrategicGuessState:
        return StrategicGuessState()

    def is_terminal(self, state: StrategicGuessState) -> bool:
        return state.stage == "terminal"

    def utility_player_zero(self, state: StrategicGuessState) -> float:
        if not self.is_terminal(state) or state.utility is None:
            raise ValueError("utility is defined only at terminal strategic Guess Who states")
        return state.utility

    def current_player(self, state: StrategicGuessState) -> int | None:
        return {
            "player_0_secret": 0,
            "player_1_secret": 1,
            "player_0_action": 0,
            "player_1_action": 1,
            "terminal": None,
        }[state.stage]

    def chance_outcomes(
        self, state: StrategicGuessState
    ) -> tuple[tuple[Hashable, float], ...]:
        return ()

    def _round_actions(self, candidates: int) -> tuple[tuple[str, int], ...]:
        guesses = tuple(
            ("guess", index)
            for index in range(len(self.roster))
            if candidates & (1 << index)
        )
        questions = []
        for index in range(len(self.questions)):
            yes, no = self.detective._split(candidates, index)
            if yes and no:
                questions.append(("ask", index))
        return guesses + tuple(questions)

    def legal_actions(self, state: StrategicGuessState) -> tuple[Hashable, ...]:
        if state.stage in {"player_0_secret", "player_1_secret"}:
            return tuple(range(len(self.roster)))
        if state.stage == "player_0_action":
            return self._round_actions(state.candidates[0])
        if state.stage == "player_1_action":
            return self._round_actions(state.candidates[1])
        return ()

    def information_set(self, state: StrategicGuessState) -> Hashable:
        if state.stage in {"player_0_secret", "player_1_secret"}:
            return "select_secret"
        player = self.current_player(state)
        if player not in (0, 1):
            raise ValueError("terminal strategic Guess Who state has no information set")
        return "act", state.secrets[player], state.transcript

    @staticmethod
    def _guess_utility(
        action_zero: tuple[str, int],
        action_one: tuple[str, int],
        secrets: tuple[int | None, int | None],
    ) -> float | None:
        zero_guesses = action_zero[0] == "guess"
        one_guesses = action_one[0] == "guess"
        if not zero_guesses and not one_guesses:
            return None
        if secrets[0] is None or secrets[1] is None:
            raise ValueError("guess resolution requires both private identities")
        correct_zero = zero_guesses and action_zero[1] == secrets[1]
        correct_one = one_guesses and action_one[1] == secrets[0]
        if zero_guesses and one_guesses:
            return float(correct_zero) - float(correct_one)
        if zero_guesses:
            return 1.0 if correct_zero else -1.0
        return -1.0 if correct_one else 1.0

    def next_state(
        self, state: StrategicGuessState, action: Hashable
    ) -> StrategicGuessState:
        if action not in self.legal_actions(state):
            raise ValueError(f"illegal strategic Guess Who action: {action!r}")
        if state.stage == "player_0_secret":
            return StrategicGuessState(
                stage="player_1_secret", secrets=(int(action), None),
                question_costs_paid=state.question_costs_paid,
            )
        if state.stage == "player_1_secret":
            return StrategicGuessState(
                stage="player_0_action",
                secrets=(state.secrets[0], int(action)),
                candidates=(self._full_mask, self._full_mask),
                question_costs_paid=state.question_costs_paid,
            )
        chosen = action
        if not isinstance(chosen, tuple) or len(chosen) != 2:
            raise ValueError("round action must be an ask or guess tuple")
        round_action = (str(chosen[0]), int(chosen[1]))
        if state.stage == "player_0_action":
            return StrategicGuessState(
                stage="player_1_action",
                secrets=state.secrets,
                candidates=state.candidates,
                transcript=state.transcript,
                pending_player_0_action=round_action,
                question_costs_paid=state.question_costs_paid,
            )
        if state.stage != "player_1_action" or state.pending_player_0_action is None:
            raise ValueError("strategic Guess Who round is missing player 0's action")
        action_zero = state.pending_player_0_action
        action_one = round_action
        utility = self._guess_utility(action_zero, action_one, state.secrets)
        if utility is not None:
            return StrategicGuessState(
                stage="terminal", secrets=state.secrets,
                candidates=state.candidates, transcript=state.transcript,
                question_costs_paid=state.question_costs_paid,
                utility=utility,
            )
        question_zero, question_one = action_zero[1], action_one[1]
        if state.secrets[0] is None or state.secrets[1] is None:
            raise ValueError("question resolution requires both private identities")
        answer_zero = bool(
            self.detective._yes_masks[question_zero] & (1 << state.secrets[1])
        )
        answer_one = bool(
            self.detective._yes_masks[question_one] & (1 << state.secrets[0])
        )
        split_zero = self.detective._split(state.candidates[0], question_zero)
        split_one = self.detective._split(state.candidates[1], question_one)
        candidates = (
            split_zero[0] if answer_zero else split_zero[1],
            split_one[0] if answer_one else split_one[1],
        )
        return StrategicGuessState(
            stage="player_0_action",
            secrets=state.secrets,
            candidates=candidates,
            question_costs_paid=state.question_costs_paid,
            transcript=state.transcript + (
                (question_zero, answer_zero, question_one, answer_one),
            ),
        )


class PrivateCostStrategicGuessWhoGame(StrategicGuessWhoGame):
    """Versioned zero-sum variant with private identity-dependent ask costs."""

    RULES_ID = "strategic_guess_who_private_question_cost_v2"

    @classmethod
    def rules_contract(cls) -> dict[str, object]:
        return {
            "rules_id": cls.RULES_ID,
            "base_rules_id": StrategicGuessWhoGame.RULES_ID,
            "question_cost_visibility": "own_private_identity_schedule_known_to_owner",
            "question_cost_timing": "charged_for_every_committed_ask_even_if_same_round_guess_ends_game",
            "question_cost_range": "finite_nonnegative",
            "utility_player_0": "terminal_outcome_minus_player_0_cost_plus_player_1_cost",
            "zero_sum": True,
            "cost_schedule_source": "experiment_configuration",
        }

    def __init__(
        self,
        roster: tuple[Character, ...],
        questions: tuple[Question, ...],
        question_costs: tuple[tuple[float, ...], ...],
    ) -> None:
        super().__init__(roster, questions)
        if (
            len(question_costs) != len(roster)
            or any(len(row) != len(questions) for row in question_costs)
            or any(
                not isfinite(value) or value < 0
                for row in question_costs
                for value in row
            )
        ):
            raise ValueError(
                "private question costs must be a finite nonnegative roster-by-question matrix"
            )
        self.question_costs = tuple(
            tuple(float(value) for value in row) for row in question_costs
        )

    def next_state(
        self, state: StrategicGuessState, action: Hashable
    ) -> StrategicGuessState:
        child = super().next_state(state, action)
        if state.stage != "player_1_action":
            return child
        action_zero = state.pending_player_0_action
        if action_zero is None or state.secrets[0] is None or state.secrets[1] is None:
            raise ValueError("private-cost round requires both secrets and committed actions")
        if not isinstance(action, tuple) or len(action) != 2:
            raise ValueError("private-cost round action must be an ask or guess tuple")
        action_one = (str(action[0]), int(action[1]))
        incremental_zero = (
            self.question_costs[state.secrets[0]][action_zero[1]]
            if action_zero[0] == "ask" else 0.0
        )
        incremental_one = (
            self.question_costs[state.secrets[1]][action_one[1]]
            if action_one[0] == "ask" else 0.0
        )
        totals = (
            state.question_costs_paid[0] + incremental_zero,
            state.question_costs_paid[1] + incremental_one,
        )
        utility = child.utility
        if utility is not None:
            utility = utility - totals[0] + totals[1]
        return replace(child, question_costs_paid=totals, utility=utility)
