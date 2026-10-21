import copy
import itertools
import json
from pathlib import Path

import pytest

from aip.core.game_spec_pilot import (
    EvidenceSourcePolicy, GameSpecVocabulary,
    compile_game_spec_candidate_json, score_pilot_case,
)
from aip.core.game_spec import GameSpecObservationSlice
from aip.core.game_spec_smoke import (
    compile_field_contrast_suite, evaluate_smoke_gates, validate_scope_refusal,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "configs/llm_gamespec_smoke_execution_2026-10-21.json").read_text())


def compile_owners(case_id, fields, owners):
    return compile_game_spec_candidate_json({
        "schema_version": "aip-observation-gamespec-candidates-v1",
        "game_id": case_id,
        "candidates": [{
            "hypothesis_id": "candidate",
            "public_fields": [f for f, o in owners.items() if o == "public"],
            "private_fields_by_player": {
                f"player_{p}": [f for f, o in owners.items() if o == f"player_{p}"]
                for p in range(2)
            },
        }],
    }, GameSpecVocabulary(case_id, 2, tuple(fields)))


def passing_counts():
    return {
        "schema_by_arm": {arm: {"valid": 18, "total": 20}
                          for arm in MANIFEST["schedule"]["arm_order"]},
        "repairs_executable": 10, "repair_probes": 12,
        "correct_oos": 15, "oos_trials": 15,
        "closed_set_correct": 6, "closed_set_trials": 6,
        "human_verified": 4, "human_cases": 4,
        "call_costs_usd": [0.008] * 185, "usage_complete": True,
        "false_certifications": 0,
    }


@pytest.mark.parametrize("case", MANIFEST["cases"], ids=lambda c: c["case_id"])
def test_full_field_suite_uniquely_recovers_reviewed_partition(case):
    vocabulary = GameSpecVocabulary(case["case_id"], 2, tuple(case["fields"]))
    evidence = compile_field_contrast_suite(vocabulary, case["reference_owners"])
    reference = compile_owners(case["case_id"], case["fields"], case["reference_owners"])
    certified = []
    for ownership in itertools.product(("public", "player_0", "player_1"), repeat=3):
        owners = dict(zip(case["fields"], ownership))
        compiled = compile_owners(case["case_id"], case["fields"], owners)
        score = score_pilot_case(
            arm_id="offline_exhaustive_control", candidate_set=compiled,
            trusted_reference=reference.hypotheses[0].observation_spec,
            vocabulary=vocabulary, evidence=evidence,
            required_evidence_ids=tuple(e.evidence.evidence_id for e in evidence),
            repair_count=0, conditional_solver_succeeded=None,
        )
        assert not score.false_certification
        if score.verification.certified:
            certified.append(owners)
    assert certified == [case["reference_owners"]]


def test_schema_and_feedback_boundary_counts():
    good = passing_counts()
    assert evaluate_smoke_gates(MANIFEST, good)["status"] == "pass"
    for key, value in (("repairs_executable", 9), ("correct_oos", 14),
                       ("false_certifications", 1), ("usage_complete", False)):
        bad = {**good, key: value}
        assert evaluate_smoke_gates(MANIFEST, bad)["status"] == "fail"
    bad = copy.deepcopy(good)
    bad["schema_by_arm"]["single_no_feedback"]["valid"] = 17
    assert evaluate_smoke_gates(MANIFEST, bad)["status"] == "fail"
    assert evaluate_smoke_gates(MANIFEST, {})["status"] == "insufficient_evidence"


def test_cost_overrun_and_nonfinite_usage_fail():
    good = passing_counts()
    assert evaluate_smoke_gates(MANIFEST, {**good, "call_costs_usd": [0.011]})["status"] == "fail"
    assert evaluate_smoke_gates(MANIFEST, {**good, "call_costs_usd": [0.008] * 186})["status"] == "fail"
    with pytest.raises(ValueError, match="finite"):
        evaluate_smoke_gates(MANIFEST, {**good, "call_costs_usd": [float("nan")]})


def refusal():
    return {
        "schema_version": "aip-observation-refusal-v1",
        "game_id": "dice_paid_reveal", "status": "out_of_schema",
        "error_code": "OUT_OF_SCHEMA_STATIC_VISIBILITY",
        "witness": copy.deepcopy(MANIFEST["out_of_schema"]["required_witness"]),
    }


def test_scope_refusal_requires_exact_explanation_and_supported_pair_is_rejected():
    assert validate_scope_refusal(refusal(), MANIFEST["out_of_schema"])["passed"]
    assert not validate_scope_refusal(refusal(), None)["passed"]
    bad = refusal()
    bad["witness"]["field"] = "die_1"
    assert not validate_scope_refusal(bad, MANIFEST["out_of_schema"])["passed"]
    bad = refusal()
    bad["witness"]["before_visible"] = 0
    assert not validate_scope_refusal(bad, MANIFEST["out_of_schema"])["passed"]
    assert not validate_scope_refusal("too complex", MANIFEST["out_of_schema"])["passed"]


def test_near_hard_source_cannot_claim_exact_authority():
    with pytest.raises(ValueError, match="hard evidence"):
        EvidenceSourcePolicy("near_hard", "expert_review", 0.9999999999, "review", True)


def test_static_partition_cannot_fit_both_phases_for_same_field():
    # Same raw field, same actor: before a paid reveal is hidden, after is visible.
    # Every allowed static owner yields a constant visibility across both phases.
    reference = (False, True)
    for owner in ("public", "player_0", "player_1"):
        visibility = owner in ("public", "player_1")
        assert (visibility, visibility) != reference
