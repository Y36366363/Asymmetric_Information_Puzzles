#!/usr/bin/env python3
"""Replay offline smoke gates; never dispatch provider requests."""
from __future__ import annotations

import argparse
from hashlib import sha256
from itertools import product
import json
from pathlib import Path

from aip.core.game_spec_pilot import (
    GameSpecVocabulary, compile_game_spec_candidate_json, score_pilot_case,
)
from aip.core.game_spec_smoke import (
    compile_field_contrast_suite, evaluate_smoke_gates, validate_scope_refusal,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "configs/llm_gamespec_smoke_execution_2026-10-21.json"


def compile_partition(case, owners):
    return compile_game_spec_candidate_json({
        "schema_version": "aip-observation-gamespec-candidates-v1",
        "game_id": case["case_id"],
        "candidates": [{
            "hypothesis_id": "candidate",
            "public_fields": [f for f, owner in owners.items() if owner == "public"],
            "private_fields_by_player": {
                f"player_{p}": [f for f, owner in owners.items() if owner == f"player_{p}"]
                for p in range(2)
            },
        }],
    }, GameSpecVocabulary(case["case_id"], 2, tuple(case["fields"])))


def run():
    raw = MANIFEST.read_bytes()
    manifest = json.loads(raw)
    exhaustive = []
    for case in manifest["cases"]:
        vocab = GameSpecVocabulary(case["case_id"], 2, tuple(case["fields"]))
        evidence = compile_field_contrast_suite(vocab, case["reference_owners"])
        reference = compile_partition(case, case["reference_owners"])
        false_certifications = 0
        correct_certifications = 0
        for owners in product(("public", "player_0", "player_1"), repeat=len(vocab.fields)):
            candidates = compile_partition(case, dict(zip(vocab.fields, owners)))
            score = score_pilot_case(
                arm_id="offline_partition_enumeration", candidate_set=candidates,
                trusted_reference=reference.hypotheses[0].observation_spec,
                vocabulary=vocab, evidence=evidence,
                required_evidence_ids=tuple(e.evidence.evidence_id for e in evidence),
                repair_count=0, conditional_solver_succeeded=None,
            )
            false_certifications += int(score.false_certification)
            correct_certifications += int(score.certified_reference_model)
        exhaustive.append({
            "case_id": case["case_id"], "partitions_tested": 3 ** len(vocab.fields),
            "field_player_contrasts": len(evidence),
            "correct_partitions_verified": correct_certifications,
            "false_certifications": false_certifications,
        })
    good = {
        "schema_by_arm": {arm: {"valid": 18, "total": 20}
                          for arm in manifest["schedule"]["arm_order"]},
        "repairs_executable": 10, "repair_probes": 12,
        "correct_oos": 15, "oos_trials": 15,
        "closed_set_correct": 6, "closed_set_trials": 6,
        "human_verified": 4, "human_cases": 4,
        "call_costs_usd": [0.008] * 185, "usage_complete": True,
        "false_certifications": 0,
    }
    scope = manifest["out_of_schema"]
    refusal = {
        "schema_version": "aip-observation-refusal-v1",
        "game_id": scope["case_id"], "status": "out_of_schema",
        "error_code": scope["expected_code"], "witness": scope["required_witness"],
    }
    examples = {
        "passing_boundary_fixture": evaluate_smoke_gates(manifest, good),
        "repair_below_boundary": evaluate_smoke_gates(manifest, {**good, "repairs_executable": 9}),
        "empty_fixture": evaluate_smoke_gates(manifest, {}),
        "false_certificate_fixture": evaluate_smoke_gates(manifest, {**good, "false_certifications": 1}),
        "cost_overrun_fixture": evaluate_smoke_gates(manifest, {**good, "call_costs_usd": [0.011]}),
        "correct_scope_refusal": validate_scope_refusal(refusal, scope),
        "refusal_on_supported_control": validate_scope_refusal(refusal, None),
    }
    model = manifest["model"]
    reserved_cost = (
        model["maximum_input_tokens"] * model["input_usd_per_million"]
        + model["maximum_output_tokens"] * model["output_usd_per_million"]
    ) / 1e6
    passed = (
        all(row["correct_partitions_verified"] == 1 and row["false_certifications"] == 0
            for row in exhaustive)
        and examples["passing_boundary_fixture"]["status"] == "pass"
        and examples["repair_below_boundary"]["status"] == "fail"
        and examples["empty_fixture"]["status"] == "insufficient_evidence"
        and examples["false_certificate_fixture"]["status"] == "fail"
        and examples["cost_overrun_fixture"]["status"] == "fail"
        and examples["correct_scope_refusal"]["passed"]
        and not examples["refusal_on_supported_control"]["passed"]
        and reserved_cost <= manifest["gates"]["maximum_call_usd"]
        and reserved_cost * manifest["schedule"]["maximum_calls"] <= manifest["gates"]["maximum_total_usd"]
    )
    return {
        "experiment_id": "gamespec_smoke_manifest_preflight_2026-10-21",
        "manifest_sha256": sha256(raw).hexdigest(), "manifest_commit": "8bcc4d5",
        "offline_preflight_passed": passed,
        "exhaustive_finite_partition_checks": exhaustive,
        "boundary_fixture_results": examples,
        "reserved_maximum_call_usd": reserved_cost,
        "reserved_maximum_run_usd": reserved_cost * manifest["schedule"]["maximum_calls"],
        "provider_calls_executed": 0, "model_smoke_gate_status": "not_run",
        "formal_trial_allowed": False,
        "limitations": [
            "Reference owners are authored rule assumptions; field contrasts do not independently prove those assumptions.",
            "Field counterfactuals test the schema vocabulary, not reachable states of a full game tree.",
            "All gate observations in this artifact are deterministic fixtures, not model performance.",
            "Prompt, model, rules, quotas and thresholds are frozen; a provider runner and separate feedback/final evidence artifacts still require preflight before real calls.",
            "Smoke templates are public engineering controls, not future confirmatory held-out games.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "research/results/gamespec_smoke_manifest_preflight_2026-10-21.json")
    args = parser.parse_args()
    result = run()
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps({"offline_preflight_passed": result["offline_preflight_passed"],
                      "provider_calls_executed": 0}))
    raise SystemExit(0 if result["offline_preflight_passed"] else 1)
