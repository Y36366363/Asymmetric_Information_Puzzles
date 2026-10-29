"""New authored boundary panel: frozen scoring, multi-change-aware reporting only."""
from collections import Counter
from copy import deepcopy
from itertools import product
import json

from aip.benchmark.gamespec_prospective import change_witnesses, replay, score
from aip.benchmark.gamespec_witness_diagnostic import diagnostic_package


def package(v4_manifest, v4_bundle, spec):
    pairs, schedule = spec["pairs"], spec["schedule"]
    if not pairs or len({p["pair_id"] for p in pairs}) != len(pairs):
        raise ValueError("unique nonempty pair IDs required")
    expected = [p[k] for p in pairs for k in ("static_id", "dynamic_id")]
    order = schedule["scope_case_order"]
    if len(set(expected)) != len(expected) or Counter(order) != Counter(expected):
        raise ValueError("case order must cover each case exactly once")
    if schedule["repeats"] != 2:
        raise ValueError("frozen replay requires exactly two technical repeats")
    if schedule["trials_per_model"] != len(expected) * 2 or schedule["maximum_generation_calls"] != len(expected) * 4:
        raise ValueError("fixed two-model call budget mismatch")
    manifest, bundle = diagnostic_package(v4_manifest, v4_bundle, spec)
    if any(p["task"] != "scope" for p in bundle["plan"]):
        raise ValueError("scope-only plan required")
    return manifest, bundle


def partition_proposal(owners):
    return {"decision": "candidate", "candidates": [{"public_fields": [f for f, o in owners.items() if o == "public"],
        "private_fields_by_player": {p: [f for f, o in owners.items() if o == p] for p in ("player_0", "player_1")}}],
        "witness": None}


def preflight(bundle):
    """Check both unchanged evaluators against exhaustive finite answer matrices."""
    rows = []
    for pair in bundle["pairs"]:
        static, dynamic = (bundle["cases"][pair[k]] for k in ("static_id", "dynamic_id"))
        fields = list(pair["fields"])
        partition_checks = witness_checks = 0
        for xs in product(("public", "player_0", "player_1"), repeat=len(fields)):
            owners = dict(zip(fields, xs))
            text = json.dumps(partition_proposal(owners))
            if score(text, static)["correct"] != (owners == pair["owners"]) or score(text, dynamic)["correct"]:
                raise ValueError("partition preflight counterexample")
            partition_checks += 1
        valid = change_witnesses(pair["dynamic_visibility"])
        for field, player, before, after in product(fields, (0, 1), (False, True), (False, True)):
            witness = dict(field=field, player=player, before_visible=before, after_visible=after)
            text = json.dumps({"decision": "refusal", "candidates": [], "witness": witness})
            if score(text, dynamic)["correct"] != (witness in valid) or score(text, static)["correct"]:
                raise ValueError("witness preflight counterexample")
            witness_checks += 1
        rows.append({"pair_id": pair["pair_id"], "partitions_checked_per_side": partition_checks,
            "witnesses_checked_per_side": witness_checks, "all_valid_changes": valid})
    return {"passed": True, "rows": rows, "main_scorer_changed": False,
            "natural_language_truth_proven": False, "external_or_user_review_completed": False}


def failure_categories(payload, item):
    """Classify against the complete change set; never change pass/fail."""
    if item["kind"] == "static":
        return ["static_false_refusal" if payload["decision"] == "refusal" else "wrong_static_partition"]
    if payload["decision"] != "refusal":
        return ["dynamic_false_acceptance"]
    w, valid = payload["witness"], change_witnesses(item["visibility_contexts"])
    field_changes = [e for e in valid if e["field"] == w["field"]]
    player_changes = [e for e in field_changes if e["player"] == w["player"]]
    categories = []
    if not field_changes:
        categories.append("wrong_changed_field")
    elif not player_changes:
        categories.append("wrong_affected_player")
    else:
        e = player_changes[0]  # Exactly one ordered before/after state per field/player.
        if w["before_visible"] != e["before_visible"]: categories.append("wrong_initial_visibility")
        if w["after_visible"] != e["after_visible"]: categories.append("wrong_final_visibility")
        if (w["before_visible"], w["after_visible"]) == (e["after_visible"], e["before_visible"]):
            categories.append("reversed_change_direction")
    if w["before_visible"] == w["after_visible"]:
        categories.append("no_visibility_change")
    return categories


def analyze(manifest, bundle, report):
    base = replay(manifest, bundle, report)
    trials = {t["trial_id"]: t for t in report["trials"]}
    failures, candidate_counts, witnesses = [], [], []
    for p in bundle["plan"]:
        t = trials.get(p["trial_id"], {})
        item = bundle["cases"][p["case_id"]]
        payload = None
        if t.get("status") == "completed" and t["evaluation"]["serialization_ok"]:
            a = report["attempts"][t["attempt_ids"][0]]
            payload = json.loads(a["raw_response"]["choices"][0]["message"]["content"])
            if payload["decision"] == "candidate":
                candidate_counts.append({"trial_id": p["trial_id"], "candidate_count": len(payload["candidates"])})
            else:
                witnesses.append({"trial_id": p["trial_id"], "witness": deepcopy(payload["witness"]),
                                  "correct": t["evaluation"]["correct"]})
        if t.get("evaluation", {}).get("correct", False):
            continue
        transport_error = bool(set(t.get("evaluation", {}).get("errors", [])) & {"provider_error", "truncated_output"})
        categories = (["incomplete_or_provider_error"] if t.get("status") != "completed" else
                      ["transport_or_truncation"] if transport_error else
                      ["interface_contract_error"] if payload is None else failure_categories(payload, item))
        failures.append({"trial_id": p["trial_id"], "categories": categories,
                         "errors": t.get("evaluation", {}).get("errors", ["incomplete"]),
                         "submitted_proposal": payload,
                         "all_valid_changes": change_witnesses(item["visibility_contexts"])})
    return {"groups": {k: base["groups"][k] for k in ("static", "dynamic")},
        "pairs": [{"pair_id": p["pair_id"], "feature": p["feature"],
                   "all_valid_changes": change_witnesses(p["dynamic_visibility"]),
                   "joint_by_repeat": next(row["joint_by_repeat"] for row in base["pair_results"] if row["pair_id"] == p["pair_id"])}
                  for p in bundle["pairs"]],
        "joint_correct": base["joint_pair_success"], "joint_assigned": base["joint_pair_assigned"],
        "all_failures": failures, "candidate_counts": candidate_counts, "submitted_witnesses": witnesses,
        "cost_usd": base["cost_usd"], "tokens": base["tokens"], "reasoning_tokens": base["reasoning_tokens"],
        "latency_seconds": base["latency_seconds"], "provider_attempts": base["provider_attempts"],
        "false_certifications": base["false_certifications"], "oos_false_acceptances": base["oos_false_acceptances"],
        "authored_pair_count": len(bundle["pairs"]), "independently_sampled_rule_instances": 0,
        "developer_authored_unreviewed_reference": True, "external_review_required_for_development": False,
        "new_panel_not_used_to_tune_frozen_configuration": True, "independent_held_out": False,
        "overall_scientific_pass": None, "overfitting_ruled_out": False,
        "formal_trial_started": False, "deployment_permission": False,
        "adaptive_opponent_line_released": False, "new_runtime_epsilon_gto_allowed": False}
