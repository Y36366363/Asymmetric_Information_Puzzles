"""Shared-CFR adapter for the frozen single-round E-Card timing game."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Hashable

from aip.core import (
    CFRCertificationGate,
    CFRGameProperties,
    CFRGateReport,
    CFRResult,
    CFRThresholds,
    CFRTrainer,
)
from aip.puzzles.e_card.solver import (
    DUELS,
    e_card_expected_value,
    e_card_exploitability,
    e_card_evaluation,
)


@dataclass(frozen=True, slots=True)
class ECardTimingState:
    emperor_timing: int | None = None
    slave_timing: int | None = None


class ECardTimingCFRGame:
    """Sequential representation of simultaneous hidden timing commitments."""

    def initial_state(self) -> ECardTimingState:
        return ECardTimingState()

    def is_terminal(self, state: ECardTimingState) -> bool:
        return state.slave_timing is not None

    def utility_player_zero(self, state: ECardTimingState) -> float:
        if state.emperor_timing is None or state.slave_timing is None:
            raise ValueError("E-Card utility is defined only at terminal states")
        return -5.0 if state.emperor_timing == state.slave_timing else 1.0

    def current_player(self, state: ECardTimingState) -> int | None:
        if state.emperor_timing is None:
            return 0
        if state.slave_timing is None:
            return 1
        return None

    def chance_outcomes(
        self, state: ECardTimingState
    ) -> tuple[tuple[Hashable, float], ...]:
        return ()

    def legal_actions(self, state: ECardTimingState) -> tuple[Hashable, ...]:
        return DUELS if not self.is_terminal(state) else ()

    def information_set(self, state: ECardTimingState) -> Hashable:
        player = self.current_player(state)
        if player is None:
            raise ValueError("terminal E-Card states have no information set")
        # Player one must not observe player zero's hidden timing commitment.
        return ("emperor" if player == 0 else "slave", "choose_special_duel")

    def next_state(
        self, state: ECardTimingState, action: Hashable
    ) -> ECardTimingState:
        if action not in DUELS or action not in self.legal_actions(state):
            raise ValueError(f"illegal E-Card timing: {action!r}")
        if state.emperor_timing is None:
            return ECardTimingState(emperor_timing=int(action))
        return ECardTimingState(state.emperor_timing, int(action))


def train_e_card_cfr(iterations: int = 10_000) -> CFRResult:
    return CFRTrainer(ECardTimingCFRGame()).train(iterations)


def _strategies(result: CFRResult) -> tuple[dict[int, float], dict[int, float]]:
    return (
        {
            int(action): float(probability)
            for action, probability in result.policy[
                (0, ("emperor", "choose_special_duel"))
            ].items()
        },
        {
            int(action): float(probability)
            for action, probability in result.policy[
                (1, ("slave", "choose_special_duel"))
            ].items()
        },
    )


def e_card_cfr_exploitability(result: CFRResult) -> float:
    return e_card_exploitability(*_strategies(result))


def e_card_cfr_value(result: CFRResult) -> float:
    return e_card_expected_value(*_strategies(result))


def certify_e_card_cfr(
    result: CFRResult, thresholds: CFRThresholds | None = None
) -> CFRGateReport:
    required = frozenset(
        {
            (0, ("emperor", "choose_special_duel")),
            (1, ("slave", "choose_special_duel")),
        }
    )
    gate = CFRCertificationGate(
        thresholds
        or CFRThresholds(
            min_iterations=10_000,
            min_information_sets=2,
            min_visits_per_information_set=10_000,
            # This adapter is a cross-check for the exact 5x5 solution. Vanilla
            # CFR converges slowly enough that tighter gates would add runtime
            # without improving the exact policy used as ground truth.
            max_average_positive_regret=0.06,
            max_exploitability=0.006,
        )
    )
    return gate.evaluate(
        result,
        evaluation=e_card_evaluation(*_strategies(result)),
        required_information_sets=required,
        exact_information_sets=True,
        game_properties=CFRGameProperties(
            players=2,
            finite=True,
            zero_sum_or_constant_sum=True,
            perfect_recall=True,
        ),
    )
