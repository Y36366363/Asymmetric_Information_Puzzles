"""Simulation baseline for a future single-player Battleship game."""

from __future__ import annotations

import random
from dataclasses import dataclass
from functools import lru_cache
from math import ceil
from statistics import mean, median
from typing import Protocol

from aip.puzzles.battleship.models import (
    Cell,
    FleetRules,
    ShipPlacement,
    ShotOutcome,
    SimulationSummary,
)


@lru_cache(maxsize=None)
def _placements(size: int, length: int) -> tuple[frozenset[Cell], ...]:
    result: list[frozenset[Cell]] = []
    for row in range(size):
        for column in range(size - length + 1):
            result.append(frozenset((row, column + offset) for offset in range(length)))
    for row in range(size - length + 1):
        for column in range(size):
            result.append(frozenset((row + offset, column) for offset in range(length)))
    return tuple(result)


class HiddenFleetBoard:
    def __init__(self, rules: FleetRules, rng: random.Random) -> None:
        self.rules = rules
        self.ships = self._place_fleet(rng)
        self.shots: set[Cell] = set()
        self.hits: set[Cell] = set()

    def _place_fleet(self, rng: random.Random) -> tuple[ShipPlacement, ...]:
        for _ in range(1_000):
            occupied: set[Cell] = set()
            ships: list[ShipPlacement] = []
            for length in self.rules.ship_lengths:
                candidates = [
                    cells
                    for cells in _placements(self.rules.board_size, length)
                    if cells.isdisjoint(occupied)
                ]
                if not candidates:
                    break
                cells = rng.choice(candidates)
                occupied.update(cells)
                ships.append(ShipPlacement(length, cells))
            if len(ships) == len(self.rules.ship_lengths):
                return tuple(ships)
        raise RuntimeError("could not place a legal fleet")

    @property
    def all_sunk(self) -> bool:
        return all(ship.cells.issubset(self.hits) for ship in self.ships)

    def fire(self, cell: Cell) -> ShotOutcome:
        size = self.rules.board_size
        if cell in self.shots:
            raise ValueError("the same cell cannot be fired at twice")
        if not (0 <= cell[0] < size and 0 <= cell[1] < size):
            raise ValueError("shot is outside the board")
        self.shots.add(cell)
        ship = next((candidate for candidate in self.ships if cell in candidate.cells), None)
        if ship is None:
            return ShotOutcome(cell, hit=False)
        self.hits.add(cell)
        sunk = ship.cells.issubset(self.hits)
        return ShotOutcome(
            cell,
            hit=True,
            sunk=sunk,
            sunk_length=ship.length if sunk else None,
            sunk_cells=ship.cells if sunk else frozenset(),
        )


class TargetingPolicy(Protocol):
    name: str

    def choose(self) -> Cell: ...

    def observe(self, outcome: ShotOutcome) -> None: ...


class _KnowledgePolicy:
    name = "base"

    def __init__(self, rules: FleetRules, rng: random.Random) -> None:
        self.rules = rules
        self.rng = rng
        self.shots: set[Cell] = set()
        self.misses: set[Cell] = set()
        self.unresolved_hits: set[Cell] = set()
        self.sunk_cells: set[Cell] = set()
        self.remaining_lengths = list(rules.ship_lengths)

    def available(self) -> list[Cell]:
        return [
            (row, column)
            for row in range(self.rules.board_size)
            for column in range(self.rules.board_size)
            if (row, column) not in self.shots
        ]

    def observe(self, outcome: ShotOutcome) -> None:
        self.shots.add(outcome.cell)
        if not outcome.hit:
            self.misses.add(outcome.cell)
            return
        self.unresolved_hits.add(outcome.cell)
        if outcome.sunk and outcome.sunk_length is not None:
            self.remaining_lengths.remove(outcome.sunk_length)
            self.sunk_cells.update(outcome.sunk_cells)
            self.unresolved_hits.difference_update(outcome.sunk_cells)

    def _target_neighbors(self) -> list[Cell]:
        size = self.rules.board_size
        candidates: set[Cell] = set()
        for row, column in self.unresolved_hits:
            for cell in ((row - 1, column), (row + 1, column), (row, column - 1), (row, column + 1)):
                if 0 <= cell[0] < size and 0 <= cell[1] < size and cell not in self.shots:
                    candidates.add(cell)
        return sorted(candidates)


class RandomTargetingAI(_KnowledgePolicy):
    name = "random"

    def choose(self) -> Cell:
        return self.rng.choice(self.available())


class HuntTargetAI(_KnowledgePolicy):
    name = "hunt-target"

    def choose(self) -> Cell:
        targets = self._target_neighbors()
        if targets:
            return self.rng.choice(targets)
        parity = [cell for cell in self.available() if sum(cell) % 2 == 0]
        return self.rng.choice(parity or self.available())


class ProbabilityDensityAI(_KnowledgePolicy):
    name = "probability-density"

    def _hit_clusters(self) -> tuple[frozenset[Cell], ...]:
        """Group orthogonally connected hits that a legal straight ship can explain."""

        remaining = set(self.unresolved_hits)
        clusters: list[frozenset[Cell]] = []
        while remaining:
            seed = remaining.pop()
            cluster = {seed}
            frontier = [seed]
            while frontier:
                row, column = frontier.pop()
                for neighbor in (
                    (row - 1, column),
                    (row + 1, column),
                    (row, column - 1),
                    (row, column + 1),
                ):
                    if neighbor in remaining:
                        remaining.remove(neighbor)
                        cluster.add(neighbor)
                        frontier.append(neighbor)
            rows = {row for row, _column in cluster}
            columns = {column for _row, column in cluster}
            if len(rows) == 1 or len(columns) == 1:
                clusters.append(frozenset(cluster))
            else:
                clusters.extend(frozenset((cell,)) for cell in sorted(cluster))
        return tuple(clusters)

    def density_scores(self) -> tuple[dict[Cell, int], int]:
        scores = {cell: 0 for cell in self.available()}
        candidate_count = 0
        for length in self.remaining_lengths:
            candidates = [
                cells
                for cells in _placements(self.rules.board_size, length)
                if cells.isdisjoint(self.misses | self.sunk_cells)
            ]
            # The paired audit supports the stricter cluster model on 10x10 and
            # 12x12.  On 15x15 its P90 regressed, so the large board deliberately
            # keeps the legacy focus rule until a stronger tail result exists.
            if self.unresolved_hits and self.rules.board_size <= 12:
                clusters = self._hit_clusters()
                focused = [
                    cells for cells in candidates
                    if any(cluster.issubset(cells) for cluster in clusters)
                ]
                candidates = focused or candidates
            elif self.unresolved_hits:
                focused = [cells for cells in candidates if cells & self.unresolved_hits]
                candidates = focused or candidates
            candidate_count += len(candidates)
            for cells in candidates:
                for cell in cells:
                    if cell in scores:
                        scores[cell] += 1
        return scores, candidate_count

    def choose(self) -> Cell:
        scores, candidate_count = self.density_scores()
        best_score = max(scores.values())
        best = sorted(cell for cell, score in scores.items() if score == best_score)
        choice = self.rng.choice(best)
        self.last_analysis = {
            "candidatePlacements": candidate_count,
            "peakDensity": best_score,
            "tiedBestCells": len(best),
            "searchMode": "target" if self.unresolved_hits else "hunt",
            "coverageShare": (
                best_score / candidate_count if candidate_count else 0.0
            ),
            "chosenCell": choice,
        }
        return choice


class LegacyProbabilityDensityAI(ProbabilityDensityAI):
    """Pre-2026-08-14 baseline that only required touching one unresolved hit."""

    name = "legacy-density"

    def density_scores(self) -> tuple[dict[Cell, int], int]:
        scores = {cell: 0 for cell in self.available()}
        candidate_count = 0
        for length in self.remaining_lengths:
            candidates = [
                cells
                for cells in _placements(self.rules.board_size, length)
                if cells.isdisjoint(self.misses | self.sunk_cells)
            ]
            if self.unresolved_hits:
                focused = [cells for cells in candidates if cells & self.unresolved_hits]
                candidates = focused or candidates
            candidate_count += len(candidates)
            for cells in candidates:
                for cell in cells:
                    if cell in scores:
                        scores[cell] += 1
        return scores, candidate_count


POLICIES = {
    RandomTargetingAI.name: RandomTargetingAI,
    HuntTargetAI.name: HuntTargetAI,
    LegacyProbabilityDensityAI.name: LegacyProbabilityDensityAI,
    ProbabilityDensityAI.name: ProbabilityDensityAI,
}


@dataclass(slots=True)
class BattleshipSimulator:
    rules: FleetRules = FleetRules()

    def play(self, strategy: str, board_seed: int, policy_seed: int | None = None) -> int:
        try:
            policy_type = POLICIES[strategy]
        except KeyError as error:
            raise ValueError(f"unknown Battleship strategy: {strategy}") from error
        board = HiddenFleetBoard(self.rules, random.Random(board_seed))
        policy = policy_type(self.rules, random.Random(board_seed if policy_seed is None else policy_seed))
        while not board.all_sunk:
            outcome = board.fire(policy.choose())
            policy.observe(outcome)
        return len(board.shots)

    def compare(self, games: int = 200, seed: int = 20260805) -> tuple[SimulationSummary, ...]:
        if games < 1:
            raise ValueError("games must be positive")
        summaries: list[SimulationSummary] = []
        for strategy_index, strategy in enumerate(POLICIES):
            results = [
                self.play(strategy, seed + game, seed + 100_000 * (strategy_index + 1) + game)
                for game in range(games)
            ]
            ordered = sorted(results)
            summaries.append(
                SimulationSummary(
                    strategy=strategy,
                    games=games,
                    mean_shots=round(mean(results), 3),
                    median_shots=median(results),
                    p90_shots=ordered[ceil(0.9 * games) - 1],
                    best_game=ordered[0],
                    worst_game=ordered[-1],
                )
            )
        return tuple(summaries)
