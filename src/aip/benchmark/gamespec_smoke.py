"""Bounded, journaled provider smoke for the frozen observation task."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from time import monotonic

from aip.core.game_spec import ObservationStateRecord
from aip.core.game_spec_pilot import (
    EvidenceSourcePolicy, GameSpecVocabulary, compile_game_spec_candidate_json,
    compile_trusted_evidence_json, score_pilot_case,
)
from aip.core.game_spec_smoke import (
    compile_field_contrast_suite, evaluate_smoke_gates, validate_scope_refusal,
)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(path)


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def candidate_payload(case, owners_list):
    return {
        "schema_version": "aip-observation-gamespec-candidates-v1",
        "game_id": case["case_id"],
        "candidates": [{
            "hypothesis_id": f"candidate_{index}",
            "public_fields": [f for f, owner in owners.items() if owner == "public"],
            "private_fields_by_player": {
                f"player_{p}": [f for f, owner in owners.items() if owner == f"player_{p}"]
                for p in range(2)
            },
        } for index, owners in enumerate(owners_list)],
    }


def make_bundle(manifest):
    cases = {}
    for case in manifest["cases"]:
        vocab = GameSpecVocabulary(case["case_id"], 2, tuple(case["fields"]))
        final = compile_field_contrast_suite(vocab, case["reference_owners"])
        # Prioritize private invisibility, then other contrasts, fixed before calls.
        ordered = sorted(final, key=lambda e: (not e.evidence.observed_same,
                                              e.evidence.evidence_id))
        feedback = []
        for item in ordered[:2]:
            e = item.evidence
            feedback.append({
                "evidence_id": "feedback_" + e.evidence_id,
                "source_id": "reviewed_feedback_reference",
                "acting_player": e.left.acting_player,
                "left_fields": {k: v + 2 for k, v in e.left.fields},
                "right_fields": {k: v + 2 for k, v in e.right.fields},
                "observed_same": e.observed_same,
            })
        wrong = [dict.fromkeys(case["fields"], owner) for owner in ("public", "player_0", "player_1")]
        wrong = [w for w in wrong if w != case["reference_owners"]][:2]
        probe = candidate_payload(case, wrong + [case["reference_owners"]])
        missing = next(iter(case["fields"]))
        for field_list in [probe["candidates"][0]["public_fields"],
                           *probe["candidates"][0]["private_fields_by_player"].values()]:
            if missing in field_list:
                field_list.remove(missing)
        cases[case["case_id"]] = {
            "public_input": {k: case[k] for k in ("case_id", "rules", "fields")},
            "reference_owners": case["reference_owners"],
            "feedback_evidence": feedback,
            "final_evidence": [{
                "evidence_id": e.evidence.evidence_id,
                "acting_player": e.evidence.left.acting_player,
                "left_fields": e.evidence.left.field_mapping(),
                "right_fields": e.evidence.right.field_mapping(),
                "observed_same": e.evidence.observed_same,
            } for e in final],
            "structure_probe": {"payload": probe, "missing_field": missing},
            "missing_truth_initial": candidate_payload(case, wrong),
        }
    return {
        "version": "gamespec-smoke-dispatch-v1", "manifest_sha256": digest(manifest),
        "cases": cases,
        "dispatch_rules": {
            "main_order": "case, repeat, arm",
            "repairs": "structural arms stop on first compile success; semantic arm additionally requires at least one candidate compatible with the two feedback witnesses; at most two repairs",
            "semantic_feedback": "only the preselected two feedback contrasts; final six contrasts never enter requests",
            "probe_order": "feedback arm, probe index 0..5; cases cycle through frozen order; one reply each",
            "missing_truth_order": "feedback arm, control index 0..2; first three cases; initial two wrong partitions supplied as prior assistant output; request three candidates; first repair receives STRUCTURE_OK or feedback witnesses; at most two replies",
            "scope_order": "arm, repeat; OOS fields are the dev_dice vocabulary; one reply without repair",
            "provider_failure": "stop further dispatch on provider error, missing usage, version mismatch, budget violation or response refusal; never silently replay",
            "api_key": "read locally; never included in artifacts",
        },
    }


def vocab_for(case):
    return GameSpecVocabulary(case["case_id"], 2, tuple(case["fields"]))


def compile_output(payload, case, count):
    return compile_game_spec_candidate_json(payload, vocab_for(case), exact_candidates=count)


def feedback_compatible(compiled, items):
    return any(all(
        h.observation_spec.project(item["left_fields"], item["acting_player"])
        == h.observation_spec.project(item["right_fields"], item["acting_player"])
        if item["observed_same"] else
        h.observation_spec.project(item["left_fields"], item["acting_player"])
        != h.observation_spec.project(item["right_fields"], item["acting_player"])
        for item in items
    ) for h in compiled.hypotheses)


def structural_error(payload, case, error):
    # Deliberately uses no reference owners, no semantic score, no final evidence.
    if isinstance(payload, dict):
        candidates = payload.get("candidates")
        if isinstance(candidates, list):
            for c in candidates:
                if not isinstance(c, dict):
                    continue
                fields = c.get("public_fields", [])
                private = c.get("private_fields_by_player", {})
                if isinstance(fields, list) and isinstance(private, dict):
                    assigned = list(fields)
                    for values in private.values():
                        if isinstance(values, list):
                            assigned.extend(values)
                    missing = sorted(set(case["fields"]) - {x for x in assigned if isinstance(x, str)})
                    if missing:
                        return {"code": "MISSING_FIELD", "fields": missing}
    message = str(error)
    for needle, code in (("exactly", "CANDIDATE_COUNT_OR_PARTITION"),
                         ("unique", "DUPLICATE_CANDIDATE"),
                         ("partition", "FIELD_VOCABULARY")):
        if needle in message:
            return {"code": code}
    return {"code": "INVALID_JSON_OR_SCHEMA"}


def output_labels(payload, case, count):
    try:
        compiled = compile_output(payload, case, count)
    except (ValueError, TypeError) as error:
        labels = ["schema_violation"]
        text = str(error)
        for fragment, label in (("partition the", "unknown_or_missing_field"),
                                 ("exactly", "candidate_count_error"),
                                 ("unique", "duplicate_candidate")):
            if fragment in text:
                labels.append(label)
        if isinstance(payload, dict) and payload.get("status") == "out_of_schema":
            labels.append("incorrect_oos_refusal")
        if any(word in json.dumps(payload) for word in ("reliability", "certified", "posterior", '"prior"')):
            labels.append("evidence_authority_violation")
        return None, labels, structural_error(payload, case, error)
    labels = set()
    reference = case["reference_owners"]
    for signature in compiled.signatures:
        for field, owner in signature:
            expected = reference[field]
            if owner == expected:
                continue
            if owner == "public" or (expected != "public" and owner != expected):
                labels.add("privacy_leak")
            if expected == "public":
                labels.add("overhidden_public_field")
            elif owner != "public":
                labels.add("wrong_private_owner")
    if not any(dict(s) == reference for s in compiled.signatures):
        labels.add("true_model_absent")
    return compiled, sorted(labels), None


def final_score(compiled, case, materialized):
    if compiled is None:
        return {"true_model_candidate_coverage": False, "false_certification": False,
                "certified_reference_model": False, "candidate_count": 0,
                "verification": {"status": "invalid_output", "certified": False}}
    source = EvidenceSourcePolicy("final_reference", "independent_reference", 1.0,
                                  "authored_rule_reference", True)
    suite = []
    for item in materialized["final_evidence"]:
        p = item["acting_player"]
        worlds = {side: ObservationStateRecord.from_mapping(
            (item["evidence_id"], side), p, item[side + "_fields"]
        ) for side in ("left", "right")}
        suite.append(compile_trusted_evidence_json({
            "schema_version": "aip-observation-evidence-v1",
            "source_id": source.source_id, "evidence_id": item["evidence_id"],
            "acting_player": p, "observed_same": item["observed_same"],
            "left_world_id": "left", "right_world_id": "right",
        }, sources={source.source_id: source}, worlds=worlds))
    reference = compile_output(candidate_payload(case, [case["reference_owners"]]), case, 1)
    return score_pilot_case(
        arm_id="final_blind_scoring", candidate_set=compiled,
        trusted_reference=reference.hypotheses[0].observation_spec,
        vocabulary=vocab_for(case), evidence=tuple(suite),
        required_evidence_ids=tuple(e.evidence.evidence_id for e in suite),
        repair_count=0, conditional_solver_succeeded=None,
    ).to_artifact()


class SmokeRunner:
    def __init__(self, manifest, bundle, client, output, token_counter):
        self.manifest, self.bundle, self.client = manifest, bundle, client
        self.output, self.token_counter = Path(output), token_counter
        self.report = {
            "schema_version": "aip-provider-gamespec-smoke-v1", "status": "running",
            "manifest_sha256": digest(manifest), "bundle_sha256": digest(bundle),
            "model_requested": manifest["model"]["model_id"], "attempts": [],
            "trials": [], "human_ceiling": [], "stop_reason": None,
            "runtime_epsilon_gto_allowed": False, "adaptive_opponent_line_released": False,
        }
        if self.output.exists():
            raise FileExistsError("run output already exists; preserve it and do not replay")

    def persist(self):
        write_json(self.output, self.report)

    def messages(self, case, count, feedback=None, previous=None):
        content = self.manifest["user_prompt_template"].format(
            case_id=case["case_id"], rules=case["rules"],
            fields_json=json.dumps(case["fields"], sort_keys=True),
            candidate_count=count, feedback_json=json.dumps(feedback or {}, sort_keys=True),
        )
        messages = [{"role": "system", "content": self.manifest["system_prompt"]}]
        if previous is not None:
            messages.append({"role": "assistant", "content": previous})
        messages.append({"role": "user", "content": content})
        return messages

    def call(self, trial_id, messages):
        model = self.manifest["model"]
        attempts = self.report["attempts"]
        reserved = (model["maximum_input_tokens"] * model["input_usd_per_million"]
                    + model["maximum_output_tokens"] * model["output_usd_per_million"]) / 1e6
        consumed = sum(a.get("cost_usd", reserved) for a in attempts)
        if (len(attempts) >= self.manifest["schedule"]["maximum_calls"]
                or consumed + reserved > self.manifest["gates"]["maximum_total_usd"]
                or reserved > self.manifest["gates"]["maximum_call_usd"]):
            raise RuntimeError("budget_exceeded")
        # Include chat overhead conservatively, tokenizer maps to this model.
        estimate = sum(self.token_counter(m["content"]) + 10 for m in messages) + 32
        if estimate > model["maximum_input_tokens"]:
            raise RuntimeError("input_token_cap_exceeded")
        attempt = {"attempt_id": len(attempts), "trial_id": trial_id,
                   "messages": deepcopy(messages), "status": "started",
                   "input_token_preflight": estimate, "cost_usd": reserved,
                   "errors": []}
        attempts.append(attempt)
        self.persist()  # Crash after dispatch remains visible and cannot auto-retry.
        started = monotonic()
        try:
            response = self.client.chat.completions.create(
                model=model["model_id"], temperature=model["temperature"],
                response_format={"type": model["response_format"]},
                max_completion_tokens=model["maximum_output_tokens"], messages=messages,
                store=False, service_tier="default",
            )
        except Exception as error:
            attempt.update(status="provider_error", latency_seconds=monotonic() - started,
                           error_type=type(error).__name__,
                           http_status=getattr(error, "status_code", None),
                           errors=["timeout" if "timeout" in type(error).__name__.lower() else "provider_error"])
            self.persist()
            raise RuntimeError("provider_error_stop") from None
        attempt.update(status="completed", raw_response=response.model_dump(mode="json"),
                       latency_seconds=monotonic() - started,
                       request_id=getattr(response, "_request_id", None),
                       resolved_model=response.model)
        usage = response.usage
        if usage is None:
            attempt["errors"].append("missing_usage")
            self.persist()
            raise RuntimeError("missing_usage")
        attempt["cost_usd"] = (usage.prompt_tokens * model["input_usd_per_million"]
                               + usage.completion_tokens * model["output_usd_per_million"]) / 1e6
        if (response.model != model["model_id"] or usage.prompt_tokens > model["maximum_input_tokens"]
                or usage.completion_tokens > model["maximum_output_tokens"]
                or attempt["cost_usd"] > self.manifest["gates"]["maximum_call_usd"]):
            self.persist()
            raise RuntimeError("provider_model_or_budget_mismatch")
        choice = response.choices[0]
        if getattr(choice.message, "refusal", None):
            attempt["errors"].append("provider_error")
            self.persist()
            raise RuntimeError("provider_refusal_stop")
        if choice.finish_reason != "stop":
            attempt["errors"].append("truncated_output" if choice.finish_reason == "length" else "provider_error")
        text = choice.message.content or ""
        try:
            payload = json.loads(text, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
        except (ValueError, TypeError):
            attempt["errors"].append("invalid_json")
            payload = None
        self.persist()
        print(json.dumps({"call": len(attempts), "trial": trial_id,
                          "cost_usd": round(attempt["cost_usd"], 6)}), flush=True)
        return payload, text, attempt

    def run_trial(self, case, arm, repeat, kind="main", previous=None, initial=None):
        count = 1 if arm == "single_no_feedback" else 3
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
            feedback = {"code": "STRUCTURE_OK", "requested_candidates": 3}
            if arm == "multi_semantic_feedback":
                feedback["witnesses"] = materialized["feedback_evidence"]
            maximum = 2
        else:
            feedback = None
            maximum = 1 if arm == "single_no_feedback" else 3
        compiled = None
        for step in range(maximum):
            payload, previous, attempt = self.call(trial_id, self.messages(case, count, feedback, previous))
            trial["attempt_ids"].append(attempt["attempt_id"])
            compiled, labels, error_feedback = output_labels(payload, case, count)
            if attempt["errors"]:
                compiled = None
            attempt["errors"] = sorted(set(attempt["errors"] + labels))
            trial["errors"] = sorted(set(trial["errors"] + attempt["errors"]))
            if step == 0:
                trial["first_schema_valid"] = compiled is not None
            if compiled is not None and (
                arm != "multi_semantic_feedback" or kind == "probe"
                or feedback_compatible(compiled, materialized["feedback_evidence"])
            ):
                break
            feedback = error_feedback or {"code": "STRUCTURE_OK"}
            if arm == "multi_semantic_feedback":
                feedback["witnesses"] = materialized["feedback_evidence"]
        trial["score"] = final_score(compiled, case, materialized)
        trial["repair_count"] = max(0, len(trial["attempt_ids"]) - (1 if kind == "main" else 0))
        trial["status"] = "completed"
        self.persist()

    def run(self):
        self.persist()
        try:
            cases = {c["case_id"]: c for c in self.manifest["cases"]}
            schedule = self.manifest["schedule"]
            for case_id in schedule["ordered_cases"]:
                for repeat in range(schedule["repeats_per_case_per_arm"]):
                    for arm in schedule["arm_order"]:
                        self.run_trial(cases[case_id], arm, repeat)
            for arm in schedule["arm_order"]:
                control = self.manifest["out_of_schema"]
                case = {"case_id": control["case_id"], "rules": control["rules"],
                        "fields": cases["dev_dice"]["fields"]}
                for repeat in range(5):
                    trial_id = f"oos:{repeat}:{arm}"
                    payload, _, attempt = self.call(trial_id, self.messages(case, 1 if arm == "single_no_feedback" else 3))
                    result = validate_scope_refusal(payload, control)
                    if not result["passed"]:
                        attempt["errors"].append("forced_in_schema_fit" if isinstance(payload, dict) and "candidates" in payload else "incorrect_oos_refusal")
                    self.report["trials"].append({
                        "trial_id": trial_id, "arm": arm, "kind": "oos", "status": "completed",
                        "attempt_ids": [attempt["attempt_id"]], "scope_result": result,
                    })
                    self.persist()
            for arm in schedule["arm_order"][1:]:
                for index in range(6):
                    case_id = schedule["ordered_cases"][index % 4]
                    self.run_trial(cases[case_id], arm, index, "probe")
            for arm in schedule["arm_order"][1:]:
                for index in range(3):
                    self.run_trial(cases[schedule["ordered_cases"][index]], arm, index, "missing_truth")
            for case in cases.values():
                compiled = compile_output(candidate_payload(case, [case["reference_owners"]]), case, 1)
                self.report["human_ceiling"].append(final_score(compiled, case, self.bundle["cases"][case["case_id"]]))
            self.report["status"] = "completed"
        except RuntimeError as error:
            self.report["status"] = "stopped"
            self.report["stop_reason"] = str(error)
        self.report["analysis"] = analyze(self.manifest, self.report)
        self.persist()
        return self.report


def analyze(manifest, report):
    trials, attempts = report["trials"], report["attempts"]
    mains = [t for t in trials if t["kind"] == "main"]
    groups = {}
    schema = {}
    for arm in manifest["schedule"]["arm_order"]:
        selected = [t for t in mains if t["arm"] == arm]
        count = manifest["schedule"]["main_trials_per_arm"]
        coverage = sum(t.get("score", {}).get("true_model_candidate_coverage", False) for t in selected)
        verified = sum(t.get("score", {}).get("certified_reference_model", False) for t in selected)
        schema[arm] = {"valid": sum(t.get("first_schema_valid", False) for t in selected), "total": len(selected)}
        groups[arm] = {"assigned": count, "completed": sum(t["status"] == "completed" for t in selected),
                       "first_schema_valid": schema[arm]["valid"], "coverage": coverage,
                       "coverage_rate": coverage / count, "reference_verified": verified,
                       "verification_rate": verified / count,
                       "repairs": sum(t.get("repair_count", 0) for t in selected)}
    probes = [t for t in trials if t["kind"] == "probe"]
    oos = [t for t in trials if t["kind"] == "oos"]
    closed = [t for t in trials if t["kind"] == "missing_truth"]
    false_count = sum(t.get("score", {}).get("false_certification", False) for t in trials)
    observations = {
        "schema_by_arm": schema,
        "repairs_executable": sum(t.get("first_schema_valid", False) for t in probes),
        "repair_probes": len(probes), "correct_oos": sum(t["scope_result"]["passed"] for t in oos),
        "oos_trials": len(oos), "closed_set_trials": len(closed),
        "closed_set_correct": sum(t["status"] == "completed" and not t.get("score", {}).get("false_certification", True) for t in closed),
        "human_verified": sum(s["certified_reference_model"] for s in report["human_ceiling"]),
        "human_cases": len(report["human_ceiling"]),
        "call_costs_usd": [a["cost_usd"] for a in attempts],
        "usage_complete": bool(attempts) and all(a.get("raw_response", {}).get("usage") is not None for a in attempts),
        "false_certifications": false_count,
    }
    return {
        "groups": groups, "observations": observations,
        "gates": evaluate_smoke_gates(manifest, observations),
        "provider_attempts": len(attempts), "cost_usd": sum(a["cost_usd"] for a in attempts),
        "error_counts_attempt_level": dict(Counter(e for a in attempts for e in set(a["errors"]))),
        "scope": "public engineering smoke; not powered or novel held-out game generalization",
        "conditional_solver_succeeded": None,
    }
