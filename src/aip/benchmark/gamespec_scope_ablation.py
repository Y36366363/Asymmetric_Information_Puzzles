"""Paired scope/witness interface experiment, separate from frozen v1/v2 runs."""
from collections import Counter
from copy import deepcopy
import json

from aip.benchmark.gamespec_smoke import SmokeRunner, digest, final_score, make_bundle
from aip.benchmark.gamespec_smoke_v2 import compile_v2, materialize_manifest
from aip.core.game_spec_smoke import validate_scope_refusal


def materialize(base, v2, spec):
    manifest = materialize_manifest(base, v2)
    manifest["manifest_id"] = spec["manifest_id"]
    manifest["protocol"] = "paired-scope-witness-ablation-v3"
    manifest["schedule"] = deepcopy(spec["schedule"])
    manifest["gates"] = {k: spec["resource_protection"][k]
                         for k in ("maximum_call_usd", "maximum_total_usd")}
    manifest["ablation"] = deepcopy(spec)
    old_cases = {c["case_id"]: c for c in base["cases"]}
    evidence = make_bundle(base)["cases"]
    cases = {}
    for pair in spec["pairs"]:
        original = old_cases[pair["base_case_id"]]
        static = deepcopy(original)
        static["case_id"] = pair["static_id"]
        materialized = deepcopy(evidence[pair["base_case_id"]])
        materialized["missing_truth_initial"]["game_id"] = static["case_id"]
        cases[static["case_id"]] = {
            "case": static, "kind": "static", "pair_id": pair["pair_id"],
            "evidence": materialized,
        }
        dynamic = {"case_id": pair["dynamic_id"], "fields": deepcopy(original["fields"]),
                   "rules": base["out_of_schema"]["rules"] if pair.get("dynamic_rules_from_base_oos") else pair["dynamic_rules"]}
        cases[dynamic["case_id"]] = {
            "case": dynamic, "kind": "dynamic", "pair_id": pair["pair_id"],
            "control": {"case_id": dynamic["case_id"],
                        "expected_code": "OUT_OF_SCHEMA_STATIC_VISIBILITY",
                        "required_witness": deepcopy(pair["witness"])},
            "additional_witnesses": deepcopy(pair.get("additional_witnesses", [])),
        }
    plan = []
    for task, ordered in (
        ("scope", spec["schedule"]["scope_case_order"]),
        ("witness_repair", [p["static_id"] for p in spec["pairs"]]),
    ):
        for index, case_id in enumerate(ordered):
            for repeat in range(spec["schedule"]["repeats"]):
                arms = spec["arms"]
                shift = (index + repeat) % len(arms)
                for arm in arms[shift:] + arms[:shift]:
                    plan.append({"trial_id": f"{task}:{case_id}:{repeat}:{arm['id']}",
                                 "task": task, "case_id": case_id,
                                 "pair_id": cases[case_id]["pair_id"],
                                 "repeat": repeat, "arm": arm["id"]})
    return manifest, {"version": "gamespec-scope-ablation-v3", "manifest_sha256": digest(manifest),
                      "cases": cases, "plan": plan}


def messages_for(manifest, bundle, trial):
    spec = manifest["ablation"]
    arm = next(a for a in spec["arms"] if a["id"] == trial["arm"])
    materialized = bundle["cases"][trial["case_id"]]
    case = materialized["case"]
    system = spec["scope_first_prompt"] if arm["scope_first"] else manifest["system_prompt"]
    if arm["witness_gloss"]:
        system += spec["witness_gloss_prompt"]
    feedback, previous = {}, None
    if trial["task"] == "witness_repair":
        feedback = {"code": "STRUCTURE_OK", "witnesses": materialized["evidence"]["feedback_evidence"]}
        previous = json.dumps(materialized["evidence"]["missing_truth_initial"], sort_keys=True)
    content = manifest["user_prompt_template"].format(
        case_id=case["case_id"], rules=case["rules"],
        fields_json=json.dumps(case["fields"], sort_keys=True),
        candidate_count="1 to 3", feedback_json=json.dumps(feedback, sort_keys=True))
    messages = [{"role": "system", "content": system}]
    if previous is not None:
        messages.append({"role": "assistant", "content": previous})
    return messages + [{"role": "user", "content": content}]


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def nonfinite(_):
        raise ValueError("nonfinite JSON")
    return json.loads(text, object_pairs_hook=pairs, parse_constant=nonfinite)


def claims_evidence_authority(value):
    if isinstance(value, dict):
        return bool(set(value) & {"reliability", "certified", "posterior", "prior"}) or any(
            claims_evidence_authority(v) for v in value.values())
    if isinstance(value, list):
        return any(claims_evidence_authority(v) for v in value)
    return False


def evaluate_reply(text, materialized, transport_errors=()):
    result = {"correct": False, "candidate_compiles": False, "branch": "invalid",
              "scope_false_acceptance": False, "false_certification": False, "errors": []}
    errors = set(transport_errors)
    try:
        payload = strict_json(text)
    except (ValueError, TypeError):
        result["errors"] = sorted(errors | {"invalid_json"})
        return result
    if not isinstance(payload, dict):
        result["errors"] = sorted(errors | {"invalid_schema"})
        return result
    candidate = "candidates" in payload
    refusal = payload.get("status") == "out_of_schema" or payload.get("schema_version") == "aip-observation-refusal-v1"
    result["branch"] = "mixed" if candidate and refusal else "candidate" if candidate else "refusal" if refusal else "invalid"
    if candidate and refusal:
        errors.add("mixed_output_branches")
    if claims_evidence_authority(payload):
        errors.add("evidence_authority_violation")
    compiled = None
    if candidate:
        try:
            compiled = compile_v2(payload, materialized["case"])
            result["candidate_compiles"] = True
        except (ValueError, TypeError):
            errors.add("invalid_schema")
    if materialized["kind"] == "dynamic":
        scope = validate_scope_refusal(payload, materialized["control"])
        for witness in materialized.get("additional_witnesses", []):
            alternative = dict(materialized["control"], required_witness=witness)
            alternative_result = validate_scope_refusal(payload, alternative)
            if alternative_result["passed"]:
                scope = alternative_result
        result["scope_result"] = scope
        result["scope_false_acceptance"] = candidate
        if candidate:
            errors.add("forced_static_fit_out_of_scope")
        elif not scope["passed"]:
            errors.add("invalid_refusal_envelope" if scope["error_code"] == "INVALID_REFUSAL_SCHEMA" else "wrong_refusal_witness")
            if payload.get("error_code") != materialized["control"]["expected_code"]:
                errors.add("wrong_refusal_code")
        result["correct"] = scope["passed"] and not errors
    else:
        if refusal:
            errors.add("incorrect_rejection_in_scope")
        score = final_score(compiled, materialized["case"], materialized["evidence"])
        result["independent_score"] = score
        result["false_certification"] = score["false_certification"]
        if compiled is not None and not score["true_model_candidate_coverage"]:
            errors.add("semantic_wrong_partition")
        if compiled is not None and not score["certified_reference_model"]:
            errors.add("ambiguous_or_conflicted_verification")
        if not candidate and not refusal:
            errors.add("invalid_schema")
        result["correct"] = score["certified_reference_model"] and not errors
    result["errors"] = sorted(errors)
    return result


def analyze(manifest, bundle, report):
    spec = manifest["ablation"]
    by_id = {t["trial_id"]: t for t in report["trials"]}
    cells, pair_results = {}, {}
    failures = []
    for planned in bundle["plan"]:
        trial = by_id.get(planned["trial_id"])
        if trial is None or trial["status"] != "completed":
            failures.append({"trial_id": planned["trial_id"], "errors": ["incomplete"]})
        elif not trial["evaluation"]["correct"]:
            failures.append({"trial_id": trial["trial_id"], "errors": trial["evaluation"]["errors"]})
    for arm in spec["arms"]:
        arm_id = arm["id"]
        pairs = []
        for pair in spec["pairs"]:
            successes = []
            for repeat in range(spec["schedule"]["repeats"]):
                sides = [by_id.get(f"scope:{pair[side]}:{repeat}:{arm_id}", {})
                         for side in ("static_id", "dynamic_id")]
                successes.append(all(t.get("evaluation", {}).get("correct", False) for t in sides))
            repaired = [by_id.get(f"witness_repair:{pair['static_id']}:{repeat}:{arm_id}", {}).get(
                "evaluation", {}).get("correct", False) for repeat in range(spec["schedule"]["repeats"])]
            pairs.append({"pair_id": pair["pair_id"], "joint_success_by_repeat": successes,
                          "witness_repair_success_by_repeat": repaired})
        pair_results[arm_id] = pairs
        selected = [t for t in report["trials"] if t["arm"] == arm_id and t["status"] == "completed"]
        cell = {}
        for task, kind, name in (("scope", "static", "static"), ("scope", "dynamic", "dynamic"),
                                  ("witness_repair", "static", "witness_repair")):
            picked = [t for t in selected if t["task"] == task and bundle["cases"][t["case_id"]]["kind"] == kind]
            cell[name] = {"correct": sum(t["evaluation"]["correct"] for t in picked),
                          "assigned": len(spec["pairs"]) * spec["schedule"]["repeats"],
                          "completed": len(picked)}
        cell["joint_pair_success"] = {"correct": sum(sum(p["joint_success_by_repeat"]) for p in pairs),
                                      "assigned": len(spec["pairs"]) * spec["schedule"]["repeats"]}
        cells[arm_id] = cell
    def difference(treatment, control, metric):
        return cells[treatment][metric]["correct"] / cells[treatment][metric]["assigned"] - cells[control][metric]["correct"] / cells[control][metric]["assigned"]
    def pair_difference(index, treatment, control, metric):
        return (sum(pair_results[treatment][index][metric]) - sum(pair_results[control][index][metric])) / spec["schedule"]["repeats"]
    attempts = report["attempts"]
    return {
        "cells": cells, "pair_results": pair_results,
        "within_pair_contrasts": [{
            "pair_id": pair["pair_id"],
            "scope_a_effect_b0": pair_difference(i, "a1_b0", "a0_b0", "joint_success_by_repeat"),
            "scope_a_effect_b1": pair_difference(i, "a1_b1", "a0_b1", "joint_success_by_repeat"),
            "repair_b_effect_a0": pair_difference(i, "a0_b1", "a0_b0", "witness_repair_success_by_repeat"),
            "repair_b_effect_a1": pair_difference(i, "a1_b1", "a1_b0", "witness_repair_success_by_repeat"),
        } for i, pair in enumerate(spec["pairs"])],
        "scope_first_pair_success_difference": {"b0": difference("a1_b0", "a0_b0", "joint_pair_success"),
                                                 "b1": difference("a1_b1", "a0_b1", "joint_pair_success")},
        "witness_gloss_repair_difference": {"a0": difference("a0_b1", "a0_b0", "witness_repair"),
                                            "a1": difference("a1_b1", "a1_b0", "witness_repair")},
        "feedback_exposures_by_arm": {a["id"]: sum(t["task"] == "witness_repair" and t["arm"] == a["id"] and bool(t["attempt_ids"]) for t in report["trials"]) for a in spec["arms"]},
        "false_certifications_in_scope": sum(t.get("evaluation", {}).get("false_certification", False) for t in report["trials"]),
        "scope_false_acceptances": sum(t.get("evaluation", {}).get("scope_false_acceptance", False) for t in report["trials"]),
        "all_failures": failures,
        "error_counts_trial_level": dict(Counter(e for t in report["trials"] for e in t.get("evaluation", {}).get("errors", []))),
        "transport_error_counts": dict(Counter(e for a in attempts for e in a["errors"])),
        "provider_attempts": len(attempts), "cost_usd": sum(a["cost_usd"] for a in attempts),
        "tokens": {k: sum((a.get("raw_response", {}).get("usage") or {}).get(k, 0) for a in attempts)
                   for k in ("prompt_tokens", "completion_tokens")},
        "overall_scientific_pass": None, "population_confidence_interval": None,
        "uncertainty": spec["evaluation"]["uncertainty"],
        "semantic_versus_structural_effectiveness_established": False,
        "new_runtime_epsilon_gto_allowed": False, "adaptive_opponent_line_released": False,
    }


class ScopeAblationRunner(SmokeRunner):
    def run(self):
        self.report["schema_version"] = "aip-gamespec-scope-ablation-v3"
        self.report["execution_parameters"] = deepcopy(self.manifest["model"])
        self.persist()
        try:
            for planned in self.bundle["plan"]:
                trial = dict(planned, status="started", attempt_ids=[])
                self.report["trials"].append(trial)
                _, text, attempt = self.call(trial["trial_id"], messages_for(self.manifest, self.bundle, planned))
                trial["attempt_ids"].append(attempt["attempt_id"])
                trial["evaluation"] = evaluate_reply(text, self.bundle["cases"][trial["case_id"]], attempt["errors"])
                trial["status"] = "completed"
                self.persist()
            self.report["status"] = "completed"
        except RuntimeError as error:
            self.report["status"], self.report["stop_reason"] = "stopped", str(error)
        self.report["analysis"] = analyze(self.manifest, self.bundle, self.report)
        self.persist()
        return self.report


def replay(manifest, bundle, report):
    """Rebuild scores, exposure and cost from raw replies and fixed request plan."""
    if report["manifest_sha256"] != digest(manifest) or report["bundle_sha256"] != digest(bundle):
        raise ValueError("manifest or bundle mismatch")
    planned = {t["trial_id"]: t for t in bundle["plan"]}
    if [t["trial_id"] for t in report["trials"]] != [t["trial_id"] for t in bundle["plan"][:len(report["trials"])]]:
        raise ValueError("fixed schedule order mismatch")
    seen, used_attempts = set(), set()
    rebuilt = deepcopy(report)
    for trial in rebuilt["trials"]:
        if trial["trial_id"] in seen or trial["trial_id"] not in planned:
            raise ValueError("unknown or duplicate trial")
        seen.add(trial["trial_id"])
        plan = planned[trial["trial_id"]]
        if any(trial[k] != v for k, v in plan.items()):
            raise ValueError("trial assignment mismatch")
        if trial["status"] != "completed":
            continue
        if len(trial["attempt_ids"]) != 1:
            raise ValueError("one-reply budget violated")
        i = trial["attempt_ids"][0]
        if i in used_attempts:
            raise ValueError("reused provider attempt")
        used_attempts.add(i)
        attempt = rebuilt["attempts"][i]
        raw = attempt["raw_response"]
        if attempt["attempt_id"] != i or attempt["trial_id"] != trial["trial_id"]:
            raise ValueError("attempt assignment mismatch")
        if attempt["messages"] != messages_for(manifest, bundle, plan):
            raise ValueError("request or feedback mismatch")
        if raw["model"] != manifest["model"]["model_id"]:
            raise ValueError("model mismatch")
        usage, model = raw["usage"], manifest["model"]
        cost = (usage["prompt_tokens"] * model["input_usd_per_million"] + usage["completion_tokens"] * model["output_usd_per_million"]) / 1e6
        if abs(attempt["cost_usd"] - cost) > 1e-12:
            raise ValueError("cost mismatch")
        choice = raw["choices"][0]
        errors = []
        if choice["finish_reason"] != "stop":
            errors.append("truncated_output" if choice["finish_reason"] == "length" else "provider_error")
        text = choice["message"]["content"] or ""
        score = evaluate_reply(text, bundle["cases"][trial["case_id"]], errors)
        if score != trial["evaluation"]:
            raise ValueError("raw-response evaluation mismatch")
    if report["status"] == "completed" and (len(seen) != len(planned) or len(used_attempts) != len(report["attempts"])):
        raise ValueError("incomplete fixed schedule")
    analysis = analyze(manifest, bundle, rebuilt)
    if analysis != report["analysis"]:
        raise ValueError("analysis mismatch")
    return analysis
