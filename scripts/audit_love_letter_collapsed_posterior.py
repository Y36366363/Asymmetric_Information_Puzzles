"""Audit the preregistered acquisition-order-collapsed Love Letter target."""

from __future__ import annotations

import argparse
import json
from math import fsum
from pathlib import Path

from aip.benchmark.love_letter import (
    LoveLetterValueDecompositionOracle,
    build_private_hand_full_support_policy,
    love_letter_action_id,
    love_letter_strategic_hidden_state,
)
from aip.core import run_independent_evaluation
from aip.puzzles.love_letter import LoveLetterCFRGame, LoveLetterIndependentEvaluator


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREREGISTRATION = (
    ROOT
    / "configs/love_letter_collapsed_posterior_preregistration_2026-10-07.json"
)
DEFAULT_OUTPUT = (
    ROOT / "research/results/love_letter_collapsed_posterior_2026-10-07.json"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preregistration", type=Path, default=DEFAULT_PREREGISTRATION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    plan = json.loads(args.preregistration.read_text(encoding="utf-8"))
    if not plan["frozen_before_outcome_evaluation"]:
        raise ValueError("collapsed-posterior experiment is not frozen")
    target = plan["posterior_target"]
    if target["removed_fields"] != ["opponent_private_acquisition_history"]:
        raise ValueError("collapsed target changed its declared equivalence rule")
    policy_plan = plan["fixed_policy"]
    if not policy_plan["reuse_without_parameter_changes"]:
        raise ValueError("fixed policy must be reused without parameter changes")

    game = LoveLetterCFRGame.late_round_subgame()
    fixed_policy = build_private_hand_full_support_policy(
        game,
        floor=float(policy_plan["floor"]),
        kept_card_coefficient=float(policy_plan["kept_card_coefficient"]),
        played_card_coefficient=float(policy_plan["played_card_coefficient"]),
        guard_guess_coefficient=float(policy_plan["guard_guess_coefficient"]),
    )
    evaluator = LoveLetterIndependentEvaluator(game)
    fixed_evaluation = run_independent_evaluation(
        evaluator, fixed_policy, maximum_exploitability=0.001
    )
    oracle = LoveLetterValueDecompositionOracle(
        game,
        hidden_world_projector=love_letter_strategic_hidden_state,
        prior_method_id="love_letter_strategic_hidden_state_combinatorial_prior_v1",
        posterior_target=target["target_id"],
    )
    panel = oracle.decompose_conditioned_all(fixed_policy)
    exact_values = evaluator.action_values(fixed_policy)
    shift_threshold = float(
        plan["primary_endpoints"]["maximum_posterior_l1_shift"]
        ["positive_threshold"]
    )
    support_minimum = int(
        plan["primary_endpoints"]
        ["information_sets_with_nontrivial_support_after_observed_opponent_action"]
        ["nontrivial_support_minimum"]
    )
    rows = []
    for key, decomposition in sorted(
        panel.decompositions.items(), key=lambda item: repr(item[0])
    ):
        hero, information_set = key
        public_history = information_set[6]
        observed_opponent_action = any(event[0] != hero for event in public_history)
        normalization = fsum(
            decomposition.base_prior[world]
            * decomposition.policy_reach_weights[world]
            for world in decomposition.base_prior
        )
        bayes_error = max(
            abs(
                decomposition.values.posterior[world]
                - decomposition.base_prior[world]
                * decomposition.policy_reach_weights[world]
                / normalization
            )
            for world in decomposition.base_prior
        )
        expected = {
            love_letter_action_id(action): float(value)
            for action, value in exact_values[key].items()
        }
        value_error = max(
            abs(decomposition.values.total_action_values[action] - expected[action])
            for action in expected
        )
        posterior_l1 = fsum(
            abs(
                decomposition.base_prior[world]
                - decomposition.values.posterior[world]
            )
            for world in decomposition.base_prior
        )
        rows.append(
            {
                "information_set": repr(key),
                "hero": hero,
                "observed_opponent_action": observed_opponent_action,
                "support_size": len(decomposition.base_prior),
                "base_prior": dict(decomposition.base_prior),
                "policy_reach_weights": dict(
                    decomposition.policy_reach_weights
                ),
                "conditioned_posterior": dict(decomposition.values.posterior),
                "posterior_l1_shift": posterior_l1,
                "maximum_bayes_reconstruction_error": bayes_error,
                "maximum_value_reconstruction_error": value_error,
                "maximum_additivity_residual": (
                    decomposition.values.maximum_additivity_residual
                ),
            }
        )

    post_action_nontrivial = sum(
        row["observed_opponent_action"]
        and row["support_size"] >= support_minimum
        for row in rows
    )
    maximum_shift = max(row["posterior_l1_shift"] for row in rows)
    gates = plan["mechanical_gates"]
    checks = {
        "complete_full_support_panel": (
            panel.total_information_sets == gates["expected_total_information_sets"]
            and len(panel.zero_reach_information_sets)
            == gates["expected_zero_reach_information_sets_under_full_support"]
        ),
        "bayes_reconstruction": max(
            row["maximum_bayes_reconstruction_error"] for row in rows
        )
        <= gates["maximum_bayes_reconstruction_error"],
        "value_reconstruction": max(
            row["maximum_value_reconstruction_error"] for row in rows
        )
        <= gates["maximum_value_reconstruction_error"],
        "value_additivity": max(
            row["maximum_additivity_residual"] for row in rows
        )
        <= gates["maximum_additivity_residual"],
        "fixed_policy_rejected_as_equilibrium": not fixed_evaluation.passed,
    }
    predicted = int(
        plan["primary_endpoints"]
        ["information_sets_with_nontrivial_support_after_observed_opponent_action"]
        ["predicted_value"]
    )
    routing_decision = (
        plan["decision_rule"]["if_no_nontrivial_post_action_support"]
        if post_action_nontrivial == 0
        else plan["decision_rule"]["if_nontrivial_post_action_support_exists"]
    )
    artifact = {
        "experiment_id": plan["experiment_id"],
        "preregistration": str(args.preregistration.relative_to(ROOT)),
        "scope": plan["scope"],
        "posterior_target": target,
        "prior_method_id": panel.prior_method_id,
        "fixed_policy": {
            **policy_plan,
            "independent_exploitability": fixed_evaluation.exploitability,
            "equilibrium_gate_passed": fixed_evaluation.passed,
            "gto_label_allowed": False,
        },
        "panel": {
            "total_information_sets": panel.total_information_sets,
            "positive_reach_information_sets": len(panel.decompositions),
            "zero_reach_information_sets": len(panel.zero_reach_information_sets),
            "support_size_counts": {
                str(size): sum(row["support_size"] == size for row in rows)
                for size in sorted({row["support_size"] for row in rows})
            },
            "information_sets_after_observed_opponent_action": sum(
                row["observed_opponent_action"] for row in rows
            ),
            "information_sets_with_nontrivial_support_after_observed_opponent_action": post_action_nontrivial,
            "maximum_posterior_l1_shift": maximum_shift,
            "information_sets_with_posterior_shift": sum(
                row["posterior_l1_shift"] >= shift_threshold for row in rows
            ),
            "maximum_bayes_reconstruction_error": max(
                row["maximum_bayes_reconstruction_error"] for row in rows
            ),
            "maximum_value_reconstruction_error": max(
                row["maximum_value_reconstruction_error"] for row in rows
            ),
            "maximum_additivity_residual": max(
                row["maximum_additivity_residual"] for row in rows
            ),
            "rows": rows,
        },
        "primary_result": {
            "predicted_post_action_nontrivial_support_count": predicted,
            "observed_post_action_nontrivial_support_count": post_action_nontrivial,
            "prediction_matched": post_action_nontrivial == predicted,
            "maximum_posterior_l1_shift": maximum_shift,
            "classification": (
                "no_identifiable_post_action_belief_target"
                if post_action_nontrivial == 0
                else "identifiable_post_action_belief_target_exists"
            ),
        },
        "routing_decision": routing_decision,
        "checks": checks,
        "runtime_epsilon_gto_allowed": False,
        "full_round_certified": False,
    }
    artifact["passed"] = all(checks.values())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(artifact, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(args.output)
    return 0 if artifact["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
