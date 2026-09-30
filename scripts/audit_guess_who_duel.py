"""Reproduce the restricted three-character Guess Who duel certificate."""

from __future__ import annotations

import argparse
import json
from itertools import permutations
from pathlib import Path

from aip.puzzles.guess_who import DEFAULT_QUESTIONS, DEFAULT_ROSTER, GuessWhoDuel


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path,
        default=Path("research/results/guess_who_duel_audit_2026-09-30.json"),
    )
    args = parser.parse_args()
    roster = (DEFAULT_ROSTER[0], DEFAULT_ROSTER[6], DEFAULT_ROSTER[12])
    questions = DEFAULT_QUESTIONS[:3]
    orders = tuple(permutations(question.id for question in questions))
    game = GuessWhoDuel(roster, questions, orders)
    result = game.solve()
    matrix = game.payoff_matrix()
    pure_maximin = max(min(row) for row in matrix)
    pure_minimax = min(max(matrix[row][column] for row in range(len(matrix)))
                       for column in range(len(matrix)))
    report = {
        "model": "simultaneous_secret_and_fixed_question_priority_commitment",
        "scope": "three-character restricted normal-form game; not full adaptive Guess Who",
        "characters": [character.name for character in roster],
        "questions": [question.id for question in questions],
        "actions_per_player": len(result.actions),
        "payoff": "win=+1, simultaneous identification=0, loss=-1",
        "pure_maximin": pure_maximin,
        "pure_minimax": pure_minimax,
        "value": result.value,
        "nash_conv": result.nash_conv,
        "exploitability": result.exploitability,
        "player_0_deviation_gain": result.player_0_deviation_gain,
        "player_1_deviation_gain": result.player_1_deviation_gain,
        "maximum_unilateral_deviation_gain": result.maximum_unilateral_deviation_gain,
        "player_0_secret_marginals": {
            character.name: sum(probability for action, probability in
                                zip(result.actions, result.player_0_strategy)
                                if action.secret == character.name)
            for character in roster
        },
        "player_1_secret_marginals": {
            character.name: sum(probability for action, probability in
                                zip(result.actions, result.player_1_strategy)
                                if action.secret == character.name)
            for character in roster
        },
        "checks": {
            "no_pure_saddle": pure_maximin < pure_minimax,
            "independent_best_response": result.exploitability < 1e-8,
            "zero_symmetric_value": abs(result.value) < 1e-8,
            "normalized": all(abs(sum(strategy) - 1) < 1e-8 for strategy in
                              (result.player_0_strategy, result.player_1_strategy)),
        },
    }
    report["passed"] = all(report["checks"].values())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.output)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
