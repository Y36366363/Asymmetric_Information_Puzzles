"""Typed proposals, oracle-free serialization and paired v4 interface checks."""
from collections import Counter
from copy import deepcopy
import json

from aip.benchmark.gamespec_smoke import SmokeRunner, digest
from aip.benchmark.gamespec_smoke_v2 import compile_v2
from aip.benchmark.gamespec_scope_ablation import evaluate_reply, strict_json


def clone_case(original, case_id, rename=None, rules=None):
    item = deepcopy(original)
    rename = rename or {}
    field = lambda k: rename.get(k, k)
    case = item["case"]
    case["case_id"] = case_id
    case["fields"] = {field(k): v for k, v in case["fields"].items()}
    if "reference_owners" in case:
        case["reference_owners"] = {field(k): v for k, v in case["reference_owners"].items()}
    for old, new in rename.items():
        case["rules"] = case["rules"].replace(old, new)
    if rules is not None:
        case["rules"] = rules
    if "control" in item:
        item["control"]["case_id"] = case_id
        item["control"]["required_witness"]["field"] = field(item["control"]["required_witness"]["field"])
    if "evidence" in item:
        e = item["evidence"]
        for group in ("feedback_evidence", "final_evidence"):
            for w in e[group]:
                for side in ("left_fields", "right_fields"):
                    w[side] = {field(k): v for k, v in w[side].items()}
        e["missing_truth_initial"]["game_id"] = case_id
        for c in e["missing_truth_initial"]["candidates"]:
            c["public_fields"] = [field(k) for k in c["public_fields"]]
            c["private_fields_by_player"] = {p: [field(k) for k in xs] for p, xs in c["private_fields_by_player"].items()}
    return item


def materialize(v3_manifest, v3_bundle, spec, tag):
    profile = next(p for p in spec["models"] if p["tag"] == tag)
    manifest = deepcopy(v3_manifest)
    manifest["manifest_id"] = spec["manifest_id"] + ":" + tag
    manifest["interface_spec"] = deepcopy(spec)
    manifest["model"].update(model_id=profile["id"], temperature=profile["temperature"],
                              reasoning_effort=profile["reasoning_effort"],
                              input_usd_per_million=profile["input_usd_per_million"],
                              output_usd_per_million=profile["output_usd_per_million"])
    manifest["schedule"] = {"maximum_calls": spec["schedule"]["trials_per_model"]}
    manifest["gates"] = {k: profile[k] for k in ("maximum_call_usd", "maximum_total_usd")}
    bundle = {"cases": deepcopy(v3_bundle["cases"]), "pairs": deepcopy(v3_manifest["ablation"]["pairs"])}
    probes = spec["sealed_bid_probes"]
    for name in ("renamed", "phase_wording"):
        p = probes[name]
        for side, original in (("static", "slice_29"), ("dynamic", "slice_74")):
            item = clone_case(bundle["cases"][original], p[side + "_id"], p.get("rename"), p.get(side + "_rules"))
            item["pair_id"] = "p3_" + name
            bundle["cases"][p[side + "_id"]] = item
    plan = []
    tasks = [("scope", v3_manifest["ablation"]["schedule"]["scope_case_order"], 2),
             ("witness_repair", [p["static_id"] for p in bundle["pairs"]], 2),
             ("surface_probe", [probes[n][s + "_id"] for n in ("renamed", "phase_wording") for s in ("static", "dynamic")], 1)]
    for task, ids, repeats in tasks:
        for index, case_id in enumerate(ids):
            for repeat in range(repeats):
                arms = spec["arms"]
                shift = (index + repeat) % len(arms)
                for arm in arms[shift:] + arms[:shift]:
                    plan.append({"trial_id": f"{task}:{case_id}:{repeat}:{arm['id']}", "task": task,
                                 "case_id": case_id, "repeat": repeat, "arm": arm["id"],
                                 "pair_id": bundle["cases"][case_id]["pair_id"]})
    bundle["plan"] = plan
    bundle["manifest_sha256"] = digest(manifest)
    return manifest, bundle


def proposal_schema(case):
    fields = {"type": "array", "items": {"type": "string", "enum": list(case["fields"])}}
    private = {"type": "object", "properties": {"player_0": fields, "player_1": fields},
               "required": ["player_0", "player_1"], "additionalProperties": False}
    candidate = {"type": "object", "properties": {"public_fields": fields, "private_fields_by_player": private},
                 "required": ["public_fields", "private_fields_by_player"], "additionalProperties": False}
    witness = {"type": "object", "properties": {
        "field": {"type": "string", "enum": list(case["fields"])},
        "player": {"type": "integer", "enum": [0, 1]},
        "before_visible": {"type": "boolean"}, "after_visible": {"type": "boolean"}},
        "required": ["field", "player", "before_visible", "after_visible"], "additionalProperties": False}
    return {"type": "object", "properties": {
        "decision": {"type": "string", "enum": ["candidate", "refusal"]},
        "candidates": {"type": "array", "items": candidate, "minItems": 0, "maxItems": 3},
        "witness": {"anyOf": [witness, {"type": "null"}]}},
        "required": ["decision", "candidates", "witness"], "additionalProperties": False}


def serialize_proposal(proposal, case):
    """No reference/evidence argument: never infer or repair a semantic choice."""
    if not isinstance(proposal, dict) or set(proposal) != {"decision", "candidates", "witness"}:
        raise ValueError("proposal keys")
    candidates, witness = proposal["candidates"], proposal["witness"]
    if not isinstance(candidates, list):
        raise ValueError("candidate array")
    if proposal["decision"] == "candidate":
        if witness is not None or not 1 <= len(candidates) <= 3:
            raise ValueError("mixed or empty candidate branch")
        canonical = []
        for i, c in enumerate(candidates):
            if not isinstance(c, dict) or set(c) != {"public_fields", "private_fields_by_player"}:
                raise ValueError("candidate keys")
            canonical.append(dict(c, hypothesis_id=f"candidate_{i}"))
        payload = {"schema_version": "aip-observation-gamespec-candidates-v1", "game_id": case["case_id"], "candidates": canonical}
        compile_v2(payload, case)  # Vocabulary, partitions, uniqueness; no rule oracle.
        return payload
    if proposal["decision"] != "refusal" or candidates or not isinstance(witness, dict):
        raise ValueError("refusal branch")
    if (set(witness) != {"field", "player", "before_visible", "after_visible"}
            or witness["field"] not in case["fields"] or type(witness["player"]) is not int
            or witness["player"] not in (0, 1) or type(witness["before_visible"]) is not bool
            or type(witness["after_visible"]) is not bool):
        raise ValueError("witness types or vocabulary")
    return {"schema_version": "aip-observation-refusal-v1", "game_id": case["case_id"],
            "status": "out_of_schema", "error_code": "OUT_OF_SCHEMA_STATIC_VISIBILITY", "witness": deepcopy(witness)}


def messages_for(manifest, bundle, trial):
    spec = manifest["interface_spec"]
    arm = next(a for a in spec["arms"] if a["id"] == trial["arm"])
    item = bundle["cases"][trial["case_id"]]
    case = item["case"]
    messages = [{"role": "system", "content": spec["system_prompt"] + (spec["source_priority_prompt"] if arm["source_priority"] else "")}]
    feedback = {}
    if trial["task"] == "witness_repair":
        initial = deepcopy(item["evidence"]["missing_truth_initial"]["candidates"])
        for c in initial:
            c.pop("hypothesis_id")
        messages.append({"role": "assistant", "content": json.dumps({"decision": "candidate", "candidates": initial, "witness": None}, sort_keys=True)})
        feedback = {"code": "STRUCTURE_OK", "witnesses": item["evidence"]["feedback_evidence"]}
    content = manifest["user_prompt_template"].format(case_id=case["case_id"], rules=case["rules"],
        fields_json=json.dumps(case["fields"], sort_keys=True), candidate_count="1 to 3", feedback_json=json.dumps(feedback, sort_keys=True))
    content += "\nProposal JSON schema: " + json.dumps(proposal_schema(case), sort_keys=True)
    return messages + [{"role": "user", "content": content}]


def parameters(manifest, bundle, trial):
    model = manifest["model"]
    arm = next(a for a in manifest["interface_spec"]["arms"] if a["id"] == trial["arm"])
    response_format = {"type": "json_object"}
    if arm["strict_schema"]:
        response_format = {"type": "json_schema", "json_schema": {"name": "observation_proposal", "strict": True,
                           "schema": proposal_schema(bundle["cases"][trial["case_id"]]["case"])}}
    params = {"model": model["model_id"], "response_format": response_format,
              "max_completion_tokens": model["maximum_output_tokens"], "store": False, "service_tier": "default"}
    if model["temperature"] is not None:
        params["temperature"] = model["temperature"]
    if model["reasoning_effort"] is not None:
        params["reasoning_effort"] = model["reasoning_effort"]
    return params


def evaluate(text, item, errors=()):
    try:
        payload = serialize_proposal(strict_json(text), item["case"])
        score = evaluate_reply(json.dumps(payload), item, errors)
        score["serialization_ok"] = True
    except (ValueError, TypeError, KeyError):
        score = evaluate_reply("null", item, errors)
        score["errors"] = sorted(set(score["errors"]) | {"proposal_contract_failure"})
        score["serialization_ok"] = False
    return score


def analyze(manifest, bundle, report):
    spec = manifest["interface_spec"]
    trials = {t["trial_id"]: t for t in report["trials"]}
    failures = []
    for p in bundle["plan"]:
        t = trials.get(p["trial_id"], {})
        if not t.get("evaluation", {}).get("correct", False):
            failures.append({"trial_id": p["trial_id"], "errors": t.get("evaluation", {}).get("errors", ["incomplete"])})
    cells = {}
    pair_results = {}
    for arm in spec["arms"]:
        arm_id = arm["id"]
        selected = [t for t in trials.values() if t["arm"] == arm_id and t["status"] == "completed"]
        cell = {}
        for task, kind, label, denominator in (("scope", "static", "static", 8), ("scope", "dynamic", "dynamic", 8),
                ("witness_repair", "static", "repair", 8), ("surface_probe", "static", "probe_static", 2), ("surface_probe", "dynamic", "probe_dynamic", 2)):
            rows = [t for t in selected if t["task"] == task and bundle["cases"][t["case_id"]]["kind"] == kind]
            cell[label] = {"correct": sum(t["evaluation"]["correct"] for t in rows), "completed": len(rows), "assigned": denominator}
        pair_rows = []
        for pair in bundle["pairs"]:
            joint = [all(trials.get(f"scope:{pair[s]}:{r}:{arm_id}", {}).get("evaluation", {}).get("correct", False)
                         for s in ("static_id", "dynamic_id")) for r in range(2)]
            pair_rows.append({"pair_id": pair["pair_id"], "joint_by_repeat": joint})
        cell["joint_pairs"] = {"correct": sum(sum(p["joint_by_repeat"]) for p in pair_rows), "assigned": 8}
        cell["feedback_exposures"] = sum(t["task"] == "witness_repair" for t in selected)
        cells[arm_id], pair_results[arm_id] = cell, pair_rows
    attempts = report["attempts"]
    return {"cells": cells, "pair_results": pair_results, "all_failures": failures,
            "error_counts": dict(Counter(e for t in trials.values() for e in t.get("evaluation", {}).get("errors", []))),
            "provider_attempts": len(attempts), "cost_usd": sum(a["cost_usd"] for a in attempts),
            "tokens": {k: sum((a.get("raw_response", {}).get("usage") or {}).get(k, 0) for a in attempts) for k in ("prompt_tokens", "completion_tokens")},
            "reasoning_tokens": sum(((a.get("raw_response", {}).get("usage") or {}).get("completion_tokens_details") or {}).get("reasoning_tokens", 0) or 0 for a in attempts),
            "latency_seconds": sum(a.get("latency_seconds", 0) for a in attempts),
            "scope_false_acceptances": sum(t.get("evaluation", {}).get("scope_false_acceptance", False) for t in trials.values()),
            "false_certifications_in_scope": sum(t.get("evaluation", {}).get("false_certification", False) for t in trials.values()),
            "overall_scientific_pass": None, "generalization_or_no_overfit_established": False,
            "semantic_vs_structural_effectiveness_established": False, "new_runtime_epsilon_gto_allowed": False,
            "adaptive_opponent_line_released": False, "uncertainty": spec["evaluation"]["uncertainty"]}


class ParameterClient:
    def __init__(self, client):
        self.client, self.runner = client, None
        self.chat = self.completions = self

    def create(self, **kwargs):
        runner = self.runner
        params = parameters(runner.manifest, runner.bundle, runner.active_trial)
        runner.report["attempts"][-1]["provider_parameters"] = deepcopy(params)
        runner.persist()  # Record actual settings before dispatch, including omitted temperature.
        return self.client.chat.completions.create(messages=kwargs["messages"], **params)


class InterfaceRunner(SmokeRunner):
    def run(self):
        self.report["schema_version"] = "aip-gamespec-interface-v4"
        self.persist()
        try:
            for p in self.bundle["plan"]:
                self.active_trial = p
                t = dict(p, status="started", attempt_ids=[])
                self.report["trials"].append(t)
                _, text, a = self.call(t["trial_id"], messages_for(self.manifest, self.bundle, t))
                t["attempt_ids"] = [a["attempt_id"]]
                t["evaluation"] = evaluate(text, self.bundle["cases"][t["case_id"]], a["errors"])
                t["status"] = "completed"
                self.persist()
            self.report["status"] = "completed"
        except RuntimeError as e:
            self.report["status"], self.report["stop_reason"] = "stopped", str(e)
        self.report["analysis"] = analyze(self.manifest, self.bundle, self.report)
        self.persist()
        return self.report


def replay(manifest, bundle, report):
    if (report["manifest_sha256"] != digest(manifest) or report["bundle_sha256"] != digest(bundle)
            or [t["trial_id"] for t in report["trials"]] != [p["trial_id"] for p in bundle["plan"][:len(report["trials"])]]):
        raise ValueError("frozen plan mismatch")
    used_attempts = set()
    for expected, t in zip(bundle["plan"], report["trials"]):
        if any(t[k] != v for k, v in expected.items()):
            raise ValueError("trial assignment mismatch")
        if t["status"] != "completed":
            continue
        if len(t["attempt_ids"]) != 1:
            raise ValueError("reply budget")
        index = t["attempt_ids"][0]
        if index in used_attempts:
            raise ValueError("reused attempt")
        used_attempts.add(index)
        a = report["attempts"][index]
        if a["attempt_id"] != index or a["trial_id"] != t["trial_id"]:
            raise ValueError("attempt assignment mismatch")
        if a["messages"] != messages_for(manifest, bundle, t) or a["provider_parameters"] != parameters(manifest, bundle, t):
            raise ValueError("actual request mismatch")
        raw = a["raw_response"]
        if raw["model"] != manifest["model"]["model_id"]:
            raise ValueError("model mismatch")
        u, m = raw["usage"], manifest["model"]
        if u["prompt_tokens"] > m["maximum_input_tokens"] or u["completion_tokens"] > m["maximum_output_tokens"]:
            raise ValueError("usage cap mismatch")
        cost = (u["prompt_tokens"] * m["input_usd_per_million"] + u["completion_tokens"] * m["output_usd_per_million"]) / 1e6
        if abs(cost - a["cost_usd"]) > 1e-12:
            raise ValueError("cost mismatch")
        choice = raw["choices"][0]
        errors = [] if choice["finish_reason"] == "stop" else ["truncated_output" if choice["finish_reason"] == "length" else "provider_error"]
        try:
            json.loads(choice["message"]["content"] or "", parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
        except (ValueError, TypeError):
            errors.append("invalid_json")
        if evaluate(choice["message"]["content"] or "", bundle["cases"][t["case_id"]], errors) != t["evaluation"]:
            raise ValueError("raw evaluation mismatch")
    if report["status"] == "completed" and (len(report["trials"]) != len(bundle["plan"]) or len(used_attempts) != len(report["attempts"])):
        raise ValueError("incomplete schedule")
    analysis = analyze(manifest, bundle, report)
    if analysis != report["analysis"]:
        raise ValueError("summary mismatch")
    return analysis
