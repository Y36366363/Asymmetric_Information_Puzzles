"""Exact matrix/sequence-form solution for one round of E-Card.

Each player has four Citizens and one role card. The Emperor role card beats a
Citizen, a Citizen beats the Slave, and the Slave beats the Emperor. A round
ends at the first non-draw. Therefore a pure strategy is simply the duel on
which a player uses the role card. For this one-decision-per-player game, the
sequence-form realization plans are identical to the mixed strategies of the
5x5 normal-form matrix.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Mapping

from aip.core.cfr import EquilibriumEvaluation
from aip.core.equilibrium import EquilibriumGameStructure, StoppingTimeStructure
from aip.puzzles.goofspiel.solver import MatrixSolution, solve_zero_sum_matrix


DUELS = (1, 2, 3, 4, 5)


def e_card_equilibrium_structure() -> EquilibriumGameStructure:
    return EquilibriumGameStructure(
        players=2,
        finite=True,
        zero_sum_or_constant_sum=True,
        perfect_recall=True,
        chance_after_initial_state=False,
        stopping_time=StoppingTimeStructure(
            horizon=len(DUELS),
            fixed_private_information_at_start=True,
            no_new_private_information=True,
            forced_continuation_before_stop=True,
            payoff_depends_only_on_stopping_times=True,
        ),
        exact_tree_is_small=True,
    )


@dataclass(frozen=True, slots=True)
class ECardTimingSolution:
    """Exact equilibrium, with utility measured for the Emperor seat."""

    emperor_value: Fraction
    emperor_strategy: tuple[Fraction, ...]
    slave_strategy: tuple[Fraction, ...]


def e_card_payoff_matrix() -> tuple[tuple[Fraction, ...], ...]:
    """Return Emperor score difference for every pair of special-card timings."""

    return tuple(
        tuple(Fraction(-5 if emperor == slave else 1) for slave in DUELS)
        for emperor in DUELS
    )


def solve_e_card_timing_game() -> ECardTimingSolution:
    exact: MatrixSolution = solve_zero_sum_matrix(e_card_payoff_matrix())
    return ECardTimingSolution(
        emperor_value=exact.value,
        emperor_strategy=exact.row_strategy,
        slave_strategy=exact.column_strategy,
    )


def e_card_exploitability(
    emperor_strategy: Mapping[int, float], slave_strategy: Mapping[int, float]
) -> float:
    """Return half NashConv using exact pure best-response enumeration."""

    return e_card_evaluation(emperor_strategy, slave_strategy).exploitability


def e_card_evaluation(
    emperor_strategy: Mapping[int, float], slave_strategy: Mapping[int, float]
) -> EquilibriumEvaluation:
    """Return independently enumerated deviation gains for both E-Card seats."""

    matrix = e_card_payoff_matrix()
    row = tuple(float(emperor_strategy[duel]) for duel in DUELS)
    column = tuple(float(slave_strategy[duel]) for duel in DUELS)
    best_emperor = max(
        sum(float(matrix[i][j]) * column[j] for j in range(len(DUELS)))
        for i in range(len(DUELS))
    )
    worst_for_emperor = min(
        sum(row[i] * float(matrix[i][j]) for i in range(len(DUELS)))
        for j in range(len(DUELS))
    )
    profile_value = e_card_expected_value(emperor_strategy, slave_strategy)
    player_zero_gain = max(0.0, best_emperor - profile_value)
    player_one_gain = max(0.0, profile_value - worst_for_emperor)
    return EquilibriumEvaluation(
        player_0_deviation_gain=(
            0.0 if player_zero_gain <= 1e-12 else player_zero_gain
        ),
        player_1_deviation_gain=(
            0.0 if player_one_gain <= 1e-12 else player_one_gain
        ),
    )


def e_card_expected_value(
    emperor_strategy: Mapping[int, float], slave_strategy: Mapping[int, float]
) -> float:
    """Return expected Emperor score difference for a strategy profile."""

    matrix = e_card_payoff_matrix()
    return sum(
        float(emperor_strategy[emperor])
        * float(slave_strategy[slave])
        * float(matrix[i][j])
        for i, emperor in enumerate(DUELS)
        for j, slave in enumerate(DUELS)
    )
