#!/usr/bin/env python3
from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path

from aip.puzzles.goofspiel import GoofspielSolver


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "web" / "goofspiel-policy.json"


def key(
    player_cards: tuple[int, ...],
    ai_cards: tuple[int, ...],
    prizes: tuple[int, ...],
    current_prize: int,
) -> str:
    return f"{','.join(map(str, player_cards))}|{','.join(map(str, ai_cards))}|{','.join(map(str, prizes))}|{current_prize}"


def main() -> None:
    solver = GoofspielSolver(4)
    table = {}
    for size in range(1, 5):
        for player_cards in combinations(solver.cards, size):
            for ai_cards in combinations(solver.cards, size):
                for prizes in combinations(solver.cards, size):
                    for current_prize in prizes:
                        solution = solver.round_solution(
                            player_cards,
                            ai_cards,
                            prizes,
                            current_prize,
                        )
                        table[key(player_cards, ai_cards, prizes, current_prize)] = {
                            "value": float(solution.value),
                            "player": [float(value) for value in solution.row_strategy],
                            "ai": [float(value) for value in solution.column_strategy],
                        }
    OUTPUT.write_text(
        json.dumps(table, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(table)} exact public-state policies to {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
