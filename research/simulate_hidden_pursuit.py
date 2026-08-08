"""Run the backend-only Hidden Pursuit policy comparison."""

from __future__ import annotations

import argparse

from aip.puzzles.hidden_pursuit import HiddenPursuitSimulator


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=int, default=500)
    parser.add_argument("--seed", type=int, default=20260808)
    args = parser.parse_args()
    print("detectives,fugitive,games,capture_rate,mean_capture_round")
    for result in HiddenPursuitSimulator().compare(args.games, args.seed):
        print(
            result.detective_policy,
            result.fugitive_policy,
            result.games,
            result.capture_rate,
            result.mean_capture_round,
            sep=",",
        )


if __name__ == "__main__":
    main()
