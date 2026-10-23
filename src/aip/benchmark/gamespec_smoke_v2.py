"""Versioned interface repair; reuse v1 transport and independent evidence scorer.

The v1 module, dispatch lock and evidence remain byte-for-byte unchanged.
"""
from collections import Counter
from copy import deepcopy
import json

from aip.benchmark.gamespec_smoke import (
    SmokeRunner, candidate_payload, digest, feedback_compatible, final_score, make_bundle,
    structural_error, vocab_for,
)
from aip.core.game_spec_pilot import compile_game_spec_candidate_json
from aip.core.game_spec_smoke import validate_scope_refusal


def materialize_manifest(base, specification, diagnostic=False):
    manifest = deepcopy(base)
    manifest["manifest_id"] = specification["manifest_id"]
    manifest["purpose"] = specification["purpose"]
    manifest["protocol"] = "llm_gamespec_pilot_v2"
    manifest["system_prompt"] += specification["prompt_suffix"]
    # Remove a contradictory v1 instruction, not the strict uniqueness check.
    manifest["system_prompt"] = manifest["system_prompt"].replace(
        "Return the requested number of distinct candidates", "Return the requested range of distinct candidates")
    manifest["gates"] = {k: base["gates"][k] for k in ("maximum_call_usd", "maximum_total_usd")}
    manifest["v2_specification"] = deepcopy(specification)
    if diagnostic:
        d = specification["stronger_model_diagnostic"]
        for key in ("model_id", "input_usd_per_million", "output_usd_per_million"):
            manifest["model"][key] = d[key]
        manifest["model"]["reasoning_effort"] = d["reasoning_effort"]
        manifest["model"]["pricing_checked_date"] = specification["date"]
        manifest["model"]["snapshot_source"] = d["sources"][0]
        for key in ("maximum_call_usd", "maximum_total_usd"):
            manifest["gates"][key] = d[key]
        manifest["manifest_id"] += "_model_diagnostic"
    return manifest


def v2_bundle(base, manifest):
    # Generate from original insertion order: injected missing fields match v1.
    bundle = make_bundle(base)
    bundle["version"] = "gamespec-smoke-dispatch-v2"
    bundle["manifest_sha256"] = digest(manifest)
    bundle["dispatch_rules"]["candidate_count"] = "single exact 1; multi 1..3; no deduplication"
    bundle["dispatch_rules"]["missing_truth_order"] = bundle["dispatch_rules"]["missing_truth_order"].replace("request three candidates", "request one to three candidates")
    return bundle


def compile_v2(payload, case, single=False):
    return compile_game_spec_candidate_json(
        payload, vocab_for(case), minimum_candidates=1, maximum_candidates=3,
        exact_candidates=1 if single else None)


def diagnose_output(payload, case, single=False):
    try:
        compiled = compile_v2(payload, case, single)
    except (ValueError, TypeError) as error:
        labels = ["schema_violation"]
        if "unique" in str(error):
            labels.append("duplicate_candidate")
        if isinstance(payload, dict) and payload.get("status") == "out_of_schema":
            labels.append("incorrect_oos_refusal")
        return None, labels, structural_error(payload, case, error)
    labels = []
    if not any(dict(s) == case["reference_owners"] for s in compiled.signatures):
        labels.append("true_model_absent")
    for signature in compiled.signatures:
        for field, owner in signature:
            expected = case["reference_owners"][field]
            if owner != expected:
                labels.append("overhidden_public_field" if expected == "public" else
                              "privacy_leak" if owner == "public" else "wrong_private_owner")
    return compiled, sorted(set(labels)), None


def analyze_v2(manifest, report):
    trials = report["trials"]
    assigned = manifest["schedule"]["main_trials_per_arm"]
    groups = {}
    for arm in manifest["schedule"]["arm_order"]:
        selected = [t for t in trials if t["kind"] == "main" and t["arm"] == arm]
        covered = sum(t.get("score", {}).get("true_model_candidate_coverage", False) for t in selected)
        groups[arm] = {
            "assigned": assigned, "completed": sum(t["status"] == "completed" for t in selected),
            "first_schema_valid": sum(t.get("first_schema_valid", False) for t in selected),
            "first_schema_rate": sum(t.get("first_schema_valid", False) for t in selected) / assigned,
            "final_coverage": covered, "coverage_rate": covered / assigned,
            "reference_verified": sum(t.get("score", {}).get("certified_reference_model", False) for t in selected),
            "repairs": sum(t.get("repair_count", 0) for t in selected),
            "by_case": {case_id: {
                "assigned": manifest["schedule"]["repeats_per_case_per_arm"],
                "coverage": sum(t.get("score", {}).get("true_model_candidate_coverage", False)
                                for t in selected if t["case_id"] == case_id),
            } for case_id in manifest["schedule"]["ordered_cases"]},
        }
    failures = []
    for t in trials:
        if t.get("status") != "completed":
            failures.append({"trial_id": t["trial_id"], "reason": "incomplete"})
        elif t["kind"] == "oos":
            if not t["scope_result"]["passed"]:
                failures.append({"trial_id": t["trial_id"], "reason": "incorrect_scope_refusal"})
        elif not t.get("score", {}).get("certified_reference_model", False):
            failures.append({"trial_id": t["trial_id"], "reason": t["score"]["verification"]["status"],
                             "errors": t["errors"]})
    probes = [t for t in trials if t["kind"] == "probe"]
    oos = [t for t in trials if t["kind"] == "oos"]
    closed = [t for t in trials if t["kind"] == "missing_truth"]
    errors = Counter(e for a in report["attempts"] for e in set(a["errors"]))
    return {
        "groups": groups,
        "semantic_minus_structural_coverage": groups["multi_semantic_feedback"]["coverage_rate"] - groups["multi_structural_feedback"]["coverage_rate"],
        "probe_executable": sum(t.get("first_schema_valid", False) for t in probes),
        "probe_total": len(probes),
        "correct_oos": sum(t["scope_result"]["passed"] for t in oos), "oos_total": len(oos),
        "missing_truth_restored": sum(t["score"]["true_model_candidate_coverage"] for t in closed if "score" in t),
        "missing_truth_total": len(closed),
        "false_certifications": sum(t.get("score", {}).get("false_certification", False) for t in trials),
        "human_verified": sum(s["certified_reference_model"] for s in report["human_ceiling"]),
        "provider_attempts": len(report["attempts"]),
        "cost_usd": sum(a["cost_usd"] for a in report["attempts"]),
        "error_counts_attempt_level": dict(errors), "final_failures": failures,
        "final_candidate_counts": dict(Counter(str(t["score"]["candidate_count"]) for t in trials if "score" in t)),
        "tokens": {
            key: sum(a.get("raw_response", {}).get("usage", {}).get(key, 0) for a in report["attempts"])
            for key in ("prompt_tokens", "completion_tokens")
        },
        "overall_scientific_pass": None,
        "uncertainty": manifest["v2_specification"]["reporting"]["uncertainty"],
        "conditional_solver_succeeded": None,
    }


def diagnostic_required(report):
    if report["status"] != "completed":
        return False
    for trial in report["trials"]:
        if trial["kind"] == "oos" and not trial["scope_result"]["passed"]:
            return True
        if trial["kind"] in ("main", "probe") and not trial["score"]["true_model_candidate_coverage"]:
            return True
        if trial.get("score", {}).get("false_certification", False):
            return True
    return False


class V2SmokeRunner(SmokeRunner):
    def messages(self, case, count, feedback=None, previous=None):
        return super().messages(case, 1 if count == 1 else "1 to 3", feedback, previous)

    def run_trial(self, case, arm, repeat, kind="main", previous=None, initial=None):
        single = arm == "single_no_feedback"
        trial_id = f"{kind}:{case['case_id']}:{repeat}:{arm}"
        trial = {"trial_id": trial_id, "case_id": case["case_id"], "arm": arm,
                 "kind": kind, "attempt_ids": [], "initial_coverage": None,
                 "errors": [], "status": "started"}
        self.report["trials"].append(trial)
        materialized = self.bundle["cases"][case["case_id"]]
        if kind == "probe":
            feedback = {"code": "MISSING_FIELD", "fields": [materialized["structure_probe"]["missing_field"]]}
            previous = json.dumps(materialized["structure_probe"]["payload"])
            maximum = 1
        elif kind == "missing_truth":
            previous = json.dumps(materialized["missing_truth_initial"])
            trial["initial_coverage"] = False
            feedback = {"code": "STRUCTURE_OK", "requested_candidates": "1 to 3"}
            if arm == "multi_semantic_feedback":
                feedback["witnesses"] = materialized["feedback_evidence"]
            maximum = 2
        else:
            feedback = None
            maximum = 1 if single else 3
        compiled = None
        for step in range(maximum):
            payload, previous, attempt = self.call(trial_id, self.messages(case, 1 if single else 3, feedback, previous))
            trial["attempt_ids"].append(attempt["attempt_id"])
            compiled, labels, error_feedback = diagnose_output(payload, case, single)
            if attempt["errors"]:
                compiled = None
            attempt["errors"] = sorted(set(attempt["errors"] + labels))
            trial["errors"] = sorted(set(trial["errors"] + attempt["errors"]))
            if step == 0:
                trial["first_schema_valid"] = compiled is not None
            if compiled is not None and (arm != "multi_semantic_feedback" or kind == "probe"
                                        or feedback_compatible(compiled, materialized["feedback_evidence"])):
                break
            feedback = error_feedback or {"code": "STRUCTURE_OK"}
            if arm == "multi_semantic_feedback":
                feedback["witnesses"] = materialized["feedback_evidence"]
        trial["score"] = final_score(compiled, case, materialized)
        trial["repair_count"] = max(0, len(trial["attempt_ids"]) - (1 if kind == "main" else 0))
        trial["status"] = "completed"
        self.persist()

    def run(self):
        self.report["schema_version"] = "aip-provider-gamespec-smoke-v2"
        self.persist()
        try:
            cases = {c["case_id"]: c for c in self.manifest["cases"]}
            schedule = self.manifest["schedule"]
            for case_id in schedule["ordered_cases"]:
                for repeat in range(schedule["repeats_per_case_per_arm"]):
                    for arm in schedule["arm_order"]:
                        self.run_trial(cases[case_id], arm, repeat)
            control = self.manifest["out_of_schema"]
            scope_case = {"case_id": control["case_id"], "rules": control["rules"],
                          "fields": cases["dev_dice"]["fields"]}
            for arm in schedule["arm_order"]:
                for repeat in range(5):
                    trial_id = f"oos:{repeat}:{arm}"
                    payload, _, attempt = self.call(trial_id, self.messages(scope_case, 1 if arm == "single_no_feedback" else 3))
                    result = validate_scope_refusal(payload, control)
                    if not result["passed"]:
                        attempt["errors"].append("forced_in_schema_fit" if isinstance(payload, dict) and "candidates" in payload else "incorrect_oos_refusal")
                    self.report["trials"].append({"trial_id": trial_id, "arm": arm, "kind": "oos",
                                                  "status": "completed", "attempt_ids": [attempt["attempt_id"]],
                                                  "scope_result": result})
                    self.persist()
            for arm in schedule["arm_order"][1:]:
                for index in range(6):
                    self.run_trial(cases[schedule["ordered_cases"][index % 4]], arm, index, "probe")
            for arm in schedule["arm_order"][1:]:
                for index in range(3):
                    self.run_trial(cases[schedule["ordered_cases"][index]], arm, index, "missing_truth")
            for case in cases.values():
                compiled = compile_v2(candidate_payload(case, [case["reference_owners"]]), case, True)
                self.report["human_ceiling"].append(final_score(compiled, case, self.bundle["cases"][case["case_id"]]))
            self.report["status"] = "completed"
        except RuntimeError as error:
            self.report["status"], self.report["stop_reason"] = "stopped", str(error)
        self.report["analysis"] = analyze_v2(self.manifest, self.report)
        self.report["stronger_model_diagnostic_required"] = diagnostic_required(self.report)
        self.persist()
        return self.report


def independent_replay(manifest, bundle, report):
    """Recompile raw final responses; do not trust cached candidate scores."""
    if report["manifest_sha256"] != digest(manifest) or report["bundle_sha256"] != digest(bundle):
        raise ValueError("manifest or evidence bundle mismatch")
    replay = deepcopy(report)
    cases = {c["case_id"]: c for c in manifest["cases"]}
    for index, attempt in enumerate(replay["attempts"]):
        if attempt["attempt_id"] != index:
            raise ValueError("attempt index mismatch")
        if attempt["status"] != "completed":
            continue  # A stopped provider request has no response to replay.
        raw = attempt["raw_response"]
        if raw["model"] != manifest["model"]["model_id"]:
            raise ValueError("model snapshot mismatch")
        usage = raw["usage"]
        expected_cost = (usage["prompt_tokens"] * manifest["model"]["input_usd_per_million"]
                         + usage["completion_tokens"] * manifest["model"]["output_usd_per_million"]) / 1e6
        if abs(attempt["cost_usd"] - expected_cost) > 1e-12:
            raise ValueError("cost replay mismatch")
    for trial in replay["trials"]:
        if trial["status"] != "completed":
            continue
        attempt = replay["attempts"][trial["attempt_ids"][-1]]
        choice = attempt["raw_response"]["choices"][0]
        try:
            payload = json.loads(choice["message"]["content"])
        except (ValueError, TypeError):
            payload = None
        if trial["kind"] == "oos":
            result = validate_scope_refusal(payload, manifest["out_of_schema"])
            if result != trial["scope_result"]:
                raise ValueError("scope replay mismatch")
            continue
        case = cases[trial["case_id"]]
        first = replay["attempts"][trial["attempt_ids"][0]]["raw_response"]["choices"][0]
        try:
            first_payload = json.loads(first["message"]["content"])
        except (ValueError, TypeError):
            first_payload = None
        first_compiled, _, _ = diagnose_output(first_payload, case, trial["arm"] == "single_no_feedback")
        first_valid = (first_compiled is not None and first["finish_reason"] == "stop"
                       and not first["message"].get("refusal"))
        if first_valid != trial["first_schema_valid"]:
            raise ValueError("first response schema replay mismatch")
        compiled, _, _ = diagnose_output(payload, case, trial["arm"] == "single_no_feedback")
        if choice["finish_reason"] != "stop" or choice["message"].get("refusal"):
            compiled = None
        score = final_score(compiled, case, bundle["cases"][case["case_id"]])
        if score != trial["score"]:
            raise ValueError(f"raw response replay mismatch: {trial['trial_id']}")
    analysis = analyze_v2(manifest, replay)
    if analysis != report["analysis"]:
        raise ValueError("analysis replay mismatch")
    return analysis
