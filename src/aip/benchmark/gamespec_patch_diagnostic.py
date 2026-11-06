"""Luna-only preregistered patch/rewrite dispatch, scoring and offline replay."""
from collections import Counter
from copy import deepcopy
import json

from aip.benchmark.gamespec_attribution import messages_for as old_messages, parameters as old_parameters
from aip.benchmark.gamespec_cell_audit import expand_repair_output, cell_ledger, repair_schema
from aip.benchmark.gamespec_feedback_repair import local_feedback
from aip.benchmark.gamespec_prospective import score
from aip.benchmark.gamespec_scope_ablation import strict_json
from aip.benchmark.gamespec_smoke import SmokeRunner, digest, write_json
from aip.benchmark.gamespec_validation import verify_frozen_output


def materialize(old_manifest, old_bundle, spec, addendum):
    m, b = deepcopy(old_manifest), deepcopy(old_bundle)
    m["patch_spec"], m["execution_addendum"] = deepcopy(spec), deepcopy(addendum)
    m["manifest_id"] = "gamespec-patch-v12:gpt-6-luna"
    m["schedule"] = {"maximum_calls": 72}
    if any(m["model"].get(k) != v for k, v in spec["model"].items()):
        raise ValueError("frozen Luna parameters differ")
    b["plan"] = [dict(p, condition="C", task="scope", arm="f1_s1") for p in spec["schedule"]["plan"]]
    if len(b["plan"]) != 72 or len({p["trial_id"] for p in b["plan"]}) != 72:
        raise ValueError("fixed 72 unique calls required")
    b["manifest_sha256"] = digest(m)
    return m, b


def input_table(bundle, trial):
    s = bundle["seeds"][trial["seed_id"]]
    return s["original_table"] if trial["seed_kind"] == "wrong" else s["correct_control"]


def messages_for(m, b, p):
    case = b["cases"][p["case_id"]]["case"]
    feedback = None if p["feedback"] == "none" else local_feedback(tuple(case["fields"]), input_table(b, p))
    return [old_messages(m, b, p)[0],
        {"role": "assistant", "content": json.dumps({"stage_table": input_table(b, p)})},
        {"role": "user", "content": "RULES:\n" + case["rules"] + "\nFIELDS: " + json.dumps(case["fields"], sort_keys=True)
            + "\n" + m["patch_spec"]["shared_interface"]["common_user_instruction"]
            + "\nFEEDBACK: " + json.dumps(feedback, sort_keys=True)
            + "\nProposal JSON schema: " + json.dumps(repair_schema(m, case, p["representation"]), sort_keys=True)}]


def parameters(m, b, p):
    params = old_parameters(m, b, p)
    params["response_format"]["json_schema"]["schema"] = repair_schema(m, b["cases"][p["case_id"]]["case"], p["representation"])
    return params


def evaluate(text, m, b, p, errors=()):
    item = b["cases"][p["case_id"]]; fields = tuple(item["case"]["fields"])
    original = input_table(b, p)
    payload = expanded = None; interface = []
    try:
        payload = strict_json(text)
    except (ValueError, TypeError):
        interface.append("invalid_json")
    if not isinstance(payload, dict) or set(payload) != {
            "edits" if p["representation"] == "patch" else "stage_table", "proposal"}:
        interface.append("envelope_contract_failure")
    if not interface:
        try:
            expanded = expand_repair_output(payload, p["representation"], original, fields)
        except (ValueError, TypeError, KeyError):
            interface.append("patch_application_failure" if p["representation"] == "patch" else "rewrite_table_contract_failure")
    # Independent proposal-only endpoint never confers table/joint correctness.
    proposal = payload.get("proposal") if isinstance(payload, dict) else None
    proposal_score = score(json.dumps(proposal), item, errors)
    record, local, _, e = verify_frozen_output(json.dumps(expanded), "C", item, errors)
    ledger = cell_ledger(original, expanded["stage_table"], item["visibility_contexts"], fields) if expanded else None
    unchanged = bool(ledger is not None and all(c["input"] == c["output"] for c in ledger))
    categories = set(interface + list(errors))
    if not proposal_score["serialization_ok"]: categories.add("proposal_contract_failure")
    elif not proposal_score["correct"]: categories.add("proposal_reference_mismatch")
    if e["table_structurally_valid"] and not e["table_matches_reference"]: categories.add("table_reference_mismatch")
    if e["proposal_consistent_with_own_table"] is False: categories.add("proposal_own_table_mismatch")
    if unchanged and p["seed_kind"] == "wrong": categories.add("unchanged_wrong_table")
    if p["representation"] == "rewrite" and (not isinstance(payload, dict) or payload.get("stage_table") in (None, [])):
        categories.add("missing_or_empty_table")
    return {"evaluation": e, "validation": record.to_artifact(), "local": local,
        "expanded_output": expanded, "interface_errors": sorted(set(interface)),
        "proposal_only": proposal_score, "categories": sorted(categories), "cell_ledger": ledger,
        "metrics": {"table_correct": e["table_correct"], "joint_correct": e["whole_response_correct"],
            "reference_proposal_correct": proposal_score["correct"],
            "own_table_consistent": e["proposal_consistent_with_own_table"],
            "unchanged_table": unchanged, "invalid_patch": p["representation"] == "patch" and bool(interface),
            "repair_rounds": 1,
            "cell_outcomes": dict(Counter(c["outcome"] for c in ledger)) if ledger is not None else None}}


def summary(rows):
    def n(key): return sum(bool(r["metrics"] and r["metrics"][key]) for r in rows)
    completed = sum(r["status"] == "completed" for r in rows)
    return {"assigned": len(rows), "completed": completed,
        "table_correct": n("table_correct"), "joint_correct": n("joint_correct"),
        "reference_proposal_correct": n("reference_proposal_correct"),
        "table_failure_completed": completed - n("table_correct"),
        "joint_failure_completed": completed - n("joint_correct"),
        "unexecuted_or_incomplete": len(rows) - completed,
        "correct_input_table_degraded": sum(r["seed_kind"] == "correct_control" and r["status"] == "completed"
            and not r["metrics"]["table_correct"] for r in rows),
        "correct_input_joint_degraded": sum(r["seed_kind"] == "correct_control" and r["status"] == "completed"
            and not r["metrics"]["joint_correct"] for r in rows),
        "invalid_patch": n("invalid_patch"), "unchanged_table": n("unchanged_table"),
        "own_table_contradictions": sum(r["metrics"] is not None and r["metrics"]["own_table_consistent"] is False for r in rows),
        "cell_outcomes": dict(sum((Counter((r["metrics"] or {}).get("cell_outcomes") or {}) for r in rows), Counter())),
        "states": dict(Counter(r["validation_status"] for r in rows)),
        "categories": dict(Counter(c for r in rows for c in r["categories"]))}


def sol_trigger(rows):
    selected = [r for r in rows if r["seed_kind"] == "wrong" and r["representation"] == "patch"]
    repaired = sum(bool(r["metrics"] and r["metrics"]["table_correct"]) for r in selected)
    failed = [r for r in selected if r["status"] == "completed" and not r["metrics"]["table_correct"]]
    discrepancy = sum(r["metrics"]["reference_proposal_correct"] for r in failed)
    eligible = len(rows) == 72 and all(r["status"] == "completed" for r in rows) and len(selected) == 18
    return {"eligible": eligible, "patch_wrong_assigned": len(selected), "patch_wrong_table_correct": repaired,
        "patch_wrong_table_failures_completed": len(failed), "correct_proposal_wrong_table_failures": discrepancy,
        "below_half": repaired < 9, "discrepancy_strict_majority": 2 * discrepancy > len(failed),
        "triggered": eligible and repaired < 9 and 2 * discrepancy > len(failed),
        "action": "separate_Sol_preregistration_and_request_lock_required_before_any_call",
        "scientific_pass_or_cognitive_label": False, "Sol_calls_in_this_run": 0}


def analyze(m, b, report):
    done = {t["trial_id"]: t for t in report["trials"]}
    rows = [dict(p, status=done.get(p["trial_id"], {}).get("status", "unexecuted"),
        metrics=done.get(p["trial_id"], {}).get("metrics"),
        validation_status=done.get(p["trial_id"], {}).get("validation", {}).get("status", "unexecuted"),
        categories=done.get(p["trial_id"], {}).get("categories", ["incomplete"])) for p in b["plan"]]
    conditions = {feedback: {fmt: {kind: summary([r for r in rows if r["feedback"] == feedback
        and r["representation"] == fmt and r["seed_kind"] == kind]) for kind in ("wrong", "correct_control")}
        for fmt in ("rewrite", "patch")} for feedback in ("none", "local")}
    contrasts = {f: {metric: (conditions[f]["patch"]["wrong"][metric] - conditions[f]["rewrite"]["wrong"][metric]) / 9
        for metric in ("table_correct", "joint_correct")} for f in conditions}
    paired = []
    for seed in ("s00", "s05", "s07"):
        for kind in ("wrong", "correct_control"):
            for feedback in ("none", "local"):
                for repeat in range(3):
                    members = {r["representation"]: r for r in rows if (r["seed_id"], r["seed_kind"], r["feedback"], r["repeat"]) == (seed, kind, feedback, repeat)}
                    paired.append({"seed_id": seed, "seed_kind": kind, "feedback": feedback, "repeat": repeat,
                        "formats": members})
    per_rule = {cid: {f: {fmt: {kind: summary([r for r in rows if r["case_id"] == cid and r["feedback"] == f
        and r["representation"] == fmt and r["seed_kind"] == kind]) for kind in ("wrong", "correct_control")}
        for fmt in ("rewrite", "patch")} for f in conditions} for cid in ("case_281", "case_608")}
    equal_rule_rates = {f: {fmt: {kind: {metric: sum(per_rule[cid][f][fmt][kind][metric] /
        per_rule[cid][f][fmt][kind]["assigned"] for cid in per_rule) / 2 for metric in ("table_correct", "joint_correct")}
        for kind in ("wrong", "correct_control")} for fmt in ("rewrite", "patch")} for f in conditions}
    attempts = report["attempts"]
    known = [a for a in attempts if a.get("raw_response", {}).get("usage")]
    resources = {"attempts": len(attempts), "known_usage_attempts": len(known),
        "known_cost_usd_estimate": sum(a["cost_usd"] for a in known),
        "failed_or_unknown_usage_reserved_usd": sum(a["cost_usd"] for a in attempts if a not in known),
        "prompt_tokens": sum(a["raw_response"]["usage"]["prompt_tokens"] for a in known),
        "completion_tokens": sum(a["raw_response"]["usage"]["completion_tokens"] for a in known),
        "reasoning_tokens": sum((a["raw_response"]["usage"].get("completion_tokens_details") or {}).get("reasoning_tokens", 0) or 0 for a in known),
        "latency_seconds": sum(a.get("latency_seconds", 0) for a in attempts),
        "errors": dict(Counter(e for a in attempts for e in a["errors"]))}
    return {"assigned": 72, "conditions": conditions, "primary_patch_minus_rewrite": contrasts,
        "paired_outcomes": paired, "per_rule": per_rule, "equal_rule_rates": equal_rule_rates,
        "per_pattern": {sid: summary([r for r in rows if r["seed_id"] == sid]) for sid in ("s00", "s05", "s07")},
        "rows": rows, "all_failures": [r for r in rows if not (r["metrics"] or {}).get("joint_correct")],
        "resources": resources, "sol_reentry": sol_trigger(rows),
        "development_diagnostic": True, "independent_held_out": False, "overall_scientific_pass": None,
        "formal_trial_started": False, "old_scores_changed": False, "runtime_epsilon_gto_allowed": False,
        "adaptive_opponent_line_released": False}


class PatchClient:
    def __init__(self, client):
        self.client, self.runner = client, None
        self.chat = self.completions = self

    def create(self, **kwargs):
        r = self.runner; params = parameters(r.manifest, r.bundle, r.active_trial)
        r.report["attempts"][-1]["provider_parameters"] = deepcopy(params); r.persist()
        return self.client.chat.completions.create(messages=kwargs["messages"], **params)


class PatchRunner(SmokeRunner):
    def __init__(self, *args, halt_path, **kwargs):
        super().__init__(*args, **kwargs)
        self.halt_path = halt_path

    def run(self):
        self.report["schema_version"] = "aip-gamespec-patch-diagnostic-v12"
        self.persist()
        try:
            for p in self.bundle["plan"]:
                if self.halt_path.exists(): raise RuntimeError("global_oracle_stop")
                self.active_trial = p
                t = dict(p, status="started", attempt_ids=[]); self.report["trials"].append(t)
                try:
                    _, text, attempt = self.call(p["trial_id"], messages_for(self.manifest, self.bundle, p))
                finally:
                    t["attempt_ids"] = [a["attempt_id"] for a in self.report["attempts"] if a["trial_id"] == p["trial_id"]]
                t["raw_text"] = text
                try: t.update(evaluate(text, self.manifest, self.bundle, p, attempt["errors"]))
                except ValueError as error:
                    counterexample = {"trial_id": p["trial_id"], "raw_text": text, "error": str(error)}
                    self.report["oracle_counterexample"] = counterexample
                    write_json(self.halt_path, counterexample)
                    raise RuntimeError("independent_oracle_disagreement") from None
                t["status"] = "completed"; self.persist()
            self.report["status"] = "completed"
        except RuntimeError as error:
            self.report["status"], self.report["stop_reason"] = "stopped", str(error)
        self.report["analysis"] = analyze(self.manifest, self.bundle, self.report)
        self.persist()
        return self.report


def replay(m, b, report):
    if report["manifest_sha256"] != digest(m) or report["bundle_sha256"] != digest(b):
        raise ValueError("manifest/bundle changed")
    if report["model_requested"] != m["model"]["model_id"] or report["runtime_epsilon_gto_allowed"] or report["adaptive_opponent_line_released"]:
        raise ValueError("model/runtime authority changed")
    trials, attempts, plan = report["trials"], report["attempts"], b["plan"]
    if len(trials) > len(plan) or len(attempts) > len(trials): raise ValueError("excess dispatch")
    completed = 0
    for index, t in enumerate(trials):
        p = plan[index]
        if any(t.get(k) != v for k, v in p.items()): raise ValueError("assignment changed")
        ids = t["attempt_ids"]
        if ids not in ([], [index]): raise ValueError("attempt assignment changed")
        if not ids:
            if index != len(trials)-1 or t["status"] != "started": raise ValueError("missing attempt")
            continue
        a = attempts[index]
        if a["attempt_id"] != index or a["trial_id"] != p["trial_id"] or a["messages"] != messages_for(m, b, p) or a["provider_parameters"] != parameters(m, b, p):
            raise ValueError("request changed")
        model = m["model"]
        estimate = sum(len(msg["content"].encode()) + 10 for msg in a["messages"]) + 32
        if a["input_token_preflight"] != estimate: raise ValueError("input estimate changed")
        raw = a.get("raw_response"); usage = raw.get("usage") if raw else None
        expected_cost = (model["maximum_input_tokens"] * model["input_usd_per_million"] + model["maximum_output_tokens"] * model["output_usd_per_million"]) / 1e6
        if usage:
            expected_cost = (usage["prompt_tokens"] * model["input_usd_per_million"] + usage["completion_tokens"] * model["output_usd_per_million"]) / 1e6
        if abs(a["cost_usd"] - expected_cost) > 1e-12: raise ValueError("cost changed")
        if t["status"] != "completed":
            if index != len(trials)-1 or report["status"] != "stopped": raise ValueError("incomplete assignment")
            continue
        completed += 1
        if not raw or not usage or raw["model"] != model["model_id"] or a["resolved_model"] != raw["model"]:
            raise ValueError("model/usage changed")
        if usage["prompt_tokens"] > model["maximum_input_tokens"] or usage["completion_tokens"] > model["maximum_output_tokens"]:
            raise ValueError("usage exceeds frozen caps")
        choice = raw["choices"][0]; text = choice["message"]["content"] or ""
        if choice["message"].get("refusal"): raise ValueError("completed provider refusal")
        errors = [] if choice["finish_reason"] == "stop" else ["truncated_output" if choice["finish_reason"] == "length" else "provider_error"]
        try: json.loads(text, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
        except (ValueError, TypeError): errors.append("invalid_json")
        if a["errors"] != errors or text != t["raw_text"]: raise ValueError("raw text/errors changed")
        result = evaluate(text, m, b, p, errors)
        if any(t.get(k) != v for k, v in result.items()): raise ValueError("offline rescore changed")
    if report["status"] == "completed" and (completed != 72 or len(attempts) != 72): raise ValueError("completed run incomplete")
    analysis = analyze(m, b, report)
    if analysis != report["analysis"]: raise ValueError("analysis changed")
    return {"raw_rescoring_agrees": True, "analysis": analysis}
