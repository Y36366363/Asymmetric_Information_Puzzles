#!/usr/bin/env python3
from __future__ import annotations

from aip.puzzles.manor_mystery import MysterySolver


def main() -> None:
    solver = MysterySolver()
    for summary in solver.compare(games=200, seed=20_000):
        print(
            f"{summary.strategy:>11}: solved={summary.solved_rate:.1%}, "
            f"mean suggestions={summary.mean_suggestions:.3f}, "
            f"worst={summary.worst_suggestions}"
        )


if __name__ == "__main__":
    main()
