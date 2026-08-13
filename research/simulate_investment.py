"""Repeatable policy comparison for the virtual investment tournament."""

from __future__ import annotations

import random

from aip.puzzles.investment import InvestmentTournament, Opportunity


def simulate(games: int = 3000) -> list[dict[str, float | str]]:
    policies = {
        "cash": lambda offer: 0.0,
        "flat_10": lambda offer: 0.10,
        "half_kelly": lambda offer: min(0.75, offer.kelly / 2),
        "kelly": lambda offer: min(0.75, offer.kelly),
        "double_kelly": lambda offer: min(0.75, offer.kelly * 2),
    }
    rows = []
    for name, stake in policies.items():
        titles = survivors = 0
        bankrolls = []
        for seed in range(games):
            tournament = InvestmentTournament(random.Random(seed))
            while tournament.phase == "decision":
                offer: Opportunity = max(
                    tournament.offers, key=lambda item: item.expected_return
                )
                tournament.invest(offer.id, stake(offer))
            player = next(item for item in tournament.contestants if item.id == "player")
            titles += tournament.winner == "player"
            survivors += player.alive
            bankrolls.append(player.bankroll)
        rows.append(
            {
                "policy": name,
                "title_rate": titles / games,
                "survival_rate": survivors / games,
                "mean_bankroll": sum(bankrolls) / games,
            }
        )
    return rows


if __name__ == "__main__":
    for row in simulate():
        print(
            f"{row['policy']:>12}  title={row['title_rate']:.2%}  "
            f"survive={row['survival_rate']:.2%}  mean={row['mean_bankroll']:.1f}"
        )
