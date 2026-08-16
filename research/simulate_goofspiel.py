#!/usr/bin/env python3
from __future__ import annotations

from aip.puzzles.goofspiel import GoofspielSolver


def main() -> None:
    solver = GoofspielSolver(4)
    print(f"initial exact game value: {solver.state_value(solver.cards, solver.cards, solver.cards)}")
    for summary in solver.compare(games=2_000, seed=30_000):
        print(
            f"{summary.policy:>12}: player mean difference={summary.player_mean_difference:+.3f}, "
            f"win={summary.player_win_rate:.1%}, draw={summary.draw_rate:.1%}"
        )


if __name__ == "__main__":
    main()
