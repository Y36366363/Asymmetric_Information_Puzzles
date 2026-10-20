#!/usr/bin/env python3
"""Offline dry run for the frozen LLM GameSpec pilot protocol."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform

from aip.core import (
    EvidenceSourcePolicy,
    GameSpecVocabulary,
    compile_game_spec_candidate_json,
    compile_trusted_evidence_json,
    score_pilot_case,
)
from aip.puzzles.liars_dice import (
    one_die_observation_records,
    one_die_observation_spec,
    one_die_private_die_invariance_cases,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL = (
    ROOT / "configs/llm_gamespec_pilot_protocol_preregistration_2026-10-20.json"
)
DEFAULT_OUTPUT = (
    ROOT / "research/results/llm_gamespec_pilot_protocol_dry_run_2026-10-20.json"
)
SCHEMA = "aip-observation-gamespec-candidates-v1"


def _candidate(hypothesis_id, public, player_0, player_1):
    return {
        "hypothesis_id": hypothesis_id,
        "public_fields": list(public),
        "private_fields_by_player": {
            "player_0": list(player_0),
            "player_1": list(player_1),
        },
    }


HIDDEN = _candidate("hidden", ("bids",), ("die_0",), ("die_1",))
VISIBLE = _candidate("visible", ("bids", "die_0", "die_1"), (), ())
SWAPPED = _candidate("swapped", ("bids",), ("die_1",), ("die_0",))


def _payload(*candidates):
    return {
        "schema_version": SCHEMA,
        "game_id": "one_die_liar",
        "candidates": list(candidates),
    }


def run_audit(protocol_path: Path) -> dict[str, object]:
    raw_protocol = protocol_path.read_bytes()
    protocol = json.loads(raw_protocol)
    if protocol["status"] != "frozen_design_before_compiler_and_model_calls":
        raise ValueError("LLM GameSpec pilot protocol was not frozen before work")
    if protocol["scope"]["paid_model_calls_in_this_phase"]:
        raise ValueError("offline dry run may not enable provider calls")

    vocabulary = GameSpecVocabulary(
        "one_die_liar", 2, ("bids", "die_0", "die_1")
    )
    records = {record.state: record for record in one_die_observation_records()}
    reference_case = one_die_private_die_invariance_cases()[0]
    worlds = {
        "left": records[reference_case.left_state],
        "right": records[reference_case.right_state],
    }
    source = EvidenceSourcePolicy(
        "manual_reference",
        "independent_reference",
        1.0,
        "one_die_manual_contract_v1",
        True,
    )
    evidence_payload = {
        "schema_version": "aip-observation-evidence-v1",
        "evidence_id": "hidden_die_pair_0000",
        "source_id": "manual_reference",
        "left_world_id": "left",
        "right_world_id": "right",
        "acting_player": 0,
        "observed_same": True,
    }
    evidence = compile_trusted_evidence_json(
        evidence_payload,
        sources={source.source_id: source},
        worlds=worlds,
    )

    fixtures = {
        "single_no_feedback": (_payload(VISIBLE), 1, 0),
        "multi_structural_feedback": (_payload(VISIBLE, HIDDEN, SWAPPED), 3, 1),
        "multi_semantic_feedback": (_payload(SWAPPED, VISIBLE, HIDDEN), 3, 1),
        "human_reference_ceiling": (_payload(HIDDEN), 1, 0),
    }
    scores = {}
    for arm_id, (candidate_payload, exact_count, repairs) in fixtures.items():
        candidate_set = compile_game_spec_candidate_json(
            candidate_payload,
            vocabulary,
            exact_candidates=exact_count,
        )
        scores[arm_id] = score_pilot_case(
            arm_id=arm_id,
            candidate_set=candidate_set,
            trusted_reference=one_die_observation_spec(),
            vocabulary=vocabulary,
            evidence=(evidence,),
            required_evidence_ids=("hidden_die_pair_0000",),
            repair_count=repairs,
            conditional_solver_succeeded=None,
        ).to_artifact()

    absent_set = compile_game_spec_candidate_json(
        _payload(VISIBLE, SWAPPED),
        vocabulary,
        exact_candidates=2,
    )
    closed_set = score_pilot_case(
        arm_id="true_model_absent_negative_control",
        candidate_set=absent_set,
        trusted_reference=one_die_observation_spec(),
        vocabulary=vocabulary,
        evidence=(evidence,),
        required_evidence_ids=("hidden_die_pair_0000",),
        repair_count=0,
        conditional_solver_succeeded=None,
    ).to_artifact()

    forbidden_output_checks = {}
    for key, value in (
        ("prior", 0.99),
        ("posterior", 0.99),
        ("evidence_reliability", 1.0),
        ("certified", True),
    ):
        invalid = dict(HIDDEN)
        invalid[key] = value
        try:
            compile_game_spec_candidate_json(
                _payload(invalid), vocabulary, exact_candidates=1
            )
        except ValueError:
            forbidden_output_checks[key] = True
        else:
            forbidden_output_checks[key] = False

    llm_scores = [
        scores[arm_id]
        for arm_id in (
            "single_no_feedback",
            "multi_structural_feedback",
            "multi_semantic_feedback",
        )
    ]
    dry_run_endpoints = {
        "true_model_candidate_coverage_rate": sum(
            score["true_model_candidate_coverage"] for score in llm_scores
        ) / len(llm_scores),
        "false_certification_rate": sum(
            score["false_certification"] for score in llm_scores
        ) / len(llm_scores),
        "interpretation": "deterministic fixture plumbing only; not an LLM estimate",
    }

    expected = protocol["offline_dry_run"]
    gates = {
        "single_wrong_candidate_not_covered": (
            scores["single_no_feedback"]["true_model_candidate_coverage"]
            == expected["expected_single_wrong_candidate_coverage"]
        ),
        "multi_candidate_sets_cover_reference": (
            scores["multi_structural_feedback"]["true_model_candidate_coverage"]
            == expected["expected_multi_candidate_coverage"]
            and scores["multi_semantic_feedback"]["true_model_candidate_coverage"]
            == expected["expected_multi_candidate_coverage"]
        ),
        "semantic_arm_verifies_reference": (
            scores["multi_semantic_feedback"]["verification"]["certified"]
            == expected["expected_semantic_feedback_verified"]
        ),
        "human_ceiling_verifies_reference": (
            scores["human_reference_ceiling"]["verification"]["certified"]
            == expected["expected_human_reference_verified"]
        ),
        "true_model_absent_fails_closed": (
            closed_set["verification"]["status"]
            == expected["expected_closed_set_status"]
            and closed_set["false_certification"]
            == expected["expected_closed_set_false_certification"]
        ),
        "model_confidence_and_certification_fields_rejected": all(
            forbidden_output_checks.values()
        ),
        "evidence_reliability_is_evaluator_owned": (
            evidence.to_artifact()["reliability_from_registry"] == 1.0
        ),
        "no_model_calls_executed": True,
        "runtime_epsilon_gto_remains_disabled": not protocol[
            "certification_policy"
        ]["runtime_epsilon_gto_allowed"],
    }

    return {
        "schema_version": "aip-llm-gamespec-pilot-dry-run-v1",
        "protocol_id": protocol["protocol_id"],
        "date": "2026-10-20",
        "preregistration": str(protocol_path.relative_to(ROOT)),
        "preregistration_sha256": sha256(raw_protocol).hexdigest(),
        "preregistration_commit": "11cb251",
        "restricted_schema": protocol["restricted_candidate_json"],
        "trusted_evidence_format": protocol["trusted_evidence_json"],
        "trusted_evidence": evidence.to_artifact(),
        "arm_fixture_scores": scores,
        "true_model_absent_negative_control": closed_set,
        "forbidden_model_output_checks": forbidden_output_checks,
        "dry_run_endpoint_plumbing": dry_run_endpoints,
        "primary_gates": gates,
        "primary_passed": all(gates.values()),
        "execution_readiness": {
            "restricted_json_compiler_ready": True,
            "trusted_evidence_registry_ready": True,
            "endpoint_scoring_ready": True,
            "execution_manifest_committed": False,
            "model_id_frozen": False,
            "held_out_rule_set_frozen": False,
            "provider_calls_allowed": False,
        },
        "promotion": {
            "llm_effect_established": False,
            "runtime_epsilon_gto_allowed": False,
            "adaptive_opponent_line_released": False,
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "paid_model_calls": False,
        "limitations": [
            "All arm outputs are deterministic fixtures, not LLM generations.",
            "The dry-run endpoint values are plumbing checks and must not be reported as model performance.",
            "Only observation visibility is represented; chance, payoff, transitions, and terminal semantics remain outside this schema.",
            "The single one-die witness distinguishes the frozen fixture candidates but is not a general completeness proof.",
            "A future execution manifest must freeze model id, trials, prompts, rule instances, and hidden references before provider calls.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    artifact = run_audit(args.protocol.resolve())
    args.output.write_text(
        json.dumps(artifact, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "output": str(args.output),
        "primary_passed": artifact["primary_passed"],
        "provider_calls_allowed": artifact["execution_readiness"]
        ["provider_calls_allowed"],
        "llm_effect_established": artifact["promotion"]["llm_effect_established"],
    }, indent=2))
    return 0 if artifact["primary_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
