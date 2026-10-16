#!/usr/bin/env python3
"""Run the frozen one-die private-information semantic negative control."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform

from aip.core import (
    CFRGameProperties,
    FullTreeBestResponseEvaluator,
    audit_observation_invariance,
    audit_small_extensive_form,
    compile_sequence_form,
    run_independent_evaluation,
    solve_sequence_form,
)
from aip.puzzles.liars_dice import (
    OneDieLiarDiceCFRGame,
    OneDieLiarIndependentEvaluator,
    one_die_private_die_invariance_cases,
    solve_one_die_liar_exact,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = (
    ROOT / "configs/one_die_private_information_semantic_audit_v1.json"
)
DEFAULT_OUTPUT = (
    ROOT / "research/results/one_die_private_information_semantic_audit_2026-10-16.json"
)
PROPERTIES = CFRGameProperties(2, True, True, True)


class OpponentDieLeakingOneDieGame(OneDieLiarDiceCFRGame):
    """Negative control whose only mutation reveals the opponent's die."""

    def information_set(self, state):
        player = self.current_player(state)
        if player is None or state.dice is None:
            raise ValueError("chance and terminal states have no player information set")
        return state.dice, state.bids


def _compact_evaluation(report) -> dict[str, object]:
    artifact = report.to_artifact()
    artifact.pop("action_values")
    artifact["action_value_information_sets"] = len(report.action_values)
    return artifact


def _solve_inside_adapter(game, evaluator_id: str) -> dict[str, object]:
    form = compile_sequence_form(
        game,
        game_properties=PROPERTIES,
        sparse=True,
        maximum_histories=10_000,
        maximum_nonzeros=100_000,
    )
    solution = solve_sequence_form(
        form, backend="scipy_highs", time_limit=30.0
    )
    report = run_independent_evaluation(
        FullTreeBestResponseEvaluator(game, evaluator_id=evaluator_id),
        solution.policy,
        maximum_exploitability=1e-10,
    )
    return {
        "representation": {
            "histories": form.audit.histories,
            "information_sets": form.audit.information_sets,
            "player_sequence_counts": [
                len(form.player_sequences[0]), len(form.player_sequences[1])
            ],
            "payoff_nonzeros": len(form.payoff_matrix.entries),
        },
        "value_to_player_0": solution.value_to_player_0,
        "maximum_flow_residual": solution.maximum_flow_residual,
        "primal_dual_gap": solution.primal_dual_gap,
        "independent_evaluation": _compact_evaluation(report),
    }


def run_audit(contract_path: Path) -> dict[str, object]:
    raw_contract = contract_path.read_bytes()
    contract = json.loads(raw_contract)
    if contract["status"] != "frozen_before_execution":
        raise ValueError("semantic audit contract was not frozen before execution")

    cases = one_die_private_die_invariance_cases()
    expected_cases = int(contract["paired_case_design"]["expected_cases"])
    if len(cases) != expected_cases:
        raise ValueError("generated semantic cases do not match the frozen contract")

    correct = OneDieLiarDiceCFRGame()
    mutant = OpponentDieLeakingOneDieGame()
    correct_structure = audit_small_extensive_form(correct, maximum_histories=10_000)
    mutant_structure = audit_small_extensive_form(mutant, maximum_histories=10_000)
    correct_semantics = audit_observation_invariance(correct, cases)
    mutant_semantics = audit_observation_invariance(mutant, cases)

    _, correct_solution = solve_one_die_liar_exact()
    correct_report = run_independent_evaluation(
        OneDieLiarIndependentEvaluator(),
        correct_solution.policy,
        maximum_exploitability=1e-10,
    )
    correct_internal = {
        "value_to_player_0": correct_solution.value_to_player_0,
        "maximum_flow_residual": correct_solution.maximum_flow_residual,
        "primal_dual_gap": correct_solution.primal_dual_gap,
        "independent_evaluation": _compact_evaluation(correct_report),
    }
    mutant_internal = _solve_inside_adapter(
        mutant, "one_die_liar_opponent_die_leak_negative_control_v1"
    )

    gates = {
        "correct_structural_audit_passes": correct_structure.passed,
        "correct_observation_invariance_passes": correct_semantics.passed,
        "mutant_observation_invariance_fails": not mutant_semantics.passed,
        "mutant_only_changes_information_set_observable": (
            dict(mutant_semantics.violations_by_component)
            == {"information_set": expected_cases}
        ),
        "mutant_violation_count_matches_contract": (
            mutant_semantics.violations == expected_cases
        ),
    }
    hypothesis_checks = {
        "mutant_structural_audit_passes": mutant_structure.passed,
    }
    secondary_checks = {
        "correct_internal_exploitability_passes": correct_report.passed,
        "mutant_internal_exploitability_passes": mutant_internal[
            "independent_evaluation"
        ]["passed"],
    }

    try:
        import numpy
        import scipy
        numerical_environment = {
            "numpy": numpy.__version__,
            "scipy": scipy.__version__,
        }
    except ImportError:
        numerical_environment = {"numpy": None, "scipy": None}

    return {
        "schema_version": "aip-semantic-negative-control-v1",
        "experiment_id": contract["contract_id"],
        "date": "2026-10-16",
        "contract": str(contract_path.relative_to(ROOT)),
        "contract_sha256": sha256(raw_contract).hexdigest(),
        "mutation": contract["mutation"],
        "case_design": {
            **contract["paired_case_design"],
            "actual_cases": len(cases),
        },
        "correct_adapter": {
            "structural_audit": correct_structure.to_artifact(),
            "observation_invariance": correct_semantics.to_artifact(),
            "internal_solution": correct_internal,
        },
        "mutant_adapter": {
            "structural_audit": mutant_structure.to_artifact(),
            "observation_invariance": mutant_semantics.to_artifact(),
            "internal_solution": mutant_internal,
        },
        "primary_gates": gates,
        "primary_passed": all(gates.values()),
        "hypothesis_checks": hypothesis_checks,
        "secondary_checks": secondary_checks,
        "interpretation": {
            "structural_audit_alone_detected_leak": not mutant_structure.passed,
            "semantic_contract_detected_leak": not mutant_semantics.passed,
            "mutant_internal_equilibrium_is_real_game_certificate": False,
            "generalization_beyond_injected_fault_established": False,
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            **numerical_environment,
        },
        "paid_model_calls": False,
        "limitations": contract["limitations"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    artifact = run_audit(args.contract.resolve())
    args.output.write_text(
        json.dumps(artifact, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "output": str(args.output),
        "primary_passed": artifact["primary_passed"],
        "correct_structural_passed": artifact["correct_adapter"]["structural_audit"]["passed"],
        "mutant_structural_passed": artifact["mutant_adapter"]["structural_audit"]["passed"],
        "correct_semantic_violations": artifact["correct_adapter"]["observation_invariance"]["violations"],
        "mutant_semantic_violations": artifact["mutant_adapter"]["observation_invariance"]["violations"],
    }, indent=2))
    return 0 if artifact["primary_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
