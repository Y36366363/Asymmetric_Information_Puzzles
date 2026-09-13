"""Small dependency-free two-phase simplex for certification-scale LPs."""

from __future__ import annotations

from dataclasses import dataclass
from math import inf, isfinite


@dataclass(frozen=True, slots=True)
class LinearProgramSolution:
    objective: float
    variables: tuple[float, ...]


def maximize_linear_program(
    objective: tuple[float, ...],
    inequalities: tuple[tuple[float, ...], ...],
    bounds: tuple[float, ...],
    *,
    tolerance: float = 1e-10,
) -> LinearProgramSolution:
    """Maximize c*x subject to A*x <= b and x >= 0.

    The implementation is intentionally small and intended for independent
    certification of tiny games. It uses an artificial variable for phase one,
    deterministic Bland-style tie breaking, and no external numeric package.
    """

    variable_count = len(objective)
    constraint_count = len(bounds)
    if variable_count == 0 or constraint_count == 0:
        raise ValueError("linear program must contain variables and constraints")
    if len(inequalities) != constraint_count or any(
        len(row) != variable_count for row in inequalities
    ):
        raise ValueError("linear-program matrix dimensions are inconsistent")
    numbers = (*objective, *bounds, *(value for row in inequalities for value in row))
    if any(not isfinite(value) for value in numbers):
        raise ValueError("linear-program coefficients must be finite")
    if not isfinite(tolerance) or tolerance <= 0:
        raise ValueError("linear-program tolerance must be finite and positive")

    # Columns: original variables, artificial variable, right-hand side.
    tableau = [
        [0.0] * (variable_count + 2) for _ in range(constraint_count + 2)
    ]
    basic = [variable_count + row for row in range(constraint_count)]
    nonbasic = list(range(variable_count)) + [-1]
    for row in range(constraint_count):
        for column in range(variable_count):
            tableau[row][column] = inequalities[row][column]
        tableau[row][variable_count] = -1.0
        tableau[row][variable_count + 1] = bounds[row]
    for column in range(variable_count):
        tableau[constraint_count][column] = -objective[column]
    tableau[constraint_count + 1][variable_count] = 1.0

    def pivot(leaving: int, entering: int) -> None:
        inverse = 1.0 / tableau[leaving][entering]
        for row in range(constraint_count + 2):
            if row == leaving:
                continue
            for column in range(variable_count + 2):
                if column == entering:
                    continue
                tableau[row][column] -= (
                    tableau[leaving][column]
                    * tableau[row][entering]
                    * inverse
                )
        for column in range(variable_count + 2):
            if column != entering:
                tableau[leaving][column] *= inverse
        for row in range(constraint_count + 2):
            if row != leaving:
                tableau[row][entering] *= -inverse
        tableau[leaving][entering] = inverse
        basic[leaving], nonbasic[entering] = (
            nonbasic[entering],
            basic[leaving],
        )

    def simplex(phase: int) -> bool:
        objective_row = constraint_count + 1 if phase == 1 else constraint_count
        while True:
            entering = min(
                (
                    column
                    for column in range(variable_count + 1)
                    if not (phase == 2 and nonbasic[column] == -1)
                ),
                key=lambda column: (
                    tableau[objective_row][column], nonbasic[column]
                ),
            )
            if tableau[objective_row][entering] >= -tolerance:
                return True
            candidates = [
                row
                for row in range(constraint_count)
                if tableau[row][entering] > tolerance
            ]
            if not candidates:
                return False
            leaving = min(
                candidates,
                key=lambda row: (
                    tableau[row][variable_count + 1]
                    / tableau[row][entering],
                    basic[row],
                ),
            )
            pivot(leaving, entering)

    first_negative = min(
        range(constraint_count),
        key=lambda row: tableau[row][variable_count + 1],
    )
    if tableau[first_negative][variable_count + 1] < -tolerance:
        pivot(first_negative, variable_count)
        if not simplex(1) or tableau[constraint_count + 1][variable_count + 1] < -tolerance:
            raise ValueError("linear program is infeasible")
        if abs(tableau[constraint_count + 1][variable_count + 1]) > tolerance:
            raise ValueError("linear program is infeasible")
        for row in range(constraint_count):
            if basic[row] == -1:
                entering = min(
                    range(variable_count + 1),
                    key=lambda column: (
                        abs(tableau[row][column]) <= tolerance,
                        nonbasic[column],
                    ),
                )
                if abs(tableau[row][entering]) > tolerance:
                    pivot(row, entering)

    if not simplex(2):
        raise ValueError("linear program is unbounded")
    variables = [0.0] * variable_count
    for row, variable in enumerate(basic):
        if 0 <= variable < variable_count:
            variables[variable] = tableau[row][variable_count + 1]
    value = tableau[constraint_count][variable_count + 1]
    if value in (inf, -inf) or not isfinite(value):
        raise ValueError("linear program produced a non-finite solution")
    return LinearProgramSolution(value, tuple(variables))
