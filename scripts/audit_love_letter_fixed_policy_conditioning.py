"""Audit the preregistered fixed-policy Love Letter belief panel."""

from __future__ import annotations

import argparse
import json
from math import fsum
from pathlib import Path

from aip.benchmark.love_letter import (
    LoveLetterValueDecompositionOracle,
    build_private_hand_full_support_policy,
    love_letter_action_id,
)
from aip.core import (
    CFRGameProperties,
    compile_sequence_form,
    run_independent_evaluation,
    solve_sequence_form,
    strategy_profile_fingerprint,
)
from aip.puzzles.love_letter import LoveLetterCFRGame, LoveLetterIndependentEvaluator


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREREGISTRATION = (
    ROOT
    / "configs/love_letter_fixed_policy_conditioning_preregistration_2026-10-06.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "research/results/love_letter_fixed_policy_conditioning_2026-10-06.json"
)


def _posterior_l1(decomposition) -> float:
    return fsum(
        abs(
            decomposition.base_prior[world]
            - decomposition.values.posterior[world]
        )
        for world in decomposition.base_prior
    )


def _summarize_panel(panel, exact_values, shift_threshold):
    rows = []
    maximum_bayes_error = 0.0
    maximum_value_error = 0.0
    maximum_additivity_residual = 0.0
    for key, decomposition in sorted(panel.decompositions.items(), key=lambda item: repr(item[0])):
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
        expected_values = {
            love_letter_action_id(action): float(value)
            for action, value in exact_values[key].items()
        }
        value_error = max(
            abs(
                decomposition.values.total_action_values[action]
                - expected_values[action]
            )
            for action in expected_values
        )
        shift = _posterior_l1(decomposition)
        maximum_bayes_error = max(maximum_bayes_error, bayes_error)
        maximum_value_error = max(maximum_value_error, value_error)
        maximum_additivity_residual = max(
            maximum_additivity_residual,
            decomposition.values.maximum_additivity_residual,
        )
        rows.append(
            {
                "information_set": repr(key),
                "base_prior": dict(decomposition.base_prior),
                "policy_reach_weights": dict(
                    decomposition.policy_reach_weights
                ),
                "conditioned_posterior": dict(decomposition.values.posterior),
                "posterior_l1_shift": shift,
                "shifted": shift >= shift_threshold,
                "maximum_bayes_reconstruction_error": bayes_error,
                "maximum_value_reconstruction_error": value_error,
                "maximum_additivity_residual": (
                    decomposition.values.maximum_additivity_residual
                ),
                "chosen_action_id": decomposition.values.chosen_action_id,
            }
        )
    return {
        "total_information_sets": panel.total_information_sets,
        "positive_reach_information_sets": len(panel.decompositions),
        "zero_reach_information_sets": len(panel.zero_reach_information_sets),
        "shifted_information_sets": sum(row["shifted"] for row in rows),
        "maximum_posterior_l1_shift": max(
            (row["posterior_l1_shift"] for row in rows), default=0.0
        ),
        "maximum_bayes_reconstruction_error": maximum_bayes_error,
        "maximum_value_reconstruction_error": maximum_value_error,
        "maximum_additivity_residual": maximum_additivity_residual,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preregistration", type=Path, default=DEFAULT_PREREGISTRATION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    plan = json.loads(args.preregistration.read_text(encoding="utf-8"))
    if not plan["frozen_before_outcome_evaluation"]:
        raise ValueError("experiment must be frozen before outcome evaluation")
    if plan["scope"] != "certified_four_card_late_round_subgame_only":
        raise ValueError("unsupported Love Letter experiment scope")
    policy_parameters = {
        key: float(plan["fixed_policy"][key])
        for key in (
            "floor",
            "kept_card_coefficient",
            "played_card_coefficient",
            "guard_guess_coefficient",
        )
    }
    game = LoveLetterCFRGame.late_round_subgame()
    form = compile_sequence_form(
        game,
        game_properties=CFRGameProperties(2, True, True, True),
        sparse=True,
    )
    equilibrium = solve_sequence_form(form, backend="scipy_highs")
    fixed_policy = build_private_hand_full_support_policy(
        game, **policy_parameters
    )
    evaluator = LoveLetterIndependentEvaluator(game)
    controls = plan["controls"]
    equilibrium_report = run_independent_evaluation(
        evaluator,
        equilibrium.policy,
        maximum_exploitability=float(
            controls["equilibrium_maximum_exploitability"]
        ),
    )
    fixed_policy_report = run_independent_evaluation(
        evaluator,
        fixed_policy,
        maximum_exploitability=float(
            controls["fixed_policy_must_fail_equilibrium_gate"]
        ),
    )
    oracle = LoveLetterValueDecompositionOracle(game)
    shift_threshold = float(
        plan["primary_endpoints"]
        ["maximum_posterior_l1_shift_from_combinatorial_prior"]
        ["positive_threshold"]
    )
    equilibrium_panel = oracle.decompose_conditioned_all(equilibrium.policy)
    fixed_panel = oracle.decompose_conditioned_all(fixed_policy)
    equilibrium_summary = _summarize_panel(
        equilibrium_panel,
        evaluator.action_values(equilibrium.policy),
        shift_threshold,
    )
    fixed_summary = _summarize_panel(
        fixed_panel,
        evaluator.action_values(fixed_policy),
        shift_threshold,
    )
    gates = plan["mechanical_gates"]
    minimum_shifted = int(
        plan["primary_endpoints"]["information_sets_with_posterior_shift"]
        ["minimum_count"]
    )
    checks = {
        "tree_audit": form.audit.passed,
        "equilibrium_independent_gate": equilibrium_report.passed,
        "equilibrium_reach_partition": (
            equilibrium_summary["positive_reach_information_sets"]
            == controls[
                "equilibrium_panel_expected_positive_reach_information_sets"
            ]
            and equilibrium_summary["zero_reach_information_sets"]
            == controls[
                "equilibrium_panel_expected_zero_reach_information_sets"
            ]
        ),
        "equilibrium_zero_shift_control": (
            equilibrium_summary["shifted_information_sets"]
            == controls["equilibrium_panel_expected_shifted_information_sets"]
        ),
        "fixed_policy_full_support_reach": (
            fixed_summary["total_information_sets"]
            == gates["expected_total_information_sets"]
            and fixed_summary["zero_reach_information_sets"]
            == gates[
                "expected_zero_reach_information_sets_under_full_support"
            ]
        ),
        "fixed_policy_bayes_reconstruction": (
            fixed_summary["maximum_bayes_reconstruction_error"]
            <= gates["maximum_bayes_reconstruction_error"]
        ),
        "fixed_policy_value_reconstruction": (
            fixed_summary["maximum_value_reconstruction_error"]
            <= gates["maximum_value_reconstruction_error"]
        ),
        "fixed_policy_additivity": (
            fixed_summary["maximum_additivity_residual"]
            <= gates["maximum_additivity_residual"]
        ),
        "fixed_policy_rejected_as_equilibrium": not fixed_policy_report.passed,
    }
    hypothesis_checks = {
        "fixed_policy_positive_conditioning_signal": (
            fixed_summary["maximum_posterior_l1_shift"] >= shift_threshold
            and fixed_summary["shifted_information_sets"] >= minimum_shifted
        )
    }
    artifact = {
        "experiment_id": plan["experiment_id"],
        "preregistration": str(args.preregistration.relative_to(ROOT)),
        "scope": plan["scope"],
        "prior_method_id": plan["prior_method_id"],
        "fixed_policy": {
            **plan["fixed_policy"],
            "profile_fingerprint": strategy_profile_fingerprint(fixed_policy),
            "minimum_action_probability": min(
                probability
                for distribution in fixed_policy.values()
                for probability in distribution.values()
            ),
            "maximum_action_probability": max(
                probability
                for distribution in fixed_policy.values()
                for probability in distribution.values()
            ),
            "independent_evaluation": fixed_policy_report.to_artifact(),
            "gto_label_allowed": False,
        },
        "equilibrium_control": {
            "value_to_player_0": equilibrium.value_to_player_0,
            "independent_evaluation": equilibrium_report.to_artifact(),
            "panel": equilibrium_summary,
        },
        "fixed_policy_panel": fixed_summary,
        "primary_result": {
            "classification": (
                "positive_conditioning_signal"
                if hypothesis_checks["fixed_policy_positive_conditioning_signal"]
                else "zero_conditioning_signal"
            ),
            "maximum_posterior_l1_shift": fixed_summary[
                "maximum_posterior_l1_shift"
            ],
            "shifted_information_sets": fixed_summary[
                "shifted_information_sets"
            ],
            "positive_threshold": shift_threshold,
        },
        "checks": checks,
        "hypothesis_checks": hypothesis_checks,
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
