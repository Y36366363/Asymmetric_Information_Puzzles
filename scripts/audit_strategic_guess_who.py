"""Certify explicit guessing and risk thresholds in the tiny Guess Who duel."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path

from aip.core import (
    CFRGameProperties,
    compile_sequence_form,
    create_regret_minimization_trainer,
    run_independent_evaluation,
    solve_sequence_form,
)
from aip.core.tree_evaluation import FullTreeBestResponseEvaluator
from aip.puzzles.guess_who import (
    DEFAULT_QUESTIONS,
    DEFAULT_ROSTER,
    StrategicGuessWhoGame,
)


CHECKPOINTS = (100, 1_000, 3_000)


def behavior_summary(game, policy):
    result = defaultdict(float)
    positive_reach_infos = set()

    def traverse(state, reach):
        if game.is_terminal(state):
            result["terminal_reach"] += reach
            return
        player = game.current_player(state)
        key = (player, game.information_set(state))
        distribution = policy[key]
        if state.stage.endswith("action") and reach > 1e-12:
            positive_reach_infos.add(key)
            if not state.transcript:
                result["blind_guess_action_mass"] += reach * sum(
                    probability for action, probability in distribution.items()
                    if action[0] == "guess"
                )
        for action, probability in distribution.items():
            if not probability:
                continue
            child_reach = reach * probability
            if state.stage == "player_1_action":
                action_zero = state.pending_player_0_action
                if action_zero is None:
                    raise AssertionError("missing simultaneous action")
                if action_zero[0] == "ask" and action[0] == "ask":
                    result["expected_both_ask_rounds"] += child_reach
                else:
                    ambiguous = (
                        action_zero[0] == "guess"
                        and state.candidates[0].bit_count() > 1
                    ) or (
                        action[0] == "guess"
                        and state.candidates[1].bit_count() > 1
                    )
                    if ambiguous:
                        result["ambiguous_terminal_guess_probability"] += child_reach
            traverse(game.next_state(state, action), child_reach)

    traverse(game.initial_state(), 1.0)
    result["positive_reach_information_sets"] = len(positive_reach_infos)
    result["maximum_root_policy_l1_by_private_secret"] = max(
        sum(abs(first[action] - second[action]) for action in first)
        for player in (0, 1)
        for first in [policy[(player, ("act", first_secret, ()))]
                      for first_secret in range(len(game.roster))]
        for second in [policy[(player, ("act", second_secret, ()))]
                       for second_secret in range(len(game.roster))]
    )
    return dict(result)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path,
        default=Path("research/results/strategic_guess_who_audit_2026-10-02.json"),
    )
    args = parser.parse_args()
    roster = (DEFAULT_ROSTER[0], DEFAULT_ROSTER[6], DEFAULT_ROSTER[12])
    game = StrategicGuessWhoGame(roster, DEFAULT_QUESTIONS[:3])
    form = compile_sequence_form(
        game,
        game_properties=CFRGameProperties(2, True, True, True),
        sparse=True,
    )
    exact = solve_sequence_form(form, backend="scipy_highs")
    evaluator = FullTreeBestResponseEvaluator(
        game, evaluator_id="strategic_guess_who_v1"
    )
    exact_report = run_independent_evaluation(
        evaluator, exact.policy, maximum_exploitability=1e-10
    )
    behavior = behavior_summary(game, exact.policy)
    algorithms = {}
    for algorithm_id in ("vanilla_cfr", "cfr_plus", "dcfr"):
        trainer = create_regret_minimization_trainer(game, algorithm_id)
        previous = 0
        trace = []
        for checkpoint in CHECKPOINTS:
            result = trainer.train(checkpoint - previous)
            report = run_independent_evaluation(
                evaluator, result.policy, maximum_exploitability=1.0
            )
            trace.append({
                "iteration": checkpoint,
                "expected_value_to_player_0": report.expected_value_to_player_0,
                "nash_conv": report.nash_conv,
                "exploitability": report.exploitability,
            })
            previous = checkpoint
        algorithms[algorithm_id] = {
            "algorithm": result.algorithm.to_artifact(),
            "trace": trace,
            "final_passes_cross_check_gate": trace[-1]["exploitability"] < 0.001,
        }
    negative_result = create_regret_minimization_trainer(
        game, "vanilla_cfr"
    ).train(10)
    negative = run_independent_evaluation(
        evaluator, negative_result.policy, maximum_exploitability=0.001
    )
    artifact = {
        "model": "three-character simultaneous adaptive duel with explicit guesses",
        "rules": {
            "correct_unilateral_guess": "win",
            "incorrect_unilateral_guess": "loss",
            "both_guess_equal_correctness": "draw",
            "same_round_opponent_action_visible": False,
        },
        "scope": "research subgame only; no runtime epsilon-GTO label",
        "solver_router": "sparse_sequence_form_lp_primary_cfr_cross_check",
        "tree_audit": form.audit.to_artifact(),
        "sequence_form": {
            "player_0_sequences": len(form.player_sequences[0]),
            "player_1_sequences": len(form.player_sequences[1]),
            "payoff_shape": list(form.payoff_matrix.shape),
            "payoff_nonzeros": len(form.payoff_matrix.entries),
            "backend": exact.backend,
            "value_to_player_0": exact.value_to_player_0,
            "maximum_flow_residual": exact.maximum_flow_residual,
            "primal_dual_gap": exact.primal_dual_gap,
            "independent_evaluation": exact_report.to_artifact(),
        },
        "equilibrium_behavior": behavior,
        "regret_minimization_cross_check": algorithms,
        "undertrained_negative_control": {
            "iterations": 10,
            "exploitability": negative.exploitability,
            "passed_gate": negative.passed,
        },
    }
    artifact["checks"] = {
        "tree_audit": form.audit.passed,
        "exact_independent_gate": exact_report.passed,
        "zero_symmetric_value": abs(exact.value_to_player_0) < 1e-10,
        "no_blind_guessing": behavior["blind_guess_action_mass"] < 1e-10,
        "positive_ambiguous_guessing": (
            behavior["ambiguous_terminal_guess_probability"] > 0.1
        ),
        "root_policy_has_no_private_secret_signal": (
            behavior["maximum_root_policy_l1_by_private_secret"] < 1e-10
        ),
        "all_cfr_cross_checks": all(
            value["final_passes_cross_check_gate"] for value in algorithms.values()
        ),
        "undertrained_negative_control_rejected": not negative.passed,
    }
    artifact["passed"] = all(artifact["checks"].values())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(artifact, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(args.output)
    return 0 if artifact["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
