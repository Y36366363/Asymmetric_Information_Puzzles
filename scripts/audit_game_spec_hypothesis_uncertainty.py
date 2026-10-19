#!/usr/bin/env python3
"""Run the frozen GameSpec epistemic-uncertainty experiment."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform

from aip.core import (
    CFRGameProperties,
    FullTreeBestResponseEvaluator,
    GameSpecHypothesis,
    GameSpecObservationSlice,
    ObservationEquivalenceEvidence,
    compile_sequence_form,
    evaluate_game_spec_hypotheses,
    generate_observation_invariance_contract,
    run_independent_evaluation,
    solve_sequence_form,
)
from aip.puzzles.liars_dice import (
    OneDieLiarDiceCFRGame,
    OneDieLiarIndependentEvaluator,
    one_die_observation_records,
    one_die_observation_spec,
    one_die_private_die_invariance_cases,
    solve_one_die_liar_exact,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / (
    "configs/game_spec_hypothesis_uncertainty_preregistration_2026-10-19.json"
)
DEFAULT_OUTPUT = ROOT / (
    "research/results/game_spec_hypothesis_uncertainty_2026-10-19.json"
)
PROPERTIES = CFRGameProperties(2, True, True, True)


class BothDiceVisibleOneDieGame(OneDieLiarDiceCFRGame):
    """Conditional model for the hypothesis that both dice are observed."""

    def information_set(self, state):
        if self.current_player(state) is None or state.dice is None:
            raise ValueError("decision states only")
        return state.dice, state.bids


def _visible_spec() -> GameSpecObservationSlice:
    return GameSpecObservationSlice(
        "one_die_both_dice_visible_v1",
        2,
        ("bids", "die_0", "die_1"),
        ((), ()),
    )


def _hypotheses() -> tuple[GameSpecHypothesis, ...]:
    return (
        GameSpecHypothesis("opponent_die_hidden", one_die_observation_spec(), 0.5),
        GameSpecHypothesis("both_dice_visible", _visible_spec(), 0.5),
    )


def _evidence(index: int, *, same: bool, reliability: float, suffix: str):
    records = {record.state: record for record in one_die_observation_records()}
    case = one_die_private_die_invariance_cases()[index]
    return ObservationEquivalenceEvidence(
        f"manual-reference-{index}-{suffix}",
        records[case.left_state],
        records[case.right_state],
        same,
        reliability,
    )


def _compact_evaluation(report) -> dict[str, object]:
    artifact = report.to_artifact()
    artifact.pop("action_values")
    artifact["action_value_information_sets"] = len(report.action_values)
    return artifact


def _conditional_solutions() -> dict[str, object]:
    _, hidden_solution = solve_one_die_liar_exact()
    hidden_report = run_independent_evaluation(
        OneDieLiarIndependentEvaluator(),
        hidden_solution.policy,
        maximum_exploitability=1e-10,
    )

    visible_game = BothDiceVisibleOneDieGame()
    visible_form = compile_sequence_form(
        visible_game,
        game_properties=PROPERTIES,
        sparse=True,
        maximum_histories=10_000,
        maximum_nonzeros=100_000,
    )
    visible_solution = solve_sequence_form(
        visible_form, backend="scipy_highs", time_limit=30.0
    )
    visible_report = run_independent_evaluation(
        FullTreeBestResponseEvaluator(
            visible_game,
            evaluator_id="one_die_both_dice_visible_conditional_v1",
            maximum_histories=10_000,
        ),
        visible_solution.policy,
        maximum_exploitability=1e-10,
    )
    return {
        "opponent_die_hidden": {
            "value_to_player_0": hidden_solution.value_to_player_0,
            "independent_evaluation": _compact_evaluation(hidden_report),
            "claim_scope": "conditional_on_this_gamespec",
        },
        "both_dice_visible": {
            "value_to_player_0": visible_solution.value_to_player_0,
            "independent_evaluation": _compact_evaluation(visible_report),
            "claim_scope": "conditional_on_this_gamespec",
        },
    }


def _posterior(report, hypothesis_id: str) -> float | None:
    return next(
        result.posterior
        for result in report.results
        if result.hypothesis_id == hypothesis_id
    )


def run_audit(contract_path: Path) -> dict[str, object]:
    raw_contract = contract_path.read_bytes()
    preregistration = json.loads(raw_contract)
    if preregistration["status"] != "frozen_before_implementation":
        raise ValueError("GameSpec uncertainty experiment was not preregistered")

    hypotheses = _hypotheses()
    records = one_die_observation_records()
    contracts = {
        hypothesis.hypothesis_id: generate_observation_invariance_contract(
            hypothesis.observation_spec,
            records,
            require_cases=False,
        ).to_artifact()
        for hypothesis in hypotheses
    }

    no_evidence = evaluate_game_spec_hypotheses(hypotheses, ())
    hard_evidence = evaluate_game_spec_hypotheses(
        hypotheses,
        (_evidence(0, same=True, reliability=1.0, suffix="hard"),),
    )

    soft_evidence = tuple(
        _evidence(
            index,
            same=True,
            reliability=0.75,
            suffix="soft",
        )
        for index in range(8)
    )
    sensitivity = []
    for count in (0, 1, 2, 4, 8):
        report = evaluate_game_spec_hypotheses(
            hypotheses, soft_evidence[:count]
        )
        sensitivity.append(
            {
                "evidence_count": count,
                "hidden_hypothesis_posterior": _posterior(
                    report, "opponent_die_hidden"
                ),
                "status": report.status,
                "semantic_certification_allowed": (
                    report.semantic_certification_allowed
                ),
            }
        )

    soft_contradiction = evaluate_game_spec_hypotheses(
        hypotheses,
        (
            _evidence(0, same=True, reliability=0.9, suffix="soft-same"),
            _evidence(0, same=False, reliability=0.9, suffix="soft-different"),
        ),
    )
    hard_contradiction = evaluate_game_spec_hypotheses(
        hypotheses,
        (
            _evidence(0, same=True, reliability=1.0, suffix="hard-same"),
            _evidence(0, same=False, reliability=1.0, suffix="hard-different"),
        ),
    )
    solutions = _conditional_solutions()

    expected_candidates = {
        item["hypothesis_id"]: item
        for item in preregistration["candidates"]
    }
    expected_curve = preregistration["primary_tests"][
        "probabilistic_sensitivity"
    ]["expected_hidden_posteriors"]
    gates = {
        "no_evidence_remains_unresolved": (
            no_evidence.status == "unresolved"
            and tuple(result.posterior for result in no_evidence.results)
            == (0.5, 0.5)
        ),
        "candidate_contract_counts_match": all(
            contracts[hypothesis_id]["cases"]
            == expected["expected_observation_contract_cases"]
            for hypothesis_id, expected in expected_candidates.items()
        ),
        "hard_reference_identifies_hidden_hypothesis": (
            hard_evidence.status == "identified"
            and hard_evidence.selected_hypothesis_id == "opponent_die_hidden"
            and hard_evidence.semantic_certification_allowed
        ),
        "probabilistic_curve_matches": all(
            abs(item["hidden_hypothesis_posterior"] - expected) < 1e-12
            for item, expected in zip(sensitivity, expected_curve)
        ),
        "soft_posterior_never_semantically_certifies": all(
            not item["semantic_certification_allowed"]
            for item in sensitivity
        ),
        "balanced_soft_contradiction_is_unresolved": (
            soft_contradiction.status == "unresolved"
            and soft_contradiction.conflicting_evidence_pairs == 1
            and tuple(
                result.posterior for result in soft_contradiction.results
            )
            == (0.5, 0.5)
        ),
        "hard_contradiction_fails_closed": (
            hard_contradiction.status == "conflicted"
            and not hard_contradiction.hard_compatible_hypotheses
        ),
        "conditional_values_match": all(
            abs(
                solutions[hypothesis_id]["value_to_player_0"]
                - expected["expected_internal_game_value_player_0"]
            )
            < 1e-10
            for hypothesis_id, expected in expected_candidates.items()
        ),
        "both_conditional_solutions_pass_internal_br": all(
            solution["independent_evaluation"]["passed"]
            for solution in solutions.values()
        ),
        "runtime_epsilon_gto_remains_disabled": not preregistration[
            "certification_policy"
        ]["runtime_epsilon_gto_allowed"],
    }

    return {
        "schema_version": "aip-gamespec-hypothesis-uncertainty-v1",
        "experiment_id": preregistration["experiment_id"],
        "date": "2026-10-19",
        "preregistration": str(contract_path.relative_to(ROOT)),
        "preregistration_sha256": sha256(raw_contract).hexdigest(),
        "preregistration_commit": "c4ae3ff",
        "conceptual_separation": preregistration["conceptual_separation"],
        "candidate_contracts": contracts,
        "no_evidence": no_evidence.to_artifact(),
        "hard_reference_evidence": hard_evidence.to_artifact(),
        "probabilistic_sensitivity": {
            "conditional_independence_assumption": True,
            "curve": sensitivity,
            "calibration_established": False,
        },
        "balanced_soft_contradiction": soft_contradiction.to_artifact(),
        "hard_contradiction": hard_contradiction.to_artifact(),
        "conditional_solutions": solutions,
        "primary_gates": gates,
        "primary_passed": all(gates.values()),
        "promotion": {
            "llm_pilot_executed": False,
            "llm_pilot_design_allowed_after_human_review": True,
            "runtime_epsilon_gto_allowed": False,
            "adaptive_opponent_line_released": False,
        },
        "interpretation": {
            "prior_is_nature_probability": False,
            "posterior_identification_is_semantic_proof": False,
            "conditional_solutions_may_be_averaged_as_one_gto": False,
            "true_gamespec_guaranteed_in_candidate_set": False,
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "paid_model_calls": False,
        "limitations": [
            "The true one-die information structure is already known; this is a falsification control, not discovery on an unknown game.",
            "The 0.75 and 0.9 evidence reliabilities are frozen sensitivity parameters, not empirically calibrated source accuracies.",
            "Repeated likelihood updates assume conditional independence and must not be used for duplicated reports from one source.",
            "If the true GameSpec is absent from the candidate set, posterior concentration can still select a wrong candidate.",
            "No LLM authored a GameSpec in this experiment.",
        ],
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
    print(
        json.dumps(
            {
                "output": str(args.output),
                "primary_passed": artifact["primary_passed"],
                "no_evidence_status": artifact["no_evidence"]["status"],
                "hard_evidence_selected": artifact["hard_reference_evidence"]
                ["selected_hypothesis_id"],
                "runtime_epsilon_gto_allowed": artifact["promotion"]
                ["runtime_epsilon_gto_allowed"],
            },
            indent=2,
        )
    )
    return 0 if artifact["primary_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
