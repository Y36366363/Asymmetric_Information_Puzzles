"""Exact value decomposition for the certified Love Letter research subgame."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import fsum
from typing import Hashable, Mapping

from aip.benchmark.value_decomposition import ValueDecomposition
from aip.core.evaluation import StrategyProfile
from aip.puzzles.love_letter import LoveLetterCFRGame, LoveLetterIndependentEvaluator
from aip.puzzles.love_letter.solver import Play


def love_letter_action_id(action: Play) -> str:
    return "play:" + ":".join((
        str(action.card),
        action.target or "none",
        str(action.guess) if action.guess is not None else "none",
    ))


@dataclass(frozen=True, slots=True)
class LoveLetterDecompositionPanel:
    decompositions: Mapping[tuple[int, Hashable], ValueDecomposition]
    zero_reach_information_sets: tuple[tuple[int, Hashable], ...]
    total_information_sets: int

    def __post_init__(self) -> None:
        if (
            len(self.decompositions) + len(self.zero_reach_information_sets)
            != self.total_information_sets
        ):
            raise ValueError("Love Letter reach partition is incomplete")
        if set(self.decompositions).intersection(self.zero_reach_information_sets):
            raise ValueError("Love Letter reach partition overlaps")


class LoveLetterValueDecompositionOracle:
    """Decompose exact best-response Q-values at every subgame information set."""

    oracle_id = "love_letter_four_card_value_decomposition_v1"

    def __init__(self, game: LoveLetterCFRGame | None = None) -> None:
        self.game = game or LoveLetterCFRGame.late_round_subgame()
        self.evaluator = LoveLetterIndependentEvaluator(self.game)

    def decompose_all(
        self, profile: StrategyProfile
    ) -> LoveLetterDecompositionPanel:
        exact_values = self.evaluator.action_values(profile)
        result = {}
        zero_reach = []
        for hero in (0, 1):
            members = self._counterfactual_members(profile, hero)
            for information_set, states in members.items():
                key = (hero, information_set)
                reach = fsum(states.values())
                if reach <= 0:
                    zero_reach.append(key)
                    continue
                posterior_weights: dict[str, float] = defaultdict(float)
                for state, weight in states.items():
                    posterior_weights[repr(self.game.hidden_world(state, hero))] += (
                        weight / reach
                    )
                totals = {
                    love_letter_action_id(action): float(value)
                    for action, value in exact_values[key].items()
                }
                immediate = {}
                for action in self.game.legal_actions(next(iter(states))):
                    action_id = love_letter_action_id(action)
                    terminal_value = 0.0
                    for state, weight in states.items():
                        successor = self.game.next_state(state, action)
                        if self.game.is_terminal(successor):
                            utility = self.game.utility_player_zero(successor)
                            terminal_value += (weight / reach) * (
                                utility if hero == 0 else -utility
                            )
                    immediate[action_id] = terminal_value
                continuation = {
                    action: totals[action] - immediate[action]
                    for action in totals
                }
                optimum = max(totals.values())
                chosen = sorted(
                    action for action, value in totals.items()
                    if abs(value - optimum) <= 1e-9
                )[0]
                result[key] = ValueDecomposition(
                    posterior_target="love_letter_hidden_world",
                    posterior=dict(sorted(posterior_weights.items())),
                    immediate_action_values=immediate,
                    continuation_action_values=continuation,
                    total_action_values=totals,
                    chosen_action_id=chosen,
                )
        if set(result).union(zero_reach) != set(exact_values):
            raise ValueError("Love Letter reach audit did not cover every information set")
        return LoveLetterDecompositionPanel(
            decompositions=result,
            zero_reach_information_sets=tuple(sorted(zero_reach, key=repr)),
            total_information_sets=len(exact_values),
        )

    def _counterfactual_members(self, profile: StrategyProfile, hero: int):
        members = defaultdict(lambda: defaultdict(float))

        def collect(state, reach: float) -> None:
            if self.game.is_terminal(state):
                return
            player = self.game.current_player(state)
            if player is None:
                for action, probability in self.game.chance_outcomes(state):
                    collect(self.game.next_state(state, action), reach * probability)
                return
            information_set = self.game.information_set(state)
            actions = self.game.legal_actions(state)
            if player == hero:
                members[information_set][state] += reach
                for action in actions:
                    collect(self.game.next_state(state, action), reach)
                return
            distribution = profile[(player, information_set)]
            for action in actions:
                collect(
                    self.game.next_state(state, action),
                    reach * float(distribution[action]),
                )

        collect(self.game.initial_state(), 1.0)
        return members
