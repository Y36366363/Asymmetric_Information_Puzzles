#!/usr/bin/env python3
from __future__ import annotations

from statistics import mean
from time import perf_counter

from aip.puzzles.manor_mystery import MysterySolver


def main() -> None:
    solver = MysterySolver()
    for summary in solver.compare(games=200, seed=20_000):
        print(
            f"{summary.strategy:>11}: solved={summary.solved_rate:.1%}, "
            f"mean suggestions={summary.mean_suggestions:.3f}, "
            f"worst={summary.worst_suggestions}"
        )
    started = perf_counter()
    robust_runs = [
        solver.play(
            30_000 + index,
            strategy="information",
            max_suggestions=8,
            reveal_policy="information_denying",
        )
        for index in range(50)
    ]
    elapsed = perf_counter() - started
    print(
        "adversarial: "
        f"solved={sum(run.solved for run in robust_runs) / len(robust_runs):.1%}, "
        f"mean suggestions={mean(run.suggestions for run in robust_runs):.3f}, "
        f"worst={max(run.suggestions for run in robust_runs)}, "
        f"mean wall time={elapsed / len(robust_runs):.3f}s"
    )


if __name__ == "__main__":
    main()
