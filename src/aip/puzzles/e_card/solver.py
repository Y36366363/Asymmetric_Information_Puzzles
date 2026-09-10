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

from aip.puzzles.goofspiel.solver import MatrixSolution, solve_zero_sum_matrix


DUELS = (1, 2, 3, 4, 5)


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
    return (best_emperor - worst_for_emperor) / 2


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
