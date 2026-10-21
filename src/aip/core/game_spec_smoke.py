"""Offline checks for the frozen quantitative observation smoke contract."""

from __future__ import annotations

from math import isfinite

from aip.core.game_spec import ObservationStateRecord
from aip.core.game_spec_pilot import (
    EvidenceSourcePolicy, GameSpecVocabulary, compile_trusted_evidence_json,
)


def compile_field_contrast_suite(vocabulary, owners):
    """Encode reviewed per-player visibility as one-field counterfactuals.

    Owners are trusted evaluator inputs derived from the authored rule reference,
    never inferred from candidate output. This checks a finite visibility slice;
    it does not validate the natural-language reference itself.
    """
    if not isinstance(vocabulary, GameSpecVocabulary):
        raise ValueError("an evaluator vocabulary is required")
    if set(owners) != set(vocabulary.fields) or any(
        owner not in ("public", "player_0", "player_1")
        for owner in owners.values()
    ):
        raise ValueError("reference owners must cover the vocabulary")
    source = EvidenceSourcePolicy(
        "reviewed_rule_reference", "independent_reference", 1.0,
        "reviewed_rule_reference", True,
    )
    suite = []
    for player in range(2):
        for field in vocabulary.fields:
            left_fields = {name: 0 for name in vocabulary.fields}
            right_fields = {**left_fields, field: 1}
            worlds = {
                "left": ObservationStateRecord.from_mapping(
                    (player, field, 0), player, left_fields
                ),
                "right": ObservationStateRecord.from_mapping(
                    (player, field, 1), player, right_fields
                ),
            }
            payload = {
                "schema_version": "aip-observation-evidence-v1",
                "evidence_id": f"p{player}_{field}",
                "source_id": source.source_id,
                "left_world_id": "left", "right_world_id": "right",
                "acting_player": player,
                "observed_same": owners[field] not in ("public", f"player_{player}"),
            }
            suite.append(compile_trusted_evidence_json(
                payload, sources={source.source_id: source}, worlds=worlds
            ))
    return tuple(suite)


def validate_scope_refusal(payload, control):
    """Validate a model refusal against the evaluator's specific scope witness.

    A supported rule instance must have control=None. Generic or unrelated
    refusals fail; a scope checker finding an unsupported rule is reported
    separately from a model correctly explaining that limitation.
    """
    if control is None:
        return {"passed": False, "error_code": "INCORRECT_OOS_REFUSAL"}
    expected_keys = {
        "schema_version", "game_id", "status", "error_code", "witness"
    }
    if not isinstance(payload, dict) or set(payload) != expected_keys:
        return {"passed": False, "error_code": "INVALID_REFUSAL_SCHEMA"}
    witness = payload["witness"]
    if (
        payload["schema_version"] != "aip-observation-refusal-v1"
        or payload["game_id"] != control["case_id"]
        or payload["status"] != "out_of_schema"
        or payload["error_code"] != control["expected_code"]
        or not isinstance(witness, dict)
        or set(witness) != set(control["required_witness"])
        or type(witness.get("player")) is not int
        or type(witness.get("before_visible")) is not bool
        or type(witness.get("after_visible")) is not bool
        or witness != control["required_witness"]
    ):
        return {"passed": False, "error_code": "INVALID_SCOPE_WITNESS"}
    return {"passed": True, "error_code": control["expected_code"]}


def evaluate_smoke_gates(manifest, observations):
    """Evaluate frozen counts without treating empty samples as successes.

    observations is an evaluator-produced summary, not accepted model output.
    Every call must carry usage and a conservative uncached cost estimate.
    """
    gates = manifest["gates"]
    checks = {}
    insufficient = False

    def count_gate(name, successes, total, expected, minimum):
        nonlocal insufficient
        if type(total) is not int or type(successes) is not int:
            raise ValueError("smoke counts must be integers")
        if total < 0 or successes < 0 or successes > total:
            raise ValueError("invalid smoke counts")
        if total < expected:
            insufficient = True
        checks[name] = total == expected and successes >= minimum

    for arm in manifest["schedule"]["arm_order"]:
        result = observations.get("schema_by_arm", {}).get(arm, {})
        count_gate(
            f"schema_{arm}", result.get("valid", 0), result.get("total", 0),
            gates["schema_denominator_per_arm"],
            gates["schema_minimum_valid_per_arm"],
        )
    count_gate(
        "repair_executable", observations.get("repairs_executable", 0),
        observations.get("repair_probes", 0), gates["repair_probe_denominator"],
        gates["repair_probe_minimum_executable"],
    )
    count_gate(
        "out_of_schema", observations.get("correct_oos", 0),
        observations.get("oos_trials", 0), gates["out_of_schema_denominator"],
        gates["correct_out_of_schema_rejections_required"],
    )
    count_gate(
        "missing_truth_control", observations.get("closed_set_correct", 0),
        observations.get("closed_set_trials", 0),
        manifest["schedule"]["missing_truth_control_initial_trials"],
        manifest["schedule"]["missing_truth_control_initial_trials"],
    )
    count_gate(
        "human_reference", observations.get("human_verified", 0),
        observations.get("human_cases", 0), len(manifest["cases"]),
        len(manifest["cases"]),
    )
    costs = observations.get("call_costs_usd", [])
    if any(
        isinstance(cost, bool) or not isinstance(cost, (float, int))
        or not isfinite(cost) or cost < 0 for cost in costs
    ):
        raise ValueError("call costs must be finite nonnegative numbers")
    if not costs:
        insufficient = True
    checks["cost"] = bool(costs) and (
        len(costs) <= manifest["schedule"]["maximum_calls"]
        and max(costs) <= gates["maximum_call_usd"]
        and sum(costs) <= gates["maximum_total_usd"]
        and observations.get("usage_complete") is True
    )
    false_certifications = observations.get("false_certifications")
    if false_certifications is None:
        insufficient = True
    elif type(false_certifications) is not int or false_certifications < 0:
        raise ValueError("false certification count must be a nonnegative integer")
    checks["false_certifications"] = false_certifications == 0
    return {
        "status": "insufficient_evidence" if insufficient else (
            "pass" if all(checks.values()) else "fail"
        ),
        "checks": checks,
        "formal_trial_execution_allowed": False,
        "runtime_epsilon_gto_allowed": False,
    }
