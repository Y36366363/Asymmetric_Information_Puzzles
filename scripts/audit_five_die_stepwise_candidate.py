"""Train and independently evaluate the frozen five-die MCCFR pilot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aip.core import run_independent_evaluation, strategy_profile_fingerprint
from aip.puzzles.liars_dice import (
    FiveDieStepwiseIndependentEvaluator,
    complete_five_die_policy,
    required_five_die_information_sets,
    train_five_die_external_sampling,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREREGISTRATION = (
    ROOT / "configs/five_die_stepwise_mccfr_preregistration_2026-10-08.json"
)
DEFAULT_PROGRESS = (
    ROOT / "research/results/five_die_stepwise_progress_2026-10-08.json"
)
DEFAULT_OUTPUT = (
    ROOT / "research/results/five_die_stepwise_candidate_2026-10-08.json"
)


def compact_evaluation(report):
    return {
        "evaluator_id": report.evaluator_id,
        "evaluator_method": report.evaluator_method,
        "profile_fingerprint": report.profile_fingerprint,
        "expected_value_to_player_0": report.expected_value_to_player_0,
        "best_response_player_0": report.best_response_player_0,
        "best_response_player_1": report.best_response_player_1,
        "player_0_deviation_gain": report.player_0_deviation_gain,
        "player_1_deviation_gain": report.player_1_deviation_gain,
        "nash_conv": report.nash_conv,
        "exploitability": report.exploitability,
        "maximum_unilateral_deviation_gain": (
            report.maximum_unilateral_deviation_gain
        ),
        "action_value_information_sets": len(report.action_values),
        "passed": report.passed,
        "failures": list(report.failures),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preregistration", type=Path, default=DEFAULT_PREREGISTRATION)
    parser.add_argument("--progress", type=Path, default=DEFAULT_PROGRESS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    plan = json.loads(args.preregistration.read_text(encoding="utf-8"))
    if not plan["frozen_before_training"]:
        raise ValueError("MCCFR pilot must be frozen before training")
    algorithm = plan["algorithm"]
    if algorithm["algorithm_id"] != "external_sampling_mccfr":
        raise ValueError("unsupported candidate algorithm")
    required = required_five_die_information_sets()
    if len(required) != int(plan["candidate_gate"]["required_information_sets"]):
        raise ValueError("preregistered information-set count changed")

    result = train_five_die_external_sampling(
        int(algorithm["iterations"]), seed=int(algorithm["seed"])
    )
    candidate = complete_five_die_policy(result.policy)
    evaluator = FiveDieStepwiseIndependentEvaluator()
    independent = run_independent_evaluation(
        evaluator,
        candidate,
        maximum_exploitability=float(
            plan["candidate_gate"]["maximum_independent_exploitability"]
        ),
    )
    progress = json.loads(args.progress.read_text(encoding="utf-8"))
    latest = progress["chunks"][-1]
    structural_complete = bool(latest["complete"] and latest["structural_audit_passed"])
    candidate_passed = independent.passed
    runtime_allowed = bool(candidate_passed and structural_complete)
    artifact = {
        "experiment_id": plan["experiment_id"],
        "preregistration": str(args.preregistration.relative_to(ROOT)),
        "rules_id": plan["rules_id"],
        "algorithm": result.algorithm.to_artifact(),
        "iterations": result.iterations,
        "sampled_information_sets": len(result.policy),
        "required_information_sets": len(required),
        "sampled_coverage": len(result.policy) / len(required),
        "uniformly_completed_information_sets": len(required) - len(result.policy),
        "completion_rule": algorithm["unvisited_information_set_completion"],
        "candidate_profile_fingerprint": strategy_profile_fingerprint(candidate),
        "independent_evaluation": compact_evaluation(independent),
        "structural_audit": {
            "histories": latest["histories"],
            "information_sets": latest["information_sets"],
            "frontier_nodes": latest["frontier_nodes"],
            "failures": latest["failures"],
            "complete": latest["complete"],
            "passed": latest["structural_audit_passed"],
        },
        "promotion": {
            "candidate_exploitability_gate_passed": candidate_passed,
            "complete_structural_gate_passed": structural_complete,
            "runtime_epsilon_gto_allowed": runtime_allowed,
            "status": (
                "independently_checked_candidate_waiting_for_structural_audit"
                if candidate_passed and not structural_complete
                else "candidate_failed_independent_gate"
                if not candidate_passed
                else "eligible_for_separate_runtime_promotion_review"
            ),
        },
    }
    artifact["audit_completed"] = (
        result.iterations == int(algorithm["iterations"])
        and result.algorithm.seed == int(algorithm["seed"])
        and len(candidate) == len(required)
        and len(independent.action_values) == len(required)
        and not runtime_allowed
    )
    artifact["passed"] = bool(
        artifact["audit_completed"] and candidate_passed and structural_complete
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(artifact, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(args.output)
    return 0 if artifact["audit_completed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
