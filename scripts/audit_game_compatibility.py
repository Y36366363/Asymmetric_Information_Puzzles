#!/usr/bin/env python3
"""Generate the cross-game independent-evaluator compatibility artifact."""

from __future__ import annotations

import json
from pathlib import Path

from aip.core import (
    ExternalSamplingCFRTrainer,
    FullTreeBestResponseEvaluator,
    PromotionEvidence,
    decide_promotion,
    recommend_equilibrium_solver,
    run_independent_evaluation,
    strategy_profile_fingerprint,
)
from aip.puzzles.e_card import (
    DUELS,
    ECardIndependentEvaluator,
    e_card_evaluation,
    e_card_equilibrium_structure,
    e_card_profile,
    exact_e_card_promotion,
    solve_e_card_timing_game,
)
from aip.puzzles.kuhn_poker import (
    KuhnCFRGame,
    KuhnIndependentEvaluator,
    solve_kuhn_sequence_form,
)
from aip.puzzles.love_letter import (
    LoveLetterCFRGame,
    LoveLetterIndependentEvaluator,
    love_letter_equilibrium_structure,
    love_letter_subgame_evaluation,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "research/results/game_compatibility_audit_2026-09-14.json"


def recommendation_artifact(structure) -> dict[str, object]:
    recommendation = recommend_equilibrium_solver(structure)
    return {
        "eligible_for_gto_pipeline": recommendation.eligible_for_gto_pipeline,
        "primary": recommendation.primary.value,
        "cross_check": (
            None
            if recommendation.cross_check is None
            else recommendation.cross_check.value
        ),
        "reasons": list(recommendation.reasons),
    }


def main() -> None:
    e_card_solution = solve_e_card_timing_game()
    emperor = dict(zip(DUELS, map(float, e_card_solution.emperor_strategy)))
    slave = dict(zip(DUELS, map(float, e_card_solution.slave_strategy)))
    e_card_policy = e_card_profile(emperor, slave)
    e_card_evaluator = ECardIndependentEvaluator()
    e_card_report = run_independent_evaluation(
        e_card_evaluator, e_card_policy, maximum_exploitability=1e-12
    )
    e_card_legacy = e_card_evaluation(emperor, slave)

    kuhn_solution = solve_kuhn_sequence_form()
    kuhn_specialized = run_independent_evaluation(
        KuhnIndependentEvaluator(),
        kuhn_solution.policy,
        maximum_exploitability=1e-12,
    )
    kuhn_evaluator = FullTreeBestResponseEvaluator(
        KuhnCFRGame(), evaluator_id="kuhn_shared_full_tree_v1"
    )
    kuhn_shared = run_independent_evaluation(
        kuhn_evaluator,
        kuhn_solution.policy,
        maximum_exploitability=1e-12,
    )

    love_game = LoveLetterCFRGame.late_round_subgame()
    love_result = ExternalSamplingCFRTrainer(love_game, seed=20260912).train(20_000)
    love_evaluator = LoveLetterIndependentEvaluator(love_game)
    love_report = run_independent_evaluation(
        love_evaluator, love_result.policy, maximum_exploitability=0.001
    )
    love_legacy = love_letter_subgame_evaluation(love_game, love_result)
    love_fingerprint = strategy_profile_fingerprint(love_result.policy)
    love_cross_method = (
        abs(love_report.nash_conv - love_legacy.nash_conv) <= 1e-12
    )
    love_promotion = decide_promotion(
        PromotionEvidence(
            artifact_complete=True,
            artifact_profile_fingerprint=love_fingerprint,
            independent_report=love_report,
            cross_method_agreement=love_cross_method,
        )
    )
    try:
        LoveLetterIndependentEvaluator(
            LoveLetterCFRGame(), maximum_histories=10_000
        )
    except OverflowError as error:
        full_round_boundary = {
            "passed": True,
            "certified": False,
            "reason": str(error),
        }
    else:
        full_round_boundary = {
            "passed": False,
            "certified": True,
            "reason": "full round unexpectedly fit the declared audit budget",
        }

    checks = {
        "e_card_matrix_and_tree_value_agree": abs(
            e_card_report.expected_value_to_player_0
            - float(e_card_solution.emperor_value)
        )
        <= 1e-12,
        "e_card_matrix_and_tree_nash_conv_agree": abs(
            e_card_report.nash_conv - e_card_legacy.nash_conv
        )
        <= 1e-12,
        "e_card_exact_policy_is_frozen": (
            exact_e_card_promotion().level.artifact_name == "frozen"
        ),
        "kuhn_specialized_and_shared_value_agree": abs(
            kuhn_shared.expected_value_to_player_0
            - kuhn_specialized.expected_value_to_player_0
        )
        <= 1e-12,
        "kuhn_specialized_and_shared_nash_conv_agree": abs(
            kuhn_shared.nash_conv - kuhn_specialized.nash_conv
        )
        <= 2e-15,
        "love_letter_later_chance_tree_passes_audit": love_evaluator.audit.passed,
        "love_letter_legacy_and_shared_nash_conv_agree": love_cross_method,
        "love_letter_subgame_passes_independent_gate": love_report.passed,
        "love_letter_full_round_remains_out_of_scope": full_round_boundary["passed"],
    }
    artifact = {
        "audit_version": "game_compatibility_v1",
        "scope": "small_finite_two_player_zero_sum_perfect_recall_games",
        "shared_evaluator": {
            "methods": [
                "expected_value",
                "best_response",
                "nash_conv",
                "exploitability",
                "action_values",
            ],
            "structural_gates": [
                "finite_tree_within_budget",
                "two_players",
                "finite_terminal_utility",
                "valid_chance_distribution",
                "information_set_action_consistency",
                "perfect_recall",
                "exact_normalized_policy_coverage",
            ],
            "training_regret_used": False,
        },
        "e_card": {
            "structure": "hidden_simultaneous_commitment_without_chance",
            "routing": recommendation_artifact(e_card_equilibrium_structure()),
            "tree_audit": e_card_evaluator.audit.to_artifact(),
            "independent_report": e_card_report.to_artifact(),
            "matrix_nash_conv": e_card_legacy.nash_conv,
            "promotion": exact_e_card_promotion().to_artifact(),
            "runtime_scope": {
                "single_round_core": "frozen_exact_equilibrium",
                "multi_round_adaptation": "strong_heuristic_not_epsilon_gto",
            },
        },
        "kuhn_poker": {
            "structure": "initial_private_chance_then_public_actions",
            "tree_audit": kuhn_evaluator.audit.to_artifact(),
            "sequence_form_value": kuhn_solution.value_to_player_0,
            "specialized_report": kuhn_specialized.to_artifact(),
            "shared_report": kuhn_shared.to_artifact(),
        },
        "love_letter_four_card_subgame": {
            "structure": "later_private_chance_and_card_effects",
            "routing_for_full_game": recommendation_artifact(
                love_letter_equilibrium_structure()
            ),
            "tree_audit": love_evaluator.audit.to_artifact(),
            "algorithm": love_result.algorithm.to_artifact(),
            "iterations": love_result.iterations,
            "independent_report": love_report.to_artifact(),
            "legacy_nash_conv": love_legacy.nash_conv,
            "promotion": love_promotion.to_artifact(),
            "certification_scope": "four_card_late_round_subgame_only",
            "full_round_boundary": full_round_boundary,
        },
        "checks": checks,
        "passed": all(checks.values()),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if not artifact["passed"]:
        raise SystemExit("cross-game compatibility audit failed")
    print(OUTPUT)


if __name__ == "__main__":
    main()
