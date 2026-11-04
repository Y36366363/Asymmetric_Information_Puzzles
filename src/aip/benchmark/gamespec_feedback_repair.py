"""Frozen-seed feedback diagnostic; truth never enters local feedback generation."""
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json

from aip.benchmark.gamespec_attribution import (
    messages_for as old_messages, parameters as old_parameters, normalize_table, output_schema,
)
from aip.benchmark.gamespec_local_checks import check_local
from aip.benchmark.gamespec_prospective import change_witnesses
from aip.benchmark.gamespec_smoke import SmokeRunner, digest, write_json
from aip.benchmark.gamespec_validation import verify_frozen_output


ARMS = ("none", "local", "semantic")
KINDS = ("wrong", "correct_control")


def catalog(bundle, audit, raw):
    rows = sorted((r for r in audit["rows"] if r["requires_semantic_reference_to_resolve"]),
                  key=lambda r: (r["case_id"], r["condition"], r["repeat"]))
    trials = {t["trial_id"]: t for t in raw["trials"]}
    seeds = {}
    for index, row in enumerate(rows):
        if row["model"] != "luna6" or row["local"]["status"] != "locally_consistent_unverified":
            raise ValueError("unexpected seed provenance")
        t = trials[row["trial_id"]]
        attempt = raw["attempts"][t["attempt_ids"][0]]
        text = attempt["raw_response"]["choices"][0]["message"]["content"]
        table = json.loads(text)["stage_table"]
        item = bundle["cases"][row["case_id"]]; fields = tuple(item["case"]["fields"])
        canonical = normalize_table(table, fields)
        if canonical == normalize_table(item["visibility_contexts"], fields) or row["reference_table_correct"]:
            raise ValueError("seed must be reference wrong")
        if check_local(fields, table=table)["status"] != "locally_consistent_unverified":
            raise ValueError("seed must be locally consistent")
        # Match original ordering for shared fields, without aliases between cells.
        correct = [[[f for f in table[phase][player] if f in reference] +
                    [f for f in fields if f in reference and f not in table[phase][player]]
                    for player, reference in enumerate(views)]
                   for phase, views in enumerate(item["visibility_contexts"])]
        seed_id = f"s{index:02d}"
        seeds[seed_id] = {"seed_id": seed_id, "case_id": row["case_id"],
            "source_model": row["model"], "source_trial_id": row["trial_id"],
            "source_condition": row["condition"], "source_repeat": row["repeat"],
            "raw_reply_sha256": sha256(text.encode()).hexdigest(), "original_table": deepcopy(table),
            "correct_control": correct, "canonical_pattern": row["case_id"] + ":" + digest(canonical)}
    groups = Counter(s["canonical_pattern"] for s in seeds.values())
    counts = Counter((s["case_id"], s["source_condition"]) for s in seeds.values())
    if len(seeds) != 12 or len(groups) != 3 or sorted(groups.values()) != [2, 5, 5] or counts != {
        ("case_281", "B"): 5, ("case_608", "B"): 5, ("case_608", "C"): 2}:
        raise ValueError("frozen twelve-seed population changed")
    return seeds


def evidence_registry(spec, cases):
    registry = {}
    for case_id, quotes in spec["evidence_registry"]["excerpts"].items():
        rules = cases[case_id]["case"]["rules"]
        entries = []
        for quote in quotes:
            if rules.count(quote) != 1: raise ValueError("excerpt must uniquely match frozen rule")
            start = rules.index(quote)
            entries.append({"source_id": spec["evidence_registry"]["source_id"], "case_id": case_id,
                "rule_sha256": sha256(rules.encode()).hexdigest(), "start": start,
                "end": start + len(quote), "quote": quote})
        registry[case_id] = entries
    return registry


def local_feedback(fields, table):
    """No rule, reference, semantic verdict or case-type parameter is accepted."""
    result = check_local(fields, table=table)
    try: changes = change_witnesses(normalize_table(table, fields))
    except ValueError: changes = None
    return {"code": "LOCAL_CONSISTENCY_ONLY", "status": result["status"],
        "semantic_result": "not_assessed", "violations": result["violations"],
        "checks": ["two phases and two players", "field vocabulary and no duplicates",
                   "each field observed by at least one player per phase under the three-owner contract"],
        "declared_transitions": changes,
        "transition_scope": "Describes only the proposed table; correctness against RULES is not assessed."}


def materialize(old_manifest, old_bundle, spec, audit, raw):
    m, b = deepcopy(old_manifest), deepcopy(old_bundle)
    if spec["schedule"]["maximum_generation_calls"] != 144 or spec["schedule"]["maximum_repair_rounds"] != 1:
        raise ValueError("fixed single-round 144-call design required")
    b["seeds"] = catalog(b, audit, raw)
    b["evidence_registry"] = evidence_registry(spec, b["cases"])
    m["manifest_id"] = spec["manifest_id"] + ":" + m["model"]["model_id"]
    m["repair_spec"] = deepcopy(spec)
    m["schedule"] = {"maximum_calls": 72}
    b["plan"] = []
    for index, (seed_id, seed) in enumerate(b["seeds"].items()):
        kinds = KINDS if index % 2 == 0 else KINDS[::-1]
        for kind_index, kind in enumerate(kinds):
            shift = (index + kind_index) % 3
            for arm in ARMS[shift:] + ARMS[:shift]:
                b["plan"].append({"trial_id": f"{seed_id}:{kind}:{arm}", "seed_id": seed_id,
                    "case_id": seed["case_id"], "seed_kind": kind, "feedback_arm": arm,
                    "condition": "C", "task": "scope", "arm": "f1_s1"})
    b["manifest_sha256"] = digest(m)
    return m, b


def proposed_table(bundle, trial):
    seed = bundle["seeds"][trial["seed_id"]]
    return seed["original_table"] if trial["seed_kind"] == "wrong" else seed["correct_control"]


def feedback_for(bundle, trial):
    if trial["feedback_arm"] == "none": return None
    case = bundle["cases"][trial["case_id"]]["case"]
    feedback = local_feedback(tuple(case["fields"]), proposed_table(bundle, trial))
    if trial["feedback_arm"] == "semantic":
        feedback["rule_excerpts"] = deepcopy(bundle["evidence_registry"][trial["case_id"]])
    return feedback


def messages_for(manifest, bundle, trial):
    case = bundle["cases"][trial["case_id"]]["case"]
    system = old_messages(manifest, bundle, trial)[0]
    task = manifest["repair_spec"]["interface"]["common_user_instruction"]
    content = ("RULES:\n" + case["rules"] + "\nFIELDS: " + json.dumps(case["fields"], sort_keys=True)
        + "\n" + task + "\nFEEDBACK: " + json.dumps(feedback_for(bundle, trial), sort_keys=True)
        + "\nProposal JSON schema: " + json.dumps(output_schema(manifest, case, "C"), sort_keys=True))
    return [system, {"role": "assistant", "content": json.dumps({"stage_table": proposed_table(bundle, trial)})},
            {"role": "user", "content": content}]


def parameters(manifest, bundle, trial):
    return old_parameters(manifest, bundle, trial)


class RepairClient:
    def __init__(self, client):
        self.client, self.runner = client, None
        self.chat = self.completions = self

    def create(self, **kwargs):
        r = self.runner
        params = parameters(r.manifest, r.bundle, r.active_trial)
        r.report["attempts"][-1]["provider_parameters"] = deepcopy(params)
        r.persist()
        return self.client.chat.completions.create(messages=kwargs["messages"], **params)


def cell_errors(table, item):
    fields = tuple(item["case"]["fields"])
    actual = normalize_table(table, fields); reference = normalize_table(item["visibility_contexts"], fields)
    return sum(len(set(a) ^ set(r)) for av, rv in zip(actual, reference) for a, r in zip(av, rv))


def evaluate(text, manifest, bundle, trial, errors=()):
    item = bundle["cases"][trial["case_id"]]
    record, local, _, e = verify_frozen_output(text, "C", item, errors)
    after = e["normalized_stage_table"]
    return {"evaluation": e, "validation": record.to_artifact(), "local": local,
        "metrics": {"input_cell_errors": cell_errors(proposed_table(bundle, trial), item),
            "output_cell_errors": cell_errors(after, item) if after is not None else None,
            "table_correct": e["table_correct"], "joint_correct": e["whole_response_correct"],
            "repair_rounds": 1,
            "successful_repair_round": 1 if trial["seed_kind"] == "wrong" and e["whole_response_correct"] else None}}


def analyze(manifest, bundle, report):
    done = {t["trial_id"]: t for t in report["trials"]}
    rows = []
    for p in bundle["plan"]:
        t = done.get(p["trial_id"], {}); e = t.get("evaluation")
        valid = bool(e and e["table_structurally_valid"] and e["legacy"]["serialization_ok"]
                     and not e["interface_errors"] and not e["transport_errors"])
        rows.append(dict(p, canonical_pattern=bundle["seeds"][p["seed_id"]]["canonical_pattern"],
            status=t.get("status", "unexecuted"), valid_completed=valid,
            table_correct=bool(e and e["table_correct"]), joint_correct=bool(e and e["whole_response_correct"]),
            validation_status=(t.get("validation") or {}).get("status"),
            categories=e["categories"] if e else ["incomplete"],
            table_cell_differences=e["table_cell_differences"] if e else [],
            metrics=t.get("metrics"), raw_text=t.get("raw_text")))

    def summary(picked):
        completed = [r for r in picked if r["status"] == "completed"]
        valid = [r for r in picked if r["valid_completed"]]
        return {"assigned": len(picked), "completed": len(completed), "valid_completed": len(valid),
            "table_correct": sum(r["table_correct"] for r in picked),
            "joint_correct": sum(r["joint_correct"] for r in picked),
            "valid_table_correct": sum(r["table_correct"] for r in valid),
            "valid_joint_correct": sum(r["joint_correct"] for r in valid),
            "incorrect_table_completed": sum(not r["table_correct"] for r in completed),
            "incorrect_joint_completed": sum(not r["joint_correct"] for r in completed),
            "semantic_table_degradation_valid_subset": sum(not r["table_correct"] for r in valid),
            "semantic_joint_degradation_valid_subset": sum(not r["joint_correct"] for r in valid),
            "states": {s: sum(r["validation_status"] == s for r in picked)
                for s in ("reject_local", "locally_consistent_unverified", "verified")},
            "category_counts": dict(Counter(c for r in picked for c in r["categories"]))}

    summaries = {arm: {kind: summary([r for r in rows if r["feedback_arm"] == arm and r["seed_kind"] == kind])
                       for kind in KINDS} for arm in ARMS}
    matched = []
    for seed_id, seed in bundle["seeds"].items():
        for kind in KINDS:
            arms = {r["feedback_arm"]: r for r in rows if r["seed_id"] == seed_id and r["seed_kind"] == kind}
            matched.append({"seed_id": seed_id, "case_id": seed["case_id"], "seed_kind": kind,
                "arms": {a: {k: r[k] for k in ("status", "table_correct", "joint_correct")} for a, r in arms.items()}})
    cross = {metric: {"local_fail_semantic_success": [r for r in matched
                if not r["arms"]["local"][metric] and r["arms"]["semantic"][metric]],
            "semantic_fail_local_success": [r for r in matched
                if not r["arms"]["semantic"][metric] and r["arms"]["local"][metric]]}
             for metric in ("table_correct", "joint_correct")}
    group_rates = {}
    for group_name in ("canonical_pattern", "case_id"):
        groups = sorted({r[group_name] for r in rows if r["seed_kind"] == "wrong"})
        group_rates[group_name] = {arm: {metric: sum(
            sum(r[metric] for r in rows if r["seed_kind"] == "wrong" and r["feedback_arm"] == arm and r[group_name] == g)
            / sum(r["seed_kind"] == "wrong" and r["feedback_arm"] == arm and r[group_name] == g for r in rows)
            for g in groups) / len(groups) for metric in ("table_correct", "joint_correct")} for arm in ARMS}
    attempts = report["attempts"]
    return {"conditions": summaries, "rows": rows, "matched_outcomes": matched, "cross_checks": cross,
        "equal_group_rates": group_rates,
        "per_rule": {case: {arm: {kind: summary([r for r in rows if r["case_id"] == case and
                    r["feedback_arm"] == arm and r["seed_kind"] == kind]) for kind in KINDS} for arm in ARMS}
                     for case in ("case_281", "case_608")},
        "semantic_minus_local_joint_repair": (summaries["semantic"]["wrong"]["joint_correct"] - summaries["local"]["wrong"]["joint_correct"]) / 12,
        "semantic_minus_local_table_repair": (summaries["semantic"]["wrong"]["table_correct"] - summaries["local"]["wrong"]["table_correct"]) / 12,
        "all_failures": [r for r in rows if not r["joint_correct"]],
        "resources": {"attempts": len(attempts), "cost_usd_estimate": sum(a["cost_usd"] for a in attempts),
            "unknown_usage_attempts": sum(not a.get("raw_response", {}).get("usage") for a in attempts),
            "tokens": {k: sum((a.get("raw_response", {}).get("usage") or {}).get(k, 0) for a in attempts)
                       for k in ("prompt_tokens", "completion_tokens")},
            "reasoning_tokens": sum(((a.get("raw_response", {}).get("usage") or {}).get("completion_tokens_details") or {}).get("reasoning_tokens", 0) or 0 for a in attempts),
            "latency_seconds": sum(a.get("latency_seconds", 0) for a in attempts),
            "errors": dict(Counter(e for a in attempts for e in a["errors"]))},
        "units": {"provenance_seeds": 12, "wrong_patterns": 3, "rule_instances": 2,
                  "correct_reference_patterns": 2},
        "overall_scientific_pass": None, "development_diagnostic": True, "independent_held_out": False,
        "old_A_latent_error_layer_identified": False, "old_scores_changed": False,
        "formal_trial_started": False, "new_runtime_epsilon_gto_allowed": False,
        "adaptive_opponent_line_released": False}


class RepairRunner(SmokeRunner):
    def __init__(self, *args, halt_path, **kwargs):
        super().__init__(*args, **kwargs)
        self.halt_path = halt_path

    def run(self):
        self.report["schema_version"] = "aip-gamespec-feedback-repair-v11"
        self.persist()
        try:
            for p in self.bundle["plan"]:
                if self.halt_path.exists(): raise RuntimeError("global_oracle_stop")
                self.active_trial = p
                trial = dict(p, status="started", attempt_ids=[])
                self.report["trials"].append(trial)
                try:
                    _, text, a = self.call(p["trial_id"], messages_for(self.manifest, self.bundle, p))
                finally:
                    trial["attempt_ids"] = [a["attempt_id"] for a in self.report["attempts"] if a["trial_id"] == p["trial_id"]]
                trial["raw_text"] = text
                try: result = evaluate(text, self.manifest, self.bundle, p, a["errors"])
                except ValueError as error:
                    counterexample = {"trial_id": p["trial_id"], "raw_text": text, "error": str(error)}
                    self.report["oracle_counterexample"] = counterexample
                    write_json(self.halt_path, counterexample)
                    raise RuntimeError("independent_oracle_disagreement") from None
                trial.update(result, status="completed")
                self.persist()
            self.report["status"] = "completed"
        except RuntimeError as error:
            self.report["status"], self.report["stop_reason"] = "stopped", str(error)
        self.report["analysis"] = analyze(self.manifest, self.bundle, self.report)
        self.persist()
        return self.report


def replay(manifest, bundle, report):
    if report["manifest_sha256"] != digest(manifest) or report["bundle_sha256"] != digest(bundle):
        raise ValueError("manifest/bundle changed")
    plan = bundle["plan"]
    if len(report["trials"]) > len(plan) or len(report["attempts"]) > len(plan): raise ValueError("excess calls")
    used = set()
    for p, t in zip(plan, report["trials"]):
        if any(t[k] != v for k, v in p.items()): raise ValueError("assignment changed")
        if t["status"] != "completed": continue
        if len(t["attempt_ids"]) != 1: raise ValueError("one reply only")
        i = t["attempt_ids"][0]
        if i in used: raise ValueError("attempt reused")
        used.add(i); a = report["attempts"][i]; raw = a["raw_response"]
        choice = raw["choices"][0]; text = choice["message"]["content"] or ""
        errors = [] if choice["finish_reason"] == "stop" else ["truncated_output" if choice["finish_reason"] == "length" else "provider_error"]
        try: json.loads(text, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
        except (ValueError, TypeError): errors.append("invalid_json")
        model, usage = manifest["model"], raw["usage"]
        if raw["model"] != model["model_id"] or any(usage[k] > model[cap] for k, cap in (
                ("prompt_tokens", "maximum_input_tokens"), ("completion_tokens", "maximum_output_tokens"))):
            raise ValueError("model or usage changed")
        cost = (usage["prompt_tokens"] * model["input_usd_per_million"] + usage["completion_tokens"] * model["output_usd_per_million"]) / 1e6
        if text != t["raw_text"] or errors != a["errors"] or abs(cost - a["cost_usd"]) > 1e-12:
            raise ValueError("raw text, transport labels or cost changed")
        result = evaluate(text, manifest, bundle, p, errors)
        if any(t[k] != v for k, v in result.items()): raise ValueError("offline rescore changed")
    assigned = {p["trial_id"]: p for p in plan}
    for i, a in enumerate(report["attempts"]):
        p = assigned.get(a["trial_id"])
        if p is None or a["attempt_id"] != i or a["messages"] != messages_for(manifest, bundle, p) or a["provider_parameters"] != parameters(manifest, bundle, p):
            raise ValueError("request changed or unassigned")
    if report["status"] == "completed" and (len(used) != len(plan) or len(report["trials"]) != len(plan)):
        raise ValueError("completed report incomplete")
    analysis = analyze(manifest, bundle, report)
    if analysis != report["analysis"]: raise ValueError("analysis changed")
    return {"raw_rescoring_agrees": True, "analysis": analysis}
