"""Repeatable backend audit for Battleship targeting policies.

This program intentionally uses only the Python research engine. It does not
start, inspect, or modify the web game.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from statistics import mean

from aip.puzzles.battleship.models import FleetRules
from aip.puzzles.battleship.solver import BattleshipSimulator


FLEETS = {
    10: (5, 4, 3, 3, 2),
    12: (6, 5, 4, 3, 3, 2),
    15: (7, 6, 5, 4, 4, 3, 2),
}


@dataclass(frozen=True, slots=True)
class PairedTailAudit:
    games: int
    probability_better: int
    tied: int
    probability_worse: int
    mean_shot_delta: float
    largest_regret: int
    largest_gain: int


def paired_tail_audit(games: int, seed: int) -> PairedTailAudit:
    """Compare hunt and density policies on exactly the same hidden fleets."""

    simulator = BattleshipSimulator()
    deltas: list[int] = []
    for game in range(games):
        board_seed = seed + game
        hunt = simulator.play("hunt-target", board_seed, seed + 100_000 + game)
        density = simulator.play(
            "probability-density", board_seed, seed + 200_000 + game
        )
        deltas.append(density - hunt)
    return PairedTailAudit(
        games=games,
        probability_better=sum(delta < 0 for delta in deltas),
        tied=sum(delta == 0 for delta in deltas),
        probability_worse=sum(delta > 0 for delta in deltas),
        mean_shot_delta=round(mean(deltas), 3),
        largest_regret=max(deltas),
        largest_gain=-min(deltas),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260807)
    args = parser.parse_args()
    if args.games < 1:
        parser.error("--games must be positive")

    print("size,strategy,mean,median,p90,best,worst")
    for size, lengths in FLEETS.items():
        simulator = BattleshipSimulator(FleetRules(size, lengths))
        for summary in simulator.compare(games=args.games, seed=args.seed):
            print(
                size,
                summary.strategy,
                summary.mean_shots,
                summary.median_shots,
                summary.p90_shots,
                summary.best_game,
                summary.worst_game,
                sep=",",
            )

    tail = paired_tail_audit(args.games, args.seed)
    print("\npaired 10x10 density-minus-hunt audit")
    print(
        f"better={tail.probability_better}, tied={tail.tied}, "
        f"worse={tail.probability_worse}, mean_delta={tail.mean_shot_delta}, "
        f"largest_regret={tail.largest_regret}, largest_gain={tail.largest_gain}"
    )


if __name__ == "__main__":
    main()
