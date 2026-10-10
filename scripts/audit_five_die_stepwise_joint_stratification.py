"""Run the frozen joint-marginal five-die MCCFR experiment."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from aip.core import run_independent_evaluation
from aip.puzzles.liars_dice import (
    JOINT_STRATIFICATION_EPOCH_SIZE,
    ORDERED_DICE_HISTOGRAMS,
    FiveDieStepwiseIndependentEvaluator,
    JointStratifiedFiveDieExternalSamplingTrainer,
    joint_stratified_epoch,
    required_five_die_information_sets,
    visited_information_set_count,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREREGISTRATION = (
    ROOT
    / "configs/five_die_stepwise_joint_stratification_preregistration_2026-10-10.json"
)
DEFAULT_ORIGINAL = (
    ROOT / "research/results/five_die_stepwise_candidate_2026-10-08.json"
)
DEFAULT_BASELINE = (
    ROOT / "research/results/five_die_stepwise_coverage_2026-10-09.json"
)
DEFAULT_PROGRESS = (
    ROOT / "research/results/five_die_stepwise_progress_2026-10-08.json"
)
DEFAULT_OUTPUT = (
    ROOT / "research/results/five_die_stepwise_joint_stratification_2026-10-10.json"
)


def _compact_evaluation(report) -> dict[str, object]:
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


def _validate_retained_evidence(plan: dict, original: dict, baseline: dict) -> None:
    expected = plan["comparison_baseline"]
    final = baseline["checkpoints"][-1]
    observed = {
        "experiment_id": baseline["experiment_id"],
        "iterations": final["iterations"],
        "visited_information_sets": final["visited_information_sets"],
        "required_information_sets": baseline["required_information_sets"],
        "visited_coverage": final["visited_coverage"],
        "independent_exploitability": final["independent_evaluation"][
            "exploitability"
        ],
        "passed_gate": final["independent_evaluation"]["passed"],
    }
    if observed != expected:
        raise ValueError("comparison baseline no longer matches preregistration")
    if original.get("passed") is not False or baseline.get("passed") is not False:
        raise ValueError("both retained experiments must remain failed evidence")


def _validate_schedules(seed: int, epochs: int) -> dict[str, object]:
    expected = Counter(ORDERED_DICE_HISTOGRAMS)
    checked = 0
    for epoch in range(epochs):
        for own, opponent in joint_stratified_epoch(seed=seed, epoch=epoch):
            if Counter(own) != expected or Counter(opponent) != expected:
                raise ValueError("joint-stratified schedule changed the chance marginal")
            checked += 2
    return {
        "epochs": epochs,
        "hand_schedules_checked": checked,
        "microstates_per_hand_schedule": JOINT_STRATIFICATION_EPOCH_SIZE,
        "histograms_per_hand_schedule": len(expected),
        "exact_true_marginals": True,
        "exhaustive_joint_histogram_pairs_claimed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preregistration", type=Path, default=DEFAULT_PREREGISTRATION)
    parser.add_argument("--original", type=Path, default=DEFAULT_ORIGINAL)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--progress", type=Path, default=DEFAULT_PROGRESS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    plan = json.loads(args.preregistration.read_text(encoding="utf-8"))
    original = json.loads(args.original.read_text(encoding="utf-8"))
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    if not plan["frozen_before_training"]:
        raise ValueError("joint-stratification experiment must be frozen")
    _validate_retained_evidence(plan, original, baseline)
    algorithm = plan["algorithm"]
    if algorithm["algorithm_id"] != (
        JointStratifiedFiveDieExternalSamplingTrainer.ALGORITHM_ID
    ):
        raise ValueError("unsupported joint-stratification algorithm")
    if int(algorithm["iterations"]) != (
        int(algorithm["epoch_size"]) * int(algorithm["epochs"])
    ):
        raise ValueError("training budget must contain complete fixed epochs")

    schedule_audit = _validate_schedules(
        int(algorithm["seed"]), int(algorithm["epochs"])
    )
    required_count = len(required_five_die_information_sets())
    trainer = JointStratifiedFiveDieExternalSamplingTrainer(
        seed=int(algorithm["seed"])
    )
    checkpoints = []
    previous = 0
    threshold = float(
        plan["primary_endpoints"]["final_independent_exploitability"]["maximum"]
    )
    for target in algorithm["checkpoints"]:
        result = trainer.train(int(target) - previous)
        previous = int(target)
        visited = visited_information_set_count(result.information_set_visits)
        independent = run_independent_evaluation(
            FiveDieStepwiseIndependentEvaluator(),
            result.policy,
            maximum_exploitability=threshold,
        )
        checkpoints.append(
            {
                "iterations": result.iterations,
                "completed_chance_epochs": (
                    result.iterations // JOINT_STRATIFICATION_EPOCH_SIZE
                ),
                "initialized_information_sets": len(result.policy),
                "visited_information_sets": visited,
                "visited_coverage": visited / required_count,
                "average_positive_regret": list(result.average_positive_regret),
                "independent_evaluation": _compact_evaluation(independent),
            }
        )
        print(
            f"checkpoint={target} visited={visited}/{required_count} "
            f"exploitability={independent.exploitability:.12f}",
            flush=True,
        )

    final = checkpoints[-1]
    final_evaluation = final["independent_evaluation"]
    comparison = plan["comparison_baseline"]
    coverage_gate = bool(
        final["visited_coverage"]
        >= float(
            plan["primary_endpoints"]["visited_information_set_coverage"][
                "minimum"
            ]
        )
        and final["visited_coverage"] > float(comparison["visited_coverage"])
    )
    improvement_gate = final_evaluation["exploitability"] < float(
        comparison["independent_exploitability"]
    )
    independent_gate = bool(final_evaluation["passed"])

    progress = json.loads(args.progress.read_text(encoding="utf-8"))
    structural = progress["chunks"][-1]
    structural_gate = bool(
        structural["complete"] and structural["structural_audit_passed"]
    )
    candidate_passed = bool(coverage_gate and improvement_gate and independent_gate)
    runtime_allowed = bool(candidate_passed and structural_gate)
    exploitabilities = [
        point["independent_evaluation"]["exploitability"]
        for point in checkpoints
    ]

    artifact = {
        "experiment_id": plan["experiment_id"],
        "preregistration": str(args.preregistration.relative_to(ROOT)),
        "retained_experiments": [
            {
                "path": str(args.original.relative_to(ROOT)),
                "passed": original["passed"],
                "independent_exploitability": original["independent_evaluation"]
                ["exploitability"],
            },
            {
                "path": str(args.baseline.relative_to(ROOT)),
                "passed": baseline["passed"],
                "independent_exploitability": comparison[
                    "independent_exploitability"
                ],
                "visited_coverage": comparison["visited_coverage"],
            },
        ],
        "rules_id": plan["rules_id"],
        "algorithm": trainer.algorithm_spec.to_artifact(),
        "average_strategy_estimator_changed": False,
        "schedule_audit": schedule_audit,
        "required_information_sets": required_count,
        "coverage_measure": "positive_information_set_visit_count",
        "checkpoints": checkpoints,
        "convergence": {
            "exploitability_nonincreasing": all(
                later <= earlier
                for earlier, later in zip(exploitabilities, exploitabilities[1:])
            ),
            "monotonicity_required": False,
        },
        "gates": {
            "visited_coverage_passed": coverage_gate,
            "improved_over_comparison_baseline": improvement_gate,
            "independent_exploitability_passed": independent_gate,
            "candidate_passed": candidate_passed,
            "complete_structural_audit_passed": structural_gate,
        },
        "structural_audit": {
            "histories": structural["histories"],
            "information_sets": structural["information_sets"],
            "frontier_nodes": structural["frontier_nodes"],
            "failures": structural["failures"],
            "complete": structural["complete"],
            "passed": structural["structural_audit_passed"],
        },
        "promotion": {
            "runtime_epsilon_gto_allowed": runtime_allowed,
            "status": (
                "eligible_for_separate_runtime_promotion_review"
                if runtime_allowed
                else "candidate_passed_waiting_for_structural_audit"
                if candidate_passed
                else "joint_stratification_experiment_failed_candidate_gate"
            ),
        },
        "audit_completed": (
            trainer.iterations == int(algorithm["iterations"])
            and len(checkpoints) == len(algorithm["checkpoints"])
            and schedule_audit["exact_true_marginals"] is True
            and all(
                point["initialized_information_sets"] == required_count
                and point["independent_evaluation"][
                    "action_value_information_sets"
                ]
                == required_count
                for point in checkpoints
            )
        ),
        "passed": runtime_allowed,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(artifact, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(args.output, flush=True)
    return 0 if artifact["audit_completed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
