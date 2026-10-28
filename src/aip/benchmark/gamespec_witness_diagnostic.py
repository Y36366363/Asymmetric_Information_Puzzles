"""Development-only witness diagnostics; reuse the frozen proposal and score path."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from aip.benchmark.gamespec_smoke import digest
from aip.benchmark.gamespec_prospective import change_witnesses, materialize, replay


def diagnostic_package(v4_manifest, v4_bundle, spec):
    # v5 materialization also builds repair trials. Build once, then select scope only;
    # do not change any prompt, model parameter, serializer or scoring function.
    expanded = deepcopy(spec)
    expanded["schedule"]["trials_per_model"] = len(spec["pairs"]) * 3 * spec["schedule"]["repeats"]
    manifest, bundle = materialize(v4_manifest, v4_bundle, expanded)
    bundle["plan"] = [p for p in bundle["plan"] if p["task"] == "scope"]
    if len(bundle["plan"]) != spec["schedule"]["trials_per_model"]:
        raise ValueError("diagnostic schedule mismatch")
    manifest["prospective_spec"] = deepcopy(spec)
    manifest["schedule"] = {"maximum_calls": len(bundle["plan"])}
    bundle["manifest_sha256"] = digest(manifest)
    return manifest, bundle


def diagnostic_analysis(manifest, bundle, report):
    base = replay(manifest, bundle, report)
    trials = {t["trial_id"]: t for t in report["trials"]}
    rows = []
    failures = []
    for pair in bundle["pairs"]:
        expected = change_witnesses(pair["dynamic_visibility"])
        if len(expected) != 1:
            raise ValueError("single-change diagnostic required")
        rows.append({"pair_id": pair["pair_id"], "expected_change": expected[0],
                     "joint_by_repeat": next(p["joint_by_repeat"] for p in base["pair_results"] if p["pair_id"] == pair["pair_id"])})
    for p in bundle["plan"]:
        t = trials.get(p["trial_id"], {})
        if t.get("evaluation", {}).get("correct", False):
            continue
        item = bundle["cases"][p["case_id"]]
        categories = []
        if t.get("status") != "completed":
            categories.append("incomplete_or_provider_error")
        elif not t["evaluation"]["serialization_ok"]:
            categories.append("interface_contract_error")
        else:
            a = report["attempts"][t["attempt_ids"][0]]
            payload = json.loads(a["raw_response"]["choices"][0]["message"]["content"])
            if item["kind"] == "static":
                categories.append("static_false_refusal" if payload["decision"] == "refusal" else "wrong_static_partition")
            elif payload["decision"] != "refusal":
                categories.append("dynamic_false_acceptance")
            else:
                w, e = payload["witness"], change_witnesses(item["visibility_contexts"])[0]
                if w["field"] != e["field"]: categories.append("wrong_changed_field")
                if w["player"] != e["player"]: categories.append("wrong_affected_player")
                if w["before_visible"] != e["before_visible"]: categories.append("wrong_initial_visibility")
                if w["after_visible"] != e["after_visible"]: categories.append("wrong_final_visibility")
                if (w["before_visible"], w["after_visible"]) == (e["after_visible"], e["before_visible"]):
                    categories.append("reversed_change_direction")
                if w["before_visible"] == w["after_visible"]: categories.append("no_visibility_change")
        failures.append({"trial_id": p["trial_id"], "categories": categories,
                         "original_errors": t.get("evaluation", {}).get("errors", ["incomplete"])})
    return {"groups": {k: base["groups"][k] for k in ("static", "dynamic")},
            "cells": rows, "joint_correct": base["joint_pair_success"], "joint_assigned": base["joint_pair_assigned"],
            "all_failures": failures, "cost_usd": base["cost_usd"], "tokens": base["tokens"],
            "latency_seconds": base["latency_seconds"], "provider_attempts": base["provider_attempts"],
            "false_certifications": base["false_certifications"], "oos_false_acceptances": base["oos_false_acceptances"],
            "development_diagnostic": True, "independent_rule_instances": 0, "held_out": False,
            "overall_scientific_pass": None, "deployment_permission": False,
            "adaptive_opponent_line_released": False, "new_runtime_epsilon_gto_allowed": False}


def review_intake(record, root):
    """Fail-closed documentary gate, not identity verification or a semantic certificate.

    A reviewer supplies a separate table before seeing author labels/model replies.
    The two files must agree; unresolved disagreements are retained outside dispatch.
    """
    if record.get("status") != "ready_for_freeze":
        raise ValueError("independent rules pending; no dispatch")
    for key in ("author_id", "reviewer_id", "provenance_note"):
        if not isinstance(record.get(key), str) or not record[key].strip():
            raise ValueError("missing provenance")
    if record["author_id"] == record["reviewer_id"]:
        raise ValueError("author and reviewer must differ")
    required = ("reviewer_not_in_development", "reviewer_blind_to_author_reference",
                "reviewer_blind_to_model_outputs", "rules_not_used_in_development",
                "all_submitted_pairs_included", "no_unresolved_disagreements")
    if any(record.get(k) is not True for k in required):
        raise ValueError("independent review attestations missing")
    docs = {}
    for key in ("rules", "author_reference", "reviewer_reference"):
        entry = record[key]
        path = (Path(root) / entry["path"]).resolve()
        if not path.is_relative_to(Path(root).resolve()):
            raise ValueError("intake path outside package")
        raw = path.read_bytes()
        if sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError("review file changed")
        docs[key] = json.loads(raw)
    rules = docs["rules"]
    ids = [p["pair_id"] for p in rules["pairs"]]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("nonempty unique rule pairs required")
    for ref in (docs["author_reference"], docs["reviewer_reference"]):
        if set(ref) != {p["pair_id"] for p in rules["pairs"]}:
            raise ValueError("reference coverage mismatch")
        for pair in rules["pairs"]:
            if ref[pair["pair_id"]] != {k: pair[k] for k in ("owners", "static_visibility", "dynamic_visibility")}:
                raise ValueError("reference disagreement; retain before adjudication")
    from aip.benchmark.gamespec_prospective import audit_references
    audit = audit_references(rules)
    return {"documentary_gate_passed": True, "identity_independently_verified": False,
            "natural_language_truth_proven": False, "reference_audit": audit,
            "rule_pairs": len(rules["pairs"]), "generation_calls_authorized": False,
            "next_step": "commit frozen panel, references, provenance, order and one-shot execution manifest before any calls"}
