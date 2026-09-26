#!/usr/bin/env python3
"""Recompute evidence-backed completion status for the main exact-game targets."""

from __future__ import annotations

import json
from pathlib import Path

from aip.benchmark import evaluate_goofspiel_policy, evaluate_kuhn_policy
from aip.core import (
    CFRGameProperties,
    compile_sequence_form,
    run_independent_evaluation,
    solve_sequence_form,
)
from aip.puzzles.e_card import (
    DUELS,
    e_card_exploitability,
    solve_e_card_timing_game,
)
from aip.puzzles.kuhn_poker import equilibrium_policy
from aip.puzzles.liars_dice import (
    OneDieLiarIndependentEvaluator,
    solve_one_die_liar_exact,
)
from aip.puzzles.love_letter import LoveLetterCFRGame, LoveLetterIndependentEvaluator


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "research/results/game_readiness_2026-09-26.json"
LOVE_PROGRESS = ROOT / "research/results/love_letter_local_progress_2026-09-17.json"


def report() -> dict[str, object]:
    _, liar_solution = solve_one_die_liar_exact()
    liar_report = run_independent_evaluation(
        OneDieLiarIndependentEvaluator(),
        liar_solution.policy,
        maximum_exploitability=1e-10,
    )
    goof = evaluate_goofspiel_policy("equilibrium")
    kuhn = evaluate_kuhn_policy(equilibrium_policy())
    e_card = solve_e_card_timing_game()
    e_card_profile = dict(zip(DUELS, map(float, e_card.emperor_strategy)))

    love_game = LoveLetterCFRGame.late_round_subgame()
    love_solution = solve_sequence_form(
        compile_sequence_form(
            love_game,
            game_properties=CFRGameProperties(2, True, True, True),
            sparse=True,
        ),
        backend="scipy_highs",
    )
    love_evaluator = LoveLetterIndependentEvaluator(love_game)
    love_report = run_independent_evaluation(
        love_evaluator,
        love_solution.policy,
        maximum_exploitability=1e-12,
    )
    progress = json.loads(LOVE_PROGRESS.read_text(encoding="utf-8"))
    latest = progress["chunks"][-1]

    games = {
        "one-die-stepwise-liars-dice": {
            "status": "complete_declared_variant",
            "solver": "exact_sequence_form_plus_certified_runtime_cfr",
            "independentEvaluator": True,
            "exploitability": liar_report.exploitability,
            "runtimeEpsilonGtoAllowed": True,
            "valueDecomposition": "complete_30_state_panel",
            "remainingWork": [
                "structured-model intermediate-output experiment",
                "new certificate required for any expanded bidding rules",
            ],
        },
        "five-die-liars-dice": {
            "status": "heuristic_only_not_gto",
            "solver": "transparent_probability_heuristic",
            "independentEvaluator": False,
            "runtimeEpsilonGtoAllowed": False,
            "valueDecomposition": "not_applicable_to_current_heuristic_rules",
            "remainingWork": [
                "freeze exact rules and action abstraction",
                "build scalable candidate and independent best response",
            ],
        },
        "goofspiel-four-card": {
            "status": "complete_exact_solver_and_benchmark",
            "solver": "exact_backward_induction_zero_sum_matrices",
            "independentEvaluator": True,
            "exploitability": float(goof.exploitability),
            "runtimeExactEquilibriumMode": True,
            "valueDecomposition": "complete_30_state_panel",
            "remainingWork": ["structured-model intermediate-output experiment"],
        },
        "kuhn-poker": {
            "status": "complete_exact_reference",
            "solver": "analytic_plus_sequence_form_plus_best_response",
            "independentEvaluator": True,
            "maximumUnilateralDeviationGain": float(
                kuhn.maximum_unilateral_deviation_gain
            ),
            "remainingWork": ["optional second adversarial model target"],
        },
        "e-card-single-round": {
            "status": "complete_solver_control",
            "solver": "exact_timing_matrix",
            "exploitability": e_card_exploitability(
                e_card_profile,
                dict(zip(DUELS, map(float, e_card.slave_strategy))),
            ),
            "runtimeScope": "multi-round adaptation remains strong heuristic",
            "remainingWork": ["retain as exact solver control, not primary agent task"],
        },
        "love-letter-four-card-subgame": {
            "status": "complete_certified_research_subgame",
            "solver": "sparse_sequence_form_scipy_highs",
            "independentEvaluator": True,
            "histories": love_evaluator.audit.histories,
            "informationSets": len(love_report.action_values),
            "expectedValueToPlayer0": love_report.expected_value_to_player_0,
            "exploitability": love_report.exploitability,
            "runtimeFullRoundAllowed": False,
            "valueDecomposition": "17_positive_reach_43_zero_reach_information_sets",
            "remainingWork": ["do not generalize certificate to full round"],
        },
        "love-letter-full-round": {
            "status": "blocked_on_complete_structural_enumeration",
            "solver": "none_complete",
            "independentEvaluator": False,
            "historiesTraversed": latest["histories"],
            "informationSetsObserved": latest["information_sets"],
            "frontierNodes": latest["frontier_nodes"],
            "maximumDepth": latest["maximum_depth"],
            "structuralFailures": latest["failures"],
            "structuralAuditComplete": latest["complete"],
            "runtimeEpsilonGtoAllowed": False,
            "remainingWork": [
                "close resumable structural audit",
                "compile and solve complete candidate",
                "run complete independent best response",
                "bind profile fingerprint to promotion evidence",
            ],
        },
    }
    return {
        "schemaVersion": "aip-game-readiness-v1",
        "date": "2026-09-26",
        "games": games,
        "conclusion": {
            "basicConstructionComplete": [
                "one-die-stepwise-liars-dice",
                "goofspiel-four-card",
                "kuhn-poker",
                "e-card-single-round",
                "love-letter-four-card-subgame",
            ],
            "notComplete": ["five-die-liars-dice", "love-letter-full-round"],
            "nextPriority": (
                "structured intermediate-output check on Liar and Goofspiel; "
                "continue bounded Love Letter full-round audit independently"
            ),
        },
    }


def main() -> int:
    value = report()
    OUTPUT.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(value["conclusion"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
