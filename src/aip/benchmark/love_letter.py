"""Exact value decomposition for the certified Love Letter research subgame."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import fsum
from typing import Hashable, Mapping

from aip.benchmark.value_decomposition import (
    ConditionedValueDecomposition,
    ValueDecomposition,
)
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


@dataclass(frozen=True, slots=True)
class LoveLetterConditionedDecompositionPanel:
    """Positive-reach values with chance prior and policy reach kept separate."""

    decompositions: Mapping[
        tuple[int, Hashable], ConditionedValueDecomposition
    ]
    zero_reach_information_sets: tuple[tuple[int, Hashable], ...]
    total_information_sets: int
    prior_method_id: str = "love_letter_chance_reach_combinatorial_prior_v1"

    def __post_init__(self) -> None:
        if (
            len(self.decompositions) + len(self.zero_reach_information_sets)
            != self.total_information_sets
        ):
            raise ValueError("Love Letter conditioned reach partition is incomplete")
        if set(self.decompositions).intersection(self.zero_reach_information_sets):
            raise ValueError("Love Letter conditioned reach partition overlaps")


class LoveLetterValueDecompositionOracle:
    """Decompose exact best-response Q-values at every subgame information set."""

    oracle_id = "love_letter_four_card_value_decomposition_v1"

    def __init__(self, game: LoveLetterCFRGame | None = None) -> None:
        self.game = game or LoveLetterCFRGame.late_round_subgame()
        self.evaluator = LoveLetterIndependentEvaluator(self.game)

    def decompose_all(
        self, profile: StrategyProfile
    ) -> LoveLetterDecompositionPanel:
        conditioned = self.decompose_conditioned_all(profile)
        return LoveLetterDecompositionPanel(
            decompositions={
                key: decomposition.values
                for key, decomposition in conditioned.decompositions.items()
            },
            zero_reach_information_sets=conditioned.zero_reach_information_sets,
            total_information_sets=conditioned.total_information_sets,
        )

    def decompose_conditioned_all(
        self, profile: StrategyProfile
    ) -> LoveLetterConditionedDecompositionPanel:
        """Compute chance-combinatorial priors before opponent-policy conditioning.

        Chance reach comes only from the adapter's chance distributions. In the
        full game those probabilities use remaining card multiplicities; in the
        four-card subgame they use the explicitly enumerated 24 deal/draw orders.
        Hero actions are counterfactually traversed with unit weight. Opponent
        action probabilities are accumulated separately as policy reach.
        """

        exact_values = self.evaluator.action_values(profile)
        result = {}
        zero_reach = []
        for hero in (0, 1):
            members = self._counterfactual_contributions(profile, hero)
            for information_set, contributions in members.items():
                key = (hero, information_set)
                conditioned_reach = fsum(
                    conditioned_mass
                    for _, conditioned_mass in contributions.values()
                )
                if conditioned_reach <= 0:
                    zero_reach.append(key)
                    continue
                chance_world_mass: dict[str, float] = defaultdict(float)
                conditioned_world_mass: dict[str, float] = defaultdict(float)
                for state, (chance_mass, conditioned_mass) in contributions.items():
                    world = repr(self.game.hidden_world(state, hero))
                    chance_world_mass[world] += chance_mass
                    conditioned_world_mass[world] += conditioned_mass
                chance_reach = fsum(chance_world_mass.values())
                if chance_reach <= 0:
                    raise ValueError("positive policy reach has zero chance reach")
                base_prior = {
                    world: mass / chance_reach
                    for world, mass in sorted(chance_world_mass.items())
                }
                posterior_weights = {
                    world: conditioned_world_mass[world] / conditioned_reach
                    for world in sorted(chance_world_mass)
                }
                policy_reach_weights = {
                    world: (
                        conditioned_world_mass[world] / chance_world_mass[world]
                    )
                    for world in sorted(chance_world_mass)
                }
                totals = {
                    love_letter_action_id(action): float(value)
                    for action, value in exact_values[key].items()
                }
                immediate = {}
                representative = next(iter(contributions))
                for action in self.game.legal_actions(representative):
                    action_id = love_letter_action_id(action)
                    terminal_value = 0.0
                    for state, (_, conditioned_mass) in contributions.items():
                        successor = self.game.next_state(state, action)
                        if self.game.is_terminal(successor):
                            utility = self.game.utility_player_zero(successor)
                            terminal_value += (conditioned_mass / conditioned_reach) * (
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
                result[key] = ConditionedValueDecomposition(
                    base_prior=base_prior,
                    policy_reach_weights=policy_reach_weights,
                    values=ValueDecomposition(
                        posterior_target="love_letter_hidden_world",
                        posterior=posterior_weights,
                        immediate_action_values=immediate,
                        continuation_action_values=continuation,
                        total_action_values=totals,
                        chosen_action_id=chosen,
                    ),
                )
        if set(result).union(zero_reach) != set(exact_values):
            raise ValueError("Love Letter reach audit did not cover every information set")
        return LoveLetterConditionedDecompositionPanel(
            decompositions=result,
            zero_reach_information_sets=tuple(sorted(zero_reach, key=repr)),
            total_information_sets=len(exact_values),
        )

    def _counterfactual_contributions(
        self, profile: StrategyProfile, hero: int
    ):
        members = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))

        def collect(state, chance_reach: float, opponent_reach: float) -> None:
            if self.game.is_terminal(state):
                return
            player = self.game.current_player(state)
            if player is None:
                for action, probability in self.game.chance_outcomes(state):
                    collect(
                        self.game.next_state(state, action),
                        chance_reach * probability,
                        opponent_reach,
                    )
                return
            information_set = self.game.information_set(state)
            actions = self.game.legal_actions(state)
            if player == hero:
                masses = members[information_set][state]
                masses[0] += chance_reach
                masses[1] += chance_reach * opponent_reach
                for action in actions:
                    collect(
                        self.game.next_state(state, action),
                        chance_reach,
                        opponent_reach,
                    )
                return
            distribution = profile[(player, information_set)]
            for action in actions:
                collect(
                    self.game.next_state(state, action),
                    chance_reach,
                    opponent_reach * float(distribution[action]),
                )

        collect(self.game.initial_state(), 1.0, 1.0)
        return {
            information_set: {
                state: (masses[0], masses[1])
                for state, masses in states.items()
            }
            for information_set, states in members.items()
        }
