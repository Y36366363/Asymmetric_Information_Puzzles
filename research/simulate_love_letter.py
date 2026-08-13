"""Repeatable match-level comparison for Love Letter policies."""

from __future__ import annotations

import argparse
import random

from aip.puzzles.love_letter.solver import LoveLetterGame


def compare(games: int, seed: int) -> list[dict[str, float | str]]:
    matchups = (("belief", "random"), ("random", "belief"), ("belief", "belief"))
    rows: list[dict[str, float | str]] = []
    for player_policy, ai_policy in matchups:
        player_wins = decisions = 0
        for offset in range(games):
            game = LoveLetterGame(random.Random(seed + offset))
            while game.phase != "match_finished":
                if game.phase == "round_finished":
                    game.start_round()
                    continue
                actor = "player" if game.phase == "player_turn" else "ai"
                policy = player_policy if actor == "player" else ai_policy
                game.play(actor, game.choose_play(actor, policy))
                decisions += 1
            player_wins += game.round_winner == "player"
        rows.append(
            {
                "player": player_policy,
                "ai": ai_policy,
                "player_win_rate": player_wins / games,
                "mean_decisions": decisions / games,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=int, default=2_000)
    parser.add_argument("--seed", type=int, default=20260814)
    args = parser.parse_args()
    if args.games < 1:
        parser.error("--games must be positive")
    print("player,ai,games,player_win_rate,mean_decisions")
    for row in compare(args.games, args.seed):
        print(
            row["player"],
            row["ai"],
            args.games,
            row["player_win_rate"],
            row["mean_decisions"],
            sep=",",
        )


if __name__ == "__main__":
    main()
