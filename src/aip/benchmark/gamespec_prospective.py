"""Prospective finite observation slices; fixed v4 interface, direct table oracle."""
from copy import deepcopy
from itertools import product
import json

from aip.benchmark.gamespec_smoke import SmokeRunner, digest, make_bundle
from aip.benchmark.gamespec_interface import evaluate, messages_for, parameters, serialize_proposal
from aip.benchmark.gamespec_scope_ablation import strict_json


def projection(owners, player):
    return {field for field, owner in owners.items() if owner in ("public", f"player_{player}")}


def change_witnesses(contexts):
    return [{"field": field, "player": player,
             "before_visible": field in contexts[0][player], "after_visible": field in contexts[1][player]}
            for player in range(2) for field in sorted(set(contexts[0][player]) ^ set(contexts[1][player]))]


def audit_references(spec):
    rows = []
    identifiers = set()
    for pair in spec["pairs"]:
        fields = list(pair["fields"])
        static = pair["static_visibility"]
        contexts = pair["dynamic_visibility"]
        for case_id in (pair["static_id"], pair["dynamic_id"]):
            if case_id in identifiers:
                raise ValueError("duplicate case ID")
            identifiers.add(case_id)
        if len(contexts) != 2 or len(static) != 2 or any(len(c) != 2 for c in contexts):
            raise ValueError("two player/two context reference required")
        for view in [static] + contexts:
            if any(len(xs) != len(set(xs)) or not set(xs) <= set(fields) for xs in view):
                raise ValueError("reference table vocabulary or duplicates")
        if set(pair["owners"]) != set(fields) or any(projection(pair["owners"], p) != set(static[p]) for p in range(2)):
            raise ValueError("owner mapping disagrees with direct visibility table")
        static_matches, dynamic_matches = [], []
        for values in product(("public", "player_0", "player_1"), repeat=len(fields)):
            owners = dict(zip(fields, values))
            if all(projection(owners, p) == set(static[p]) for p in range(2)):
                static_matches.append(owners)
            if all(projection(owners, p) == set(c[p]) for c in contexts for p in range(2)):
                dynamic_matches.append(owners)
        witnesses = change_witnesses(contexts)
        if static_matches != [pair["owners"]] or dynamic_matches or not witnesses:
            raise ValueError("reference expressibility audit failed")
        rows.append({"pair_id": pair["pair_id"], "partitions_enumerated": 3 ** len(fields),
                     "static_matching_partitions": 1, "dynamic_matching_partitions": 0,
                     "all_valid_change_witnesses": witnesses})
    return {"passed": True, "rows": rows,
            "natural_language_truth_proven": False, "independent_human_sources": False}


def materialize(v4_manifest, v4_bundle, spec):
    audit = audit_references(spec)
    manifest = deepcopy(v4_manifest)
    manifest["manifest_id"] = spec["manifest_id"] + ":" + manifest["model"]["model_id"]
    # Leave the exact selected system prompt, source-priority suffix and parameter profile intact.
    manifest["interface_spec"]["arms"] = [a for a in manifest["interface_spec"]["arms"] if a["id"] == "f1_s1"]
    manifest["schedule"] = {"maximum_calls": spec["schedule"]["trials_per_model"]}
    manifest["prospective_spec"] = deepcopy(spec)
    base_cases = [{"case_id": p["static_id"], "fields": p["fields"], "rules": p["static_rules"],
                   "reference_owners": p["owners"]} for p in spec["pairs"]]
    evidence = make_bundle({"cases": base_cases})["cases"]
    cases = {}
    for pair, row in zip(spec["pairs"], audit["rows"]):
        static_id, dynamic_id = pair["static_id"], pair["dynamic_id"]
        cases[static_id] = {"case": next(c for c in base_cases if c["case_id"] == static_id),
                           "kind": "static", "pair_id": pair["pair_id"], "evidence": evidence[static_id],
                           "visibility_contexts": [pair["static_visibility"], pair["static_visibility"]]}
        witnesses = row["all_valid_change_witnesses"]
        cases[dynamic_id] = {"case": {"case_id": dynamic_id, "fields": pair["fields"], "rules": pair["dynamic_rules"]},
                            "kind": "dynamic", "pair_id": pair["pair_id"],
                            "control": {"case_id": dynamic_id, "expected_code": "OUT_OF_SCHEMA_STATIC_VISIBILITY",
                                        "required_witness": witnesses[0]},
                            "additional_witnesses": witnesses[1:], "visibility_contexts": pair["dynamic_visibility"]}
    plan = []
    for task, ids in (("scope", spec["schedule"]["scope_case_order"]),
                      ("witness_repair", [p["static_id"] for p in spec["pairs"]])):
        for case_id in ids:
            for repeat in range(spec["schedule"]["repeats"]):
                plan.append({"trial_id": f"{task}:{case_id}:{repeat}:f1_s1", "task": task, "case_id": case_id,
                             "repeat": repeat, "arm": "f1_s1", "pair_id": cases[case_id]["pair_id"]})
    if len(plan) != spec["schedule"]["trials_per_model"]:
        raise ValueError("assigned plan mismatch")
    return manifest, {"manifest_sha256": digest(manifest), "cases": cases, "plan": plan,
                      "pairs": deepcopy(spec["pairs"]), "reference_preflight": audit}


def table_oracle(text, item):
    """Direct visible-set checks, no GameSpec compiler/projection or final-score calls."""
    try:
        proposal = strict_json(text)
        if proposal["decision"] == "refusal":
            witness = proposal["witness"]
            return (item["kind"] == "dynamic" and type(witness["player"]) is int
                    and type(witness["before_visible"]) is bool and type(witness["after_visible"]) is bool
                    and witness in change_witnesses(item["visibility_contexts"]))
        if item["kind"] != "static" or proposal["decision"] != "candidate":
            return False
        for candidate in proposal["candidates"]:
            if all(set(candidate["public_fields"]) | set(candidate["private_fields_by_player"][f"player_{p}"])
                   == set(context[p]) for context in item["visibility_contexts"] for p in range(2)):
                return True
    except (ValueError, TypeError, KeyError):
        pass
    return False


def score(text, item, errors=()):
    evaluated = evaluate(text, item, errors)
    # Semantic oracle only eligible after the independent structural contract succeeds.
    oracle = evaluated["serialization_ok"] and table_oracle(text, item) and not errors
    if bool(oracle) != evaluated["correct"]:
        raise ValueError("independent_table_oracle_disagreement")
    evaluated["table_oracle_correct"] = bool(oracle)
    return evaluated


def analyze(manifest, bundle, report):
    trials = {t["trial_id"]: t for t in report["trials"]}
    groups = {}
    for task, kind, name in (("scope", "static", "static"), ("scope", "dynamic", "dynamic"),
                              ("witness_repair", "static", "repair")):
        assigned = [p for p in bundle["plan"] if p["task"] == task and bundle["cases"][p["case_id"]]["kind"] == kind]
        groups[name] = {"assigned": len(assigned),
                        "completed": sum(trials.get(p["trial_id"], {}).get("status") == "completed" for p in assigned),
                        "correct": sum(trials.get(p["trial_id"], {}).get("evaluation", {}).get("correct", False) for p in assigned)}
    pairs = []
    for pair in bundle["pairs"]:
        correct = [all(trials.get(f"scope:{pair[side]}:{r}:f1_s1", {}).get("evaluation", {}).get("correct", False)
                       for side in ("static_id", "dynamic_id")) for r in range(2)]
        repair = [trials.get(f"witness_repair:{pair['static_id']}:{r}:f1_s1", {}).get("evaluation", {}).get("correct", False) for r in range(2)]
        pairs.append({"pair_id": pair["pair_id"], "joint_by_repeat": correct, "repair_by_repeat": repair})
    attempts = report["attempts"]
    return {"groups": groups, "pair_results": pairs, "joint_pair_success": sum(sum(p["joint_by_repeat"]) for p in pairs),
            "joint_pair_assigned": len(pairs) * 2,
            "all_failures": [{"trial_id": p["trial_id"], "errors": trials.get(p["trial_id"], {}).get("evaluation", {}).get("errors", ["incomplete"])}
                             for p in bundle["plan"] if not trials.get(p["trial_id"], {}).get("evaluation", {}).get("correct", False)],
            "provider_attempts": len(attempts), "cost_usd": sum(a["cost_usd"] for a in attempts),
            "tokens": {k: sum((a.get("raw_response", {}).get("usage") or {}).get(k, 0) for a in attempts) for k in ("prompt_tokens", "completion_tokens")},
            "latency_seconds": sum(a.get("latency_seconds", 0) for a in attempts),
            "reasoning_tokens": sum(((a.get("raw_response", {}).get("usage") or {}).get("completion_tokens_details") or {}).get("reasoning_tokens", 0) or 0 for a in attempts),
            "false_certifications": sum(t.get("evaluation", {}).get("false_certification", False) for t in trials.values()),
            "oos_false_acceptances": sum(t.get("evaluation", {}).get("scope_false_acceptance", False) for t in trials.values()),
            "feedback_exposures": sum(t["task"] == "witness_repair" and t["status"] == "completed" for t in trials.values()),
            "overall_scientific_pass": None, "generalization_proven": False, "formal_trial_started": False,
            "uncertainty": manifest["prospective_spec"]["independent_scoring"]["uncertainty"],
            "adaptive_opponent_line_released": False, "new_runtime_epsilon_gto_allowed": False}


class ProspectiveRunner(SmokeRunner):
    def run(self):
        self.report["schema_version"] = "aip-gamespec-prospective-v5"
        self.report["reference_preflight"] = self.bundle["reference_preflight"]
        self.persist()
        try:
            for planned in self.bundle["plan"]:
                self.active_trial = planned
                trial = dict(planned, status="started", attempt_ids=[])
                self.report["trials"].append(trial)
                _, text, attempt = self.call(trial["trial_id"], messages_for(self.manifest, self.bundle, trial))
                trial["attempt_ids"] = [attempt["attempt_id"]]
                try:
                    trial["evaluation"] = score(text, self.bundle["cases"][trial["case_id"]], attempt["errors"])
                except ValueError:
                    self.report["oracle_counterexample"] = {"trial_id": trial["trial_id"], "raw_text": text}
                    raise RuntimeError("independent_table_oracle_disagreement") from None
                trial["status"] = "completed"
                self.persist()
            self.report["status"] = "completed"
        except RuntimeError as error:
            self.report["status"], self.report["stop_reason"] = "stopped", str(error)
        self.report["analysis"] = analyze(self.manifest, self.bundle, self.report)
        self.persist()
        return self.report


def replay(manifest, bundle, report):
    if (report["manifest_sha256"] != digest(manifest) or report["bundle_sha256"] != digest(bundle)
            or [t["trial_id"] for t in report["trials"]] != [p["trial_id"] for p in bundle["plan"][:len(report["trials"])]]):
        raise ValueError("frozen plan mismatch")
    used = set()
    for planned, trial in zip(bundle["plan"], report["trials"]):
        if any(trial[k] != v for k, v in planned.items()):
            raise ValueError("assignment mismatch")
        if trial["status"] != "completed":
            continue
        if len(trial["attempt_ids"]) != 1 or trial["attempt_ids"][0] in used:
            raise ValueError("reply budget or reused attempt")
        i = trial["attempt_ids"][0]
        used.add(i)
        a = report["attempts"][i]
        if a["attempt_id"] != i or a["trial_id"] != trial["trial_id"]:
            raise ValueError("attempt mismatch")
        if a["messages"] != messages_for(manifest, bundle, planned) or a["provider_parameters"] != parameters(manifest, bundle, planned):
            raise ValueError("request mismatch")
        raw, model = a["raw_response"], manifest["model"]
        if raw["model"] != model["model_id"]:
            raise ValueError("model mismatch")
        u = raw["usage"]
        if u["prompt_tokens"] > model["maximum_input_tokens"] or u["completion_tokens"] > model["maximum_output_tokens"]:
            raise ValueError("usage cap mismatch")
        cost = (u["prompt_tokens"] * model["input_usd_per_million"] + u["completion_tokens"] * model["output_usd_per_million"]) / 1e6
        if abs(cost - a["cost_usd"]) > 1e-12:
            raise ValueError("cost mismatch")
        choice = raw["choices"][0]
        errors = [] if choice["finish_reason"] == "stop" else ["truncated_output" if choice["finish_reason"] == "length" else "provider_error"]
        text = choice["message"]["content"] or ""
        try:
            json.loads(text, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
        except (ValueError, TypeError):
            errors.append("invalid_json")
        if score(text, bundle["cases"][trial["case_id"]], errors) != trial["evaluation"]:
            raise ValueError("raw score mismatch")
    if report["status"] == "completed" and (len(report["trials"]) != len(bundle["plan"]) or len(used) != len(report["attempts"])):
        raise ValueError("incomplete schedule")
    analysis = analyze(manifest, bundle, report)
    if analysis != report["analysis"]:
        raise ValueError("summary mismatch")
    return analysis
