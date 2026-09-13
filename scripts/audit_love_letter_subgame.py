#!/usr/bin/env python3
"""Reproduce the exhaustive Love Letter subgame and ε-GTO audit."""

from __future__ import annotations

import json

from aip.core import CFRResult, ExternalSamplingCFRTrainer
from aip.puzzles.love_letter import (
    LoveLetterCFRGame,
    audit_complete_tree,
    certify_love_letter_subgame,
    complete_information_set_actions,
    love_letter_subgame_evaluation,
)


def main() -> None:
    game = LoveLetterCFRGame.late_round_subgame()
    tree = audit_complete_tree(game)
    tables = complete_information_set_actions(game)
    uniform = CFRResult(
        iterations=1,
        policy={
            key: {action: 1 / len(actions) for action in actions}
            for key, actions in tables.items()
        },
        information_set_visits={key: 1 for key in tables},
        average_positive_regret=(1, 1),
    )
    result = ExternalSamplingCFRTrainer(game, seed=20260912).train(20_000)
    certification = certify_love_letter_subgame(game, result)
    print(
        json.dumps(
            {
                "scope": "four-card Love Letter river subgame (cards 1-4)",
                "tree": {
                    "histories": tree.histories,
                    "chanceHistories": tree.chance_histories,
                    "decisionHistories": tree.decision_histories,
                    "terminalHistories": tree.terminal_histories,
                    "informationSets": tree.information_sets,
                    "hiddenInformationSets": tree.hidden_information_sets,
                    "maximumDepth": tree.maximum_depth,
                    "failures": list(tree.failures),
                },
                "uniformEvaluation": love_letter_subgame_evaluation(
                    game, uniform
                ).to_report(),
                "mccfr": {
                    "iterations": result.iterations,
                    "seed": 20260912,
                    "minimumVisits": min(result.information_set_visits.values()),
                    "averagePositiveRegret": list(
                        result.average_positive_regret
                    ),
                    "evaluation": certification.evaluation.to_report(),
                    "certified": certification.passed,
                    "failures": list(certification.failures),
                },
                "fullRound": {
                    "implemented": True,
                    "exhaustivelyCertified": False,
                    "reason": "complete tree exceeds one million histories",
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
