from __future__ import annotations

from dataclasses import dataclass

Cell = tuple[int, int]


@dataclass(frozen=True, slots=True)
class FleetRules:
    board_size: int = 10
    ship_lengths: tuple[int, ...] = (5, 4, 3, 3, 2)

    def __post_init__(self) -> None:
        if self.board_size < 3:
            raise ValueError("board_size must be at least 3")
        if not self.ship_lengths or any(
            length < 2 or length > self.board_size for length in self.ship_lengths
        ):
            raise ValueError("every ship must fit the board and have length at least 2")


@dataclass(frozen=True, slots=True)
class ShipPlacement:
    length: int
    cells: frozenset[Cell]


@dataclass(frozen=True, slots=True)
class ShotOutcome:
    cell: Cell
    hit: bool
    sunk: bool = False
    sunk_length: int | None = None
    sunk_cells: frozenset[Cell] = frozenset()


@dataclass(frozen=True, slots=True)
class SimulationSummary:
    strategy: str
    games: int
    mean_shots: float
    median_shots: float
    p90_shots: int
    best_game: int
    worst_game: int

    def as_dict(self) -> dict[str, int | float | str]:
        return {
            "strategy": self.strategy,
            "games": self.games,
            "meanShots": self.mean_shots,
            "medianShots": self.median_shots,
            "p90Shots": self.p90_shots,
            "bestGame": self.best_game,
            "worstGame": self.worst_game,
        }
