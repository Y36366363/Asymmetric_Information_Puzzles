#!/usr/bin/env python3
"""Produce the sequence-form and independent-evaluator certification report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aip.core import (
    CFRArtifactExporter,
    CFRTrainer,
    PromotionEvidence,
    decide_promotion,
    run_independent_evaluation,
    strategy_profile_fingerprint,
)
from aip.puzzles.kuhn_poker import (
    KuhnCFRGame,
    KuhnIndependentEvaluator,
    build_kuhn_sequence_form,
    equilibrium_policy,
    kuhn_policy_profile,
    solve_kuhn_sequence_form,
)
from aip.puzzles.liars_dice import (
    OneDieLiarIndependentEvaluator,
    load_one_die_liar_policy,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "research/results/independent_equilibrium_audit_2026-09-13.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    evaluator = KuhnIndependentEvaluator()
    representation = build_kuhn_sequence_form()
    sequence = solve_kuhn_sequence_form()
    sequence_report = run_independent_evaluation(
        evaluator, sequence.policy, maximum_exploitability=1e-9
    )
    analytic_report = run_independent_evaluation(
        evaluator,
        kuhn_policy_profile(equilibrium_policy()),
        maximum_exploitability=1e-9,
    )
    cfr = CFRTrainer(KuhnCFRGame()).train(10_000)
    cfr_report = run_independent_evaluation(
        evaluator, cfr.policy, maximum_exploitability=0.01
    )
    cfr_promotion = decide_promotion(
        PromotionEvidence(
            artifact_complete=True,
            artifact_profile_fingerprint=strategy_profile_fingerprint(cfr.policy),
            independent_report=cfr_report,
            cross_method_agreement=(
                abs(cfr_report.expected_value_to_player_0 - sequence.value_to_player_0)
                <= 0.001
            ),
            reproducible=False,
            artifact_frozen=False,
        )
    )
    cfr_artifact = CFRArtifactExporter().build(
        cfr,
        game_id="canonical_kuhn_poker",
        independent_evaluation=cfr_report,
    )

    liar_path = ROOT / "src/aip/puzzles/liars_dice/one_die_cfr_policy.json"
    liar_result = load_one_die_liar_policy(liar_path)
    liar_report = run_independent_evaluation(
        OneDieLiarIndependentEvaluator(),
        liar_result.policy,
        maximum_exploitability=0.01,
    )
    liar_promotion = decide_promotion(
        PromotionEvidence(
            artifact_complete=True,
            artifact_profile_fingerprint=strategy_profile_fingerprint(
                liar_result.policy
            ),
            independent_report=liar_report,
        )
    )
    checks = {
        "sequence_form_primal_dual_gap": sequence.primal_dual_gap <= 1e-10,
        "sequence_form_flow": sequence.maximum_flow_residual <= 1e-10,
        "analytic_equilibrium_independent_br": analytic_report.passed,
        "sequence_equilibrium_independent_br": sequence_report.passed,
        "analytic_sequence_value_agreement": abs(
            analytic_report.expected_value_to_player_0
            - sequence_report.expected_value_to_player_0
        )
        <= 1e-10,
        "kuhn_cfr_independent_br": cfr_report.passed,
        "one_die_liar_independent_br": liar_report.passed,
        "runtime_requires_independently_checked": (
            liar_promotion.epsilon_gto_runtime_allowed
        ),
    }
    report = {
        "audit_version": "1.0.0",
        "dependency_decision": {
            "new_runtime_dependency": None,
            "implementation": "dependency-free two-phase simplex",
            "scipy_alternative": "BSD-3-Clause; optional future HiGHS backend; binary install cost",
            "cvxopt_alternative": "GPLv3; not selected for the MIT application boundary",
        },
        "kuhn_sequence_form": {
            "sequences_per_player": [
                len(sequences) for sequences in representation.player_sequences
            ],
            "flow_constraints_per_player": [
                len(matrix) for matrix in representation.flow_matrices
            ],
            "value_to_player_0": sequence.value_to_player_0,
            "maximum_flow_residual": sequence.maximum_flow_residual,
            "primal_dual_gap": sequence.primal_dual_gap,
            "independent_report": sequence_report.to_artifact(),
        },
        "kuhn_analytic_equilibrium": analytic_report.to_artifact(),
        "kuhn_cfr_candidate": {
            "artifact": cfr_artifact,
            "promotion": cfr_promotion.to_artifact(),
        },
        "one_die_liar": {
            "independent_report": liar_report.to_artifact(),
            "promotion": liar_promotion.to_artifact(),
        },
        "checks": checks,
        "passed": all(checks.values()),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(args.output)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
