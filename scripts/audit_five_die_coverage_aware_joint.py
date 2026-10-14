"""Run the frozen coverage-aware joint-stratified five-die experiment."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from aip.core import run_independent_evaluation
from aip.puzzles.liars_dice import (
    JOINT_STRATIFICATION_EPOCH_SIZE,
    ORDERED_DICE_HISTOGRAMS,
    CoverageAwareJointStratifiedFiveDieTrainer,
    FiveDieStepwiseIndependentEvaluator,
    joint_stratified_epoch,
    required_five_die_information_sets,
    visited_information_set_count,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREREGISTRATION = (
    ROOT / "configs/five_die_coverage_aware_joint_preregistration_2026-10-13.json"
)
DEFAULT_PROGRESS = (
    ROOT / "research/results/five_die_stepwise_progress_2026-10-08.json"
)
DEFAULT_OUTPUT = (
    ROOT / "research/results/five_die_coverage_aware_joint_2026-10-14.json"
)


def _compact_evaluation(report) -> dict[str, object]:
    artifact = report.to_artifact()
    artifact.pop("action_values")
    artifact["action_value_information_sets"] = len(report.action_values)
    return artifact


def _validate_prior_evidence(plan: dict) -> tuple[dict, list[dict[str, object]]]:
    prerequisite_path = ROOT / plan["small_game_prerequisite"]["artifact"]
    prerequisite = json.loads(prerequisite_path.read_text(encoding="utf-8"))
    if prerequisite.get("passed") is not True:
        raise ValueError("small-game prerequisite did not pass")
    retained = []
    for relative in plan["retained_failed_experiments"]:
        artifact = json.loads((ROOT / relative).read_text(encoding="utf-8"))
        if artifact.get("passed") is not False:
            raise ValueError(f"retained experiment is no longer failed: {relative}")
        retained.append({"path": relative, "passed": False})
    return prerequisite, retained


def _validate_schedule(seed: int, epochs: int) -> dict[str, object]:
    expected = Counter(ORDERED_DICE_HISTOGRAMS)
    checked = 0
    reproducible = True
    for epoch in range(epochs):
        schedules = joint_stratified_epoch(seed=seed, epoch=epoch)
        reproducible = reproducible and schedules == joint_stratified_epoch(
            seed=seed, epoch=epoch
        )
        for own, opponent in schedules:
            if Counter(own) != expected or Counter(opponent) != expected:
                raise ValueError("joint schedule changed a five-die chance marginal")
            checked += 2
    return {
        "epochs": epochs,
        "hand_schedules_checked": checked,
        "microstates_per_hand_schedule": JOINT_STRATIFICATION_EPOCH_SIZE,
        "exact_true_marginals": True,
        "fixed_schedule_reproducible": reproducible,
        "exhaustive_joint_histogram_pairs_claimed": False,
    }


def _normalized_complete(result, required: int) -> bool:
    return len(result.policy) == required and all(
        distribution
        and all(probability >= 0 for probability in distribution.values())
        and abs(sum(distribution.values()) - 1.0) <= 1e-9
        for distribution in result.policy.values()
    )


def _checkpoint(result, required: int, threshold: float) -> dict[str, object]:
    visited = visited_information_set_count(result.information_set_visits)
    fallback = {
        key
        for key, used in result.average_strategy_fallback_used.items()
        if used
    }
    zero_weight = {
        key
        for key, weight in result.average_strategy_observation_weight.items()
        if weight <= 0
    }
    evaluation = run_independent_evaluation(
        FiveDieStepwiseIndependentEvaluator(),
        result.policy,
        maximum_exploitability=threshold,
    )
    return {
        "iterations": result.iterations,
        "completed_chance_epochs": (
            result.iterations // JOINT_STRATIFICATION_EPOCH_SIZE
        ),
        "initialized_information_sets": len(result.policy),
        "visited_information_sets": visited,
        "visited_coverage": visited / required,
        "positive_observation_weight_information_sets": required - len(zero_weight),
        "raw_observation_weight_coverage": 1 - len(zero_weight) / required,
        "fallback_information_sets": len(fallback),
        "fallback_fraction": len(fallback) / required,
        "fallback_exactly_equals_zero_weight_set": fallback == zero_weight,
        "normalized_complete_policy": _normalized_complete(result, required),
        "average_positive_regret": list(result.average_positive_regret),
        "independent_evaluation": _compact_evaluation(evaluation),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preregistration", type=Path, default=DEFAULT_PREREGISTRATION)
    parser.add_argument("--progress", type=Path, default=DEFAULT_PROGRESS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    plan = json.loads(args.preregistration.read_text(encoding="utf-8"))
    if plan["status"] != "frozen_before_implementation_and_training":
        raise ValueError("five-die experiment was not frozen before training")
    prerequisite, retained = _validate_prior_evidence(plan)
    algorithm = plan["algorithm"]
    if algorithm["algorithm_id"] != (
        CoverageAwareJointStratifiedFiveDieTrainer.ALGORITHM_ID
    ):
        raise ValueError("unsupported five-die coverage-aware algorithm")
    if int(algorithm["iterations"]) != (
        int(algorithm["epoch_size"]) * int(algorithm["epochs"])
    ):
        raise ValueError("budget must contain complete chance epochs")

    schedule = _validate_schedule(
        seed=int(algorithm["seed"]), epochs=int(algorithm["epochs"])
    )
    required = len(required_five_die_information_sets())
    gates_plan = plan["candidate_gates"]
    threshold = float(gates_plan["maximum_final_independent_exploitability"])
    trainer = CoverageAwareJointStratifiedFiveDieTrainer(
        seed=int(algorithm["seed"])
    )
    checkpoints = []
    previous = 0
    for target in algorithm["checkpoints"]:
        result = trainer.train(int(target) - previous)
        previous = int(target)
        point = _checkpoint(result, required, threshold)
        checkpoints.append(point)
        print(
            f"checkpoint={target} visited={point['visited_information_sets']}/{required} "
            f"fallback={point['fallback_fraction']:.6f} "
            f"exploitability={point['independent_evaluation']['exploitability']:.12f}",
            flush=True,
        )

    prior_joint = json.loads(
        (
            ROOT
            / "research/results/five_die_stepwise_joint_stratification_2026-10-10.json"
        ).read_text(encoding="utf-8")
    )
    retained_exploitability = prior_joint["checkpoints"][-1][
        "independent_evaluation"
    ]["exploitability"]
    final = checkpoints[-1]
    final_eval = final["independent_evaluation"]
    candidate_gates = {
        "independent_exploitability": final_eval["exploitability"] <= threshold,
        "positive_visit_coverage": final["visited_coverage"]
        >= float(gates_plan["minimum_positive_visit_coverage"]),
        "fallback_fraction": final["fallback_fraction"]
        <= float(gates_plan["maximum_final_fallback_fraction"]),
        "fallback_exactly_equals_zero_weight_set": final[
            "fallback_exactly_equals_zero_weight_set"
        ],
        "normalized_complete_policy": final["normalized_complete_policy"],
        "fixed_schedule_reproducibility": schedule[
            "fixed_schedule_reproducible"
        ],
        "improved_over_retained_joint_result": final_eval["exploitability"]
        < retained_exploitability,
        "required_information_sets": required
        == int(gates_plan["required_information_sets"]),
    }
    candidate_passed = all(candidate_gates.values())

    progress = json.loads(args.progress.read_text(encoding="utf-8"))
    structural = progress["chunks"][-1]
    structural_passed = bool(
        structural["complete"] and structural["structural_audit_passed"]
    )
    runtime_allowed = bool(candidate_passed and structural_passed)
    exploitabilities = [
        point["independent_evaluation"]["exploitability"]
        for point in checkpoints
    ]
    artifact = {
        "experiment_id": plan["experiment_id"],
        "preregistration": str(args.preregistration.relative_to(ROOT)),
        "rules_id": plan["rules_id"],
        "small_game_prerequisite": {
            "path": plan["small_game_prerequisite"]["artifact"],
            "passed": prerequisite["passed"],
        },
        "retained_failed_experiments": retained,
        "retained_joint_exploitability": retained_exploitability,
        "algorithm": trainer.algorithm_spec.to_artifact(),
        "schedule_audit": schedule,
        "required_information_sets": required,
        "checkpoints": checkpoints,
        "convergence": {
            "exploitability_nonincreasing": all(
                later <= earlier
                for earlier, later in zip(exploitabilities, exploitabilities[1:])
            ),
            "monotonicity_required": False,
        },
        "gates": {
            **candidate_gates,
            "candidate_passed": candidate_passed,
            "complete_structural_audit_passed": structural_passed,
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
                else "coverage_aware_joint_candidate_failed"
            ),
        },
        "audit_completed": (
            trainer.iterations == int(algorithm["iterations"])
            and len(checkpoints) == len(algorithm["checkpoints"])
            and all(
                point["initialized_information_sets"] == required
                and point["independent_evaluation"][
                    "action_value_information_sets"
                ]
                == required
                for point in checkpoints
            )
        ),
        "candidate_passed": candidate_passed,
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
