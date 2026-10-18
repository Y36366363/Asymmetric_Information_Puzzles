#!/usr/bin/env python3
"""Run the frozen cross-game GameSpec observation-slice experiment."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform

from aip.core import audit_observation_invariance, audit_small_extensive_form
from aip.puzzles.goofspiel import (
    GoofspielCommitmentGame,
    generated_goofspiel_observation_contract,
)
from aip.puzzles.liars_dice import (
    OneDieLiarDiceCFRGame,
    generated_one_die_observation_contract,
    one_die_private_die_invariance_cases,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = (
    ROOT / "configs/game_spec_observation_slice_preregistration_2026-10-17.json"
)
DEFAULT_OUTPUT = (
    ROOT / "research/results/game_spec_observation_slice_2026-10-17.json"
)


class OpponentDieLeakingOneDieGame(OneDieLiarDiceCFRGame):
    def information_set(self, state):
        if self.current_player(state) is None or state.dice is None:
            raise ValueError("decision states only")
        return state.dice, state.bids


def _first_pair_mismatch(generated, reference):
    for index, (left, right) in enumerate(zip(generated, reference)):
        generated_pair = (left.left_state, left.right_state)
        reference_pair = (right.left_state, right.right_state)
        if generated_pair != reference_pair:
            return {
                "index": index,
                "generated": [repr(value) for value in generated_pair],
                "reference": [repr(value) for value in reference_pair],
            }
    if len(generated) != len(reference):
        return {
            "index": min(len(generated), len(reference)),
            "generated_length": len(generated),
            "reference_length": len(reference),
        }
    return None


def run_audit(contract_path: Path) -> dict[str, object]:
    raw_contract = contract_path.read_bytes()
    preregistration = json.loads(raw_contract)
    if preregistration["status"] != "frozen_before_implementation":
        raise ValueError("GameSpec experiment was not frozen before implementation")

    one_die = generated_one_die_observation_contract()
    manual_reference = one_die_private_die_invariance_cases()
    mismatch = _first_pair_mismatch(one_die.cases, manual_reference)
    one_die_exact = mismatch is None

    one_die_correct = audit_observation_invariance(
        OneDieLiarDiceCFRGame(), one_die.cases
    )
    one_die_leak = audit_observation_invariance(
        OpponentDieLeakingOneDieGame(), one_die.cases
    )

    # The preregistered stop rule prevents interpreting or executing the
    # cross-game transfer if the generated source-game contract is not exact.
    goofspiel: dict[str, object] | None = None
    if one_die_exact:
        generated_goofspiel = generated_goofspiel_observation_contract()
        correct_game = GoofspielCommitmentGame()
        leaking_game = GoofspielCommitmentGame(
            leak_player_0_commitment=True
        )
        goofspiel = {
            "generated_contract": generated_goofspiel.to_artifact(),
            "correct_adapter": {
                "structural_audit": audit_small_extensive_form(
                    correct_game
                ).to_artifact(),
                "observation_invariance": audit_observation_invariance(
                    correct_game, generated_goofspiel.cases
                ).to_artifact(),
            },
            "mutant_adapter": {
                "mutation": "player_1_information_set_includes_pending_player_0_card",
                "structural_audit": audit_small_extensive_form(
                    leaking_game
                ).to_artifact(),
                "observation_invariance": audit_observation_invariance(
                    leaking_game, generated_goofspiel.cases
                ).to_artifact(),
            },
        }

    expected_one_die = preregistration["one_die_reference_gate"]
    expected_goofspiel = preregistration["goofspiel_transfer_gate"]
    gates = {
        "one_die_pair_sequence_exactly_matches_manual_reference": one_die_exact,
        "one_die_record_count_matches": one_die.records
        == expected_one_die["expected_decision_records"],
        "one_die_pair_count_matches": len(one_die.cases)
        == expected_one_die["expected_generated_pairs"],
        "one_die_correct_adapter_has_zero_violations": one_die_correct.violations
        == expected_one_die["correct_adapter_expected_violations"],
        "one_die_leak_has_expected_information_set_violations": (
            one_die_leak.violations
            == expected_one_die["leaking_adapter_expected_violations"]
            and dict(one_die_leak.violations_by_component)
            == {
                "information_set": expected_one_die[
                    "leaking_adapter_expected_violations"
                ]
            }
        ),
        "goofspiel_transfer_was_reached": goofspiel is not None,
        "goofspiel_record_count_matches": bool(
            goofspiel
            and goofspiel["generated_contract"]["records"]
            == expected_goofspiel["expected_decision_records"]
        ),
        "goofspiel_pair_count_matches": bool(
            goofspiel
            and goofspiel["generated_contract"]["cases"]
            == expected_goofspiel["expected_generated_pairs"]
        ),
        "goofspiel_correct_adapter_has_zero_violations": bool(
            goofspiel
            and goofspiel["correct_adapter"]["observation_invariance"][
                "violations"
            ]
            == expected_goofspiel["correct_adapter_expected_violations"]
        ),
        "goofspiel_leak_is_structurally_valid": bool(
            goofspiel
            and goofspiel["mutant_adapter"]["structural_audit"]["passed"]
        ),
        "goofspiel_leak_has_expected_information_set_violations": bool(
            goofspiel
            and goofspiel["mutant_adapter"]["observation_invariance"][
                "violations"
            ]
            == expected_goofspiel["leaking_adapter_expected_violations"]
            and goofspiel["mutant_adapter"]["observation_invariance"][
                "violations_by_component"
            ]
            == {
                "information_set": expected_goofspiel[
                    "leaking_adapter_expected_violations"
                ]
            }
        ),
    }

    return {
        "schema_version": "aip-game-spec-observation-slice-v1",
        "experiment_id": preregistration["experiment_id"],
        "date": "2026-10-17",
        "preregistration": str(contract_path.relative_to(ROOT)),
        "preregistration_sha256": sha256(raw_contract).hexdigest(),
        "preregistration_commit": "16aa32a",
        "one_die_reference_reproduction": {
            "generated_contract": one_die.to_artifact(),
            "manual_reference_cases": len(manual_reference),
            "exact_ordered_state_pair_match": one_die_exact,
            "first_mismatch": mismatch,
            "correct_adapter": one_die_correct.to_artifact(),
            "mutant_adapter": one_die_leak.to_artifact(),
        },
        "goofspiel_transfer": goofspiel,
        "primary_gates": gates,
        "primary_passed": all(gates.values()),
        "interpretation": {
            "same_generator_used_for_both_games": True,
            "candidate_information_sets_used_to_generate_pairs": False,
            "full_goofspiel_gto_certified_by_this_experiment": False,
            "llm_game_spec_generation_tested": False,
            "adaptive_opponent_learning_ready": False,
            "next_stage_allowed": "design_llm_pilot_only_after_human_review",
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "paid_model_calls": False,
        "limitations": [
            "Both GameSpec declarations were authored and reviewed manually.",
            "The Goofspiel adapter is a hidden-commitment semantic slice, not a replacement for the existing full exact dynamic solver.",
            "Passing injected faults does not estimate false-negative rates on natural LLM-generated game models.",
            "Observation-field validity is established only for the declared fields and enumerated finite records.",
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
                "one_die_exact": artifact["one_die_reference_reproduction"][
                    "exact_ordered_state_pair_match"
                ],
                "goofspiel_transfer_reached": artifact["goofspiel_transfer"]
                is not None,
            },
            indent=2,
        )
    )
    return 0 if artifact["primary_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
