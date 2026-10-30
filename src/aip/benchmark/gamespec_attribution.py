"""Frozen-reference attribution: rule -> stage table -> legacy proposal.

No new truth labels, no edits to the legacy serializer or its two evaluators.
"""
from collections import Counter
from copy import deepcopy
from itertools import product
import json

from aip.benchmark.gamespec_boundary_panel import failure_categories, partition_proposal
from aip.benchmark.gamespec_interface import (messages_for as legacy_messages, parameters as legacy_parameters,
    proposal_schema, serialize_proposal)
from aip.benchmark.gamespec_prospective import change_witnesses, score, table_oracle
from aip.benchmark.gamespec_scope_ablation import strict_json
from aip.benchmark.gamespec_smoke import SmokeRunner, digest, write_json


def materialize(old_manifest, old_bundle, spec):
    if spec["schedule"]["repeats"]!=5 or spec["schedule"]["conditions"]!=["A","B","C"]:
        raise ValueError("exactly five repeats of A/B/C required")
    if spec["schedule"]["trials_per_model"]!=180 or spec["schedule"]["maximum_generation_calls"]!=360:
        raise ValueError("fixed two-model budget required")
    m, b = deepcopy(old_manifest), deepcopy(old_bundle)
    m["manifest_id"] = spec["manifest_id"] + ":" + m["model"]["model_id"]
    m["attribution_spec"] = deepcopy(spec)
    m["schedule"] = {"maximum_calls": spec["schedule"]["trials_per_model"]}
    b["plan"] = []
    ids = old_manifest["prospective_spec"]["schedule"]["scope_case_order"]
    for i, case_id in enumerate(ids):
        for repeat in range(spec["schedule"]["repeats"]):
            conditions = spec["schedule"]["conditions"]
            shift = (i + repeat) % len(conditions)
            for condition in conditions[shift:] + conditions[:shift]:
                b["plan"].append({"trial_id": f"{condition}:{case_id}:{repeat}", "condition": condition,
                    "case_id": case_id, "repeat": repeat, "pair_id": b["cases"][case_id]["pair_id"],
                    "task": "scope", "arm": "f1_s1"})
    if len(b["plan"]) != spec["schedule"]["trials_per_model"]:
        raise ValueError("assigned attribution budget mismatch")
    b["manifest_sha256"] = digest(m)
    b["frozen_reference_sha256"] = digest(b["cases"])
    return m, b


def output_schema(manifest, case, condition):
    if condition == "A": return proposal_schema(case)
    table = deepcopy(manifest["attribution_spec"]["interface"]["stage_table_schema_template"])
    table["items"]["items"]["items"]["enum"] = list(case["fields"])
    table["items"]["items"]["maxItems"] = len(case["fields"])
    props = {"stage_table": table}
    if condition == "C": props["proposal"] = proposal_schema(case)
    return {"type":"object", "properties":props, "required":list(props), "additionalProperties":False}


def messages_for(manifest, bundle, trial):
    messages = legacy_messages(manifest, bundle, trial)
    if trial["condition"] == "A": return messages
    prefix, _ = messages[-1]["content"].rsplit("\nProposal JSON schema: ", 1)
    instruction = manifest["attribution_spec"]["conditions"][trial["condition"]]["task_instruction"]
    schema = output_schema(manifest, bundle["cases"][trial["case_id"]]["case"], trial["condition"])
    messages[-1]["content"] = prefix + "\n" + instruction + "\nProposal JSON schema: " + json.dumps(schema)
    return messages


def parameters(manifest, bundle, trial):
    params = legacy_parameters(manifest, bundle, trial)
    if trial["condition"] != "A":
        params["response_format"]["json_schema"]["schema"] = output_schema(
            manifest, bundle["cases"][trial["case_id"]]["case"], trial["condition"])
    return params


class AttributionClient:
    def __init__(self, client):
        self.client, self.runner = client, None
        self.chat = self.completions = self

    def create(self, **kwargs):
        r = self.runner
        params = parameters(r.manifest, r.bundle, r.active_trial)
        r.report["attempts"][-1]["provider_parameters"] = deepcopy(params)
        r.persist()
        return self.client.chat.completions.create(messages=kwargs["messages"], **params)


def normalize_table(table, fields):
    if not isinstance(table, list) or len(table) != 2:
        raise ValueError("two phases required")
    result = []
    for phase in table:
        if not isinstance(phase, list) or len(phase) != 2:
            raise ValueError("two players per phase required")
        row = []
        for view in phase:
            if (not isinstance(view, list) or any(not isinstance(f,str) for f in view)
                    or len(view) != len(set(view)) or not set(view) <= set(fields)):
                raise ValueError("field vocabulary or duplicates")
            row.append(sorted(view))
        result.append(row)
    return result


def derive_proposal(table, fields):
    """Reference-free deterministic derivation; no reference argument or fallback."""
    table = normalize_table(table, fields)
    changes = change_witnesses(table)
    if changes:
        return {"decision":"refusal", "candidates":[], "witness":changes[0]}
    owners = {}
    for f in fields:
        visibility = (f in table[0][0], f in table[0][1])
        if visibility == (False, False):
            raise ValueError("constant never-visible field is outside three-owner language")
        owners[f] = "public" if all(visibility) else "player_0" if visibility[0] else "player_1"
    return partition_proposal(owners)


def evaluate(text, condition, item, transport_errors=()):
    errors = list(transport_errors)
    interface_errors, table_errors = [], []
    proposal = table = normalized = None
    try:
        payload = strict_json(text)
    except (ValueError, TypeError):
        payload = None
        interface_errors.append("invalid_json")
    if condition == "A":
        proposal = payload
    else:
        keys = {"stage_table"} if condition == "B" else {"stage_table", "proposal"}
        if not isinstance(payload, dict) or set(payload) != keys:
            interface_errors.append("output_contract_failure")
        if isinstance(payload, dict):
            table = payload.get("stage_table")
            if condition == "C": proposal = payload.get("proposal")
        try:
            normalized = normalize_table(table, item["case"]["fields"])
        except ValueError:
            interface_errors.append("stage_table_contract_failure")
        if condition == "B" and normalized is not None:
            try:
                proposal = derive_proposal(normalized, item["case"]["fields"])
            except ValueError:
                table_errors.append("deterministic_export_failure")
    ref = normalize_table(item["visibility_contexts"], item["case"]["fields"])
    differences = []
    if normalized is not None:
        for phase, player in product(range(2), range(2)):
            actual, expected = set(normalized[phase][player]), set(ref[phase][player])
            if actual != expected:
                differences.append({"phase":phase, "player":player,
                    "missing_fields":sorted(expected-actual), "extra_fields":sorted(actual-expected)})
    matches = normalized == ref if condition != "A" else None
    table_correct = bool(matches and not interface_errors and not errors) if condition != "A" else None
    # The legacy endpoint is identical for all three conditions. Table mismatch is
    # a separate target and never silently changes this endpoint.
    legacy = score(json.dumps(proposal), item, errors + (["output_contract_failure"] if "output_contract_failure" in interface_errors else []))
    self_consistent = None
    if normalized is not None and proposal is not None and legacy["serialization_ok"]:
        own = {"kind":"dynamic" if change_witnesses(normalized) else "static", "visibility_contexts":normalized}
        self_consistent = table_oracle(json.dumps(proposal), own)
    categories = set(interface_errors + table_errors)
    if condition != "A" and normalized is not None and not matches:
        categories.add("stage_table_mismatch")
    if not legacy["serialization_ok"]:
        categories.add("output_contract_failure")
    elif not legacy["correct"] and not errors:
        categories.update(failure_categories(proposal, item))
    if self_consistent is False: categories.add("proposal_inconsistent_with_own_table")
    if table_correct and item["kind"] == "dynamic" and not legacy["correct"]:
        categories.add("correct_table_wrong_witness")
    if condition != "A" and normalized is not None and not matches and legacy["correct"]:
        categories.add("wrong_table_correct_reference_proposal")
    if "truncated_output" in errors: categories.add("truncated_output")
    if set(errors) - {"truncated_output","invalid_json"}: categories.add("transport_error")
    if "invalid_json" in errors: categories.add("invalid_json")
    return {"legacy":legacy, "table_correct":table_correct, "table_matches_reference":matches,
        "table_structurally_valid":normalized is not None if condition != "A" else None,
        "normalized_stage_table":normalized, "table_cell_differences":differences,
        "proposal":proposal, "proposal_consistent_with_own_table":self_consistent,
        "whole_response_correct":bool(legacy["correct"] and not interface_errors and
            (condition == "A" or table_correct)),
        "stage_table_precedes_proposal":list(payload)==["stage_table","proposal"] if condition=="C" and isinstance(payload,dict) else None,
        "categories":sorted(categories), "interface_errors":sorted(set(interface_errors)),
        "transport_errors":errors}


def rate(numerator, denominator):
    return {"numerator":numerator, "denominator":denominator,
            "rate":numerator/denominator if denominator else None}


def analyze(manifest, bundle, report):
    trials = {t["trial_id"]:t for t in report["trials"]}
    rows = []
    for p in bundle["plan"]:
        t = trials.get(p["trial_id"], {})
        e = t.get("evaluation", {})
        rows.append(dict(p, kind=bundle["cases"][p["case_id"]]["kind"], status=t.get("status","unexecuted"),
            legacy_correct=e.get("legacy",{}).get("correct",False), table_correct=e.get("table_correct"),
            table_valid=e.get("table_structurally_valid"), serialization_ok=e.get("legacy",{}).get("serialization_ok",False),
            self_consistent=e.get("proposal_consistent_with_own_table"),
            whole_response_correct=e.get("whole_response_correct",False),
            categories=e.get("categories",["incomplete"]), interface_errors=e.get("interface_errors",[])))
    by_condition = {}
    for c in ("A","B","C"):
        picked = [r for r in rows if r["condition"] == c]
        d = [r for r in picked if r["kind"] == "dynamic"]
        s = [r for r in picked if r["kind"] == "static"]
        ct = [r for r in d if r["table_correct"]]
        bad_export = [r for r in ct if not r["legacy_correct"]]
        clean_export = [r for r in ct if r["serialization_ok"] and not r["interface_errors"]]
        ca = [a for a in report["attempts"] if a["trial_id"].startswith(c+":")]
        by_condition[c] = {"completed":sum(r["status"]=="completed" for r in picked), "assigned":len(picked),
            "dynamic_witness_correct":rate(sum(r["legacy_correct"] for r in d),len(d)),
            "static_correct":rate(sum(r["legacy_correct"] for r in s),len(s)),
            "table_correct_all":rate(sum(bool(r["table_correct"]) for r in picked),len(picked)) if c!="A" else None,
            "table_correct_dynamic":rate(sum(bool(r["table_correct"]) for r in d),len(d)) if c!="A" else None,
            "correct_table_wrong_witness_conditional":rate(len(bad_export),len(ct)) if c!="A" else None,
            "correct_table_wrong_witness_assigned":rate(len(bad_export),len(d)) if c!="A" else None,
            "correct_table_valid_proposal_wrong_witness":rate(sum(not r["legacy_correct"] for r in clean_export),len(clean_export)) if c!="A" else None,
            "table_proposal_cross_tab":dict(Counter(f"table_{bool(r['table_correct'])}_proposal_{r['legacy_correct']}" for r in picked)) if c!="A" else None,
            "whole_response_correct":rate(sum(r["whole_response_correct"] for r in picked),len(picked)),
            "resources":{"cost_usd_estimate":sum(a["cost_usd"] for a in ca),
                "tokens":{k:sum((a.get("raw_response",{}).get("usage") or {}).get(k,0) for a in ca) for k in ("prompt_tokens","completion_tokens")},
                "latency_seconds":sum(a.get("latency_seconds",0) for a in ca),
                "transport_error_counts":dict(Counter(e for a in ca for e in a["errors"]))},
            "interface_error_trials":sum(bool(r["interface_errors"]) or not r["serialization_ok"] for r in picked if r["status"]=="completed")}
    lookup = {(r["case_id"],r["repeat"],r["condition"]):r for r in rows}
    discordance = []
    instances = []
    for case_id,item in bundle["cases"].items():
        metrics = {}
        for c in ("A","B","C"):
            selected = [r for r in rows if r["case_id"]==case_id and r["condition"]==c]
            metrics[c] = {"legacy_correct":sum(r["legacy_correct"] for r in selected),
                "table_correct":sum(bool(r["table_correct"]) for r in selected) if c!="A" else None,
                "assigned":len(selected)}
        instances.append({"case_id":case_id,"pair_id":item["pair_id"],"kind":item["kind"],"conditions":metrics})
        for repeat in range(manifest["attribution_spec"]["schedule"]["repeats"]):
            a,b = (lookup[case_id,repeat,c] for c in ("A","B"))
            if not a["legacy_correct"] and b["legacy_correct"]:
                discordance.append({"case_id":case_id,"kind":item["kind"],"repeat":repeat,
                    "A_status":a["status"],"B_table_correct":b["table_correct"],
                    "B_correct_with_correct_table":bool(b["table_correct"]),
                    "A_categories":a["categories"]})
    attempts = report["attempts"]
    return {"conditions":by_condition, "instances":instances, "A_wrong_B_right":discordance,
        "all_failures":[r for r in rows if not r["whole_response_correct"]],
        "dynamic_pair_differences":{c:[(sum(lookup[p["dynamic_id"],i,c]["legacy_correct"] for i in range(5))-
            sum(lookup[p["dynamic_id"],i,"A"]["legacy_correct"] for i in range(5)))/5 for p in bundle["pairs"]] for c in ("B","C")},
        "provider_attempts":len(attempts), "transport_error_counts":dict(Counter(e for a in attempts for e in a["errors"])),
        "cost_usd_estimate_including_reservations":sum(a["cost_usd"] for a in attempts),
        "cost_has_unknown_usage":any("raw_response" not in a or not a.get("raw_response",{}).get("usage") for a in attempts),
        "tokens":{k:sum((a.get("raw_response",{}).get("usage") or {}).get(k,0) for a in attempts) for k in ("prompt_tokens","completion_tokens")},
        "reasoning_tokens":sum(((a.get("raw_response",{}).get("usage") or {}).get("completion_tokens_details") or {}).get("reasoning_tokens",0) or 0 for a in attempts),
        "latency_seconds":sum(a.get("latency_seconds",0) for a in attempts),
        "false_certifications":sum(t.get("evaluation",{}).get("legacy",{}).get("false_certification",False) for t in trials.values()),
        "overall_scientific_pass":None,"development_diagnostic":True,"independent_held_out":False,
        "formal_trial_started":False,"new_runtime_epsilon_gto_allowed":False,"adaptive_opponent_line_released":False}


class AttributionRunner(SmokeRunner):
    def __init__(self, *args, halt_path=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.halt_path = halt_path

    def run(self):
        self.report["schema_version"] = "aip-gamespec-attribution-v8"
        self.persist()
        try:
            for p in self.bundle["plan"]:
                if self.halt_path and self.halt_path.exists(): raise RuntimeError("global_oracle_stop")
                self.active_trial = p
                trial = dict(p,status="started",attempt_ids=[])
                self.report["trials"].append(trial)
                try:
                    _,text,a = self.call(p["trial_id"],messages_for(self.manifest,self.bundle,p))
                finally:
                    trial["attempt_ids"] = [a["attempt_id"] for a in self.report["attempts"] if a["trial_id"]==p["trial_id"]]
                try:
                    trial["evaluation"] = evaluate(text,p["condition"],self.bundle["cases"][p["case_id"]],a["errors"])
                except ValueError as error:
                    counterexample = {"trial_id":p["trial_id"],"raw_text":text,"error":str(error)}
                    self.report["oracle_counterexample"] = counterexample
                    if self.halt_path: write_json(self.halt_path,counterexample)
                    raise RuntimeError("independent_table_oracle_disagreement") from None
                trial["status"] = "completed"
                self.persist()
            self.report["status"] = "completed"
        except RuntimeError as error:
            self.report["status"],self.report["stop_reason"] = "stopped",str(error)
        self.report["analysis"] = analyze(self.manifest,self.bundle,self.report)
        self.persist()
        return self.report


def replay(manifest,bundle,report):
    if report["manifest_sha256"]!=digest(manifest) or report["bundle_sha256"]!=digest(bundle):
        raise ValueError("manifest/bundle changed")
    if len(report["trials"])>len(bundle["plan"]): raise ValueError("excess trials")
    planned_by_id = {p["trial_id"]:p for p in bundle["plan"]}
    for i,a in enumerate(report["attempts"]):
        p = planned_by_id.get(a["trial_id"])
        if p is None or a["attempt_id"]!=i: raise ValueError("unassigned attempt")
        if a["messages"]!=messages_for(manifest,bundle,p) or a.get("provider_parameters")!=parameters(manifest,bundle,p):
            raise ValueError("request changed")
    used = set(); rescored = []
    for planned,trial in zip(bundle["plan"],report["trials"]):
        if any(trial[k]!=v for k,v in planned.items()): raise ValueError("plan assignment changed")
        if trial["status"]!="completed": continue
        if len(trial["attempt_ids"])!=1: raise ValueError("reply budget mismatch")
        i = trial["attempt_ids"][0]
        if i in used: raise ValueError("attempt reused")
        used.add(i); a = report["attempts"][i]
        if a["attempt_id"]!=i or a["trial_id"]!=trial["trial_id"]: raise ValueError("attempt mismatch")
        if a["messages"]!=messages_for(manifest,bundle,planned) or a["provider_parameters"]!=parameters(manifest,bundle,planned):
            raise ValueError("request changed")
        raw,model = a["raw_response"],manifest["model"]
        if raw["model"]!=model["model_id"]: raise ValueError("model changed")
        u = raw["usage"]
        if u["prompt_tokens"]>model["maximum_input_tokens"] or u["completion_tokens"]>model["maximum_output_tokens"]:
            raise ValueError("usage cap exceeded")
        cost = (u["prompt_tokens"]*model["input_usd_per_million"]+u["completion_tokens"]*model["output_usd_per_million"])/1e6
        if abs(cost-a["cost_usd"])>1e-12: raise ValueError("cost changed")
        choice = raw["choices"][0]; text = choice["message"]["content"] or ""
        errors = [] if choice["finish_reason"]=="stop" else ["truncated_output" if choice["finish_reason"]=="length" else "provider_error"]
        try: json.loads(text,parse_constant=lambda _:(_ for _ in ()).throw(ValueError("nonfinite")))
        except (ValueError,TypeError): errors.append("invalid_json")
        if errors!=a["errors"]: raise ValueError("transport labels changed")
        e = evaluate(text,planned["condition"],bundle["cases"][planned["case_id"]],errors)
        if e!=trial["evaluation"]: raise ValueError("raw evaluation changed")
        rescored.append(dict(planned,status="completed",raw_text=text,evaluation=e))
    if report["status"]=="completed" and (len(report["trials"])!=len(bundle["plan"]) or len(used)!=len(report["attempts"])):
        raise ValueError("completed report missing assignments")
    summary = analyze(manifest,bundle,report)
    if summary!=report["analysis"]: raise ValueError("summary changed")
    done = {r["trial_id"]:r for r in rescored}
    trials_by_id = {t["trial_id"]:t for t in report["trials"]}
    rows = [done.get(p["trial_id"],dict(p,status=trials_by_id.get(p["trial_id"],{}).get("status","unexecuted"),
        raw_text=None,evaluation=None,errors=["incomplete"],
        attempt_ids=trials_by_id.get(p["trial_id"],{}).get("attempt_ids",[]))) for p in bundle["plan"]]
    return {"raw_rescoring_agrees":True,"rows":rows,"summary":summary}


def compare_statistics(analyses):
    rows = []
    for tag,a in analyses.items():
        for condition,xs in a["dynamic_pair_differences"].items():
            observed = abs(sum(xs)/len(xs))
            permutations = [abs(sum(s*x for s,x in zip(signs,xs))/len(xs)) for signs in product((-1,1),repeat=len(xs))]
            rows.append({"model":tag,"contrast":condition+"-A","pair_differences":xs,
                "difference":sum(xs)/len(xs),"two_sided_p":sum(p>=observed-1e-12 for p in permutations)/len(permutations)})
    running = 0
    for i,row in enumerate(sorted(rows,key=lambda x:x["two_sided_p"])):
        running = max(running,min(1,row["two_sided_p"]*(len(rows)-i)))
        row["holm_adjusted_p"] = running
        row["exploratory_below_005"] = running<0.05
    return rows
