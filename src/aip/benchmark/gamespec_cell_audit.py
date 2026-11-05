"""Offline observable-output audit and a reference-free, atomic cell patch codec.

Neither a valid patch nor a consistent witness is a semantic certificate.
This module does not infer hidden cognition or call a model.
"""
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json

from aip.benchmark.gamespec_attribution import normalize_table, output_schema
from aip.benchmark.gamespec_prospective import change_witnesses


def patch_schema(fields):
    return {"type": "array", "minItems": 0, "maxItems": 4 * len(fields),
        "items": {"type": "object", "additionalProperties": False,
            "properties": {"stage": {"type": "integer", "enum": [0, 1]},
                "player": {"type": "integer", "enum": [0, 1]},
                "field": {"type": "string", "enum": list(fields)},
                "action": {"type": "string", "enum": ["add", "remove"]}},
            "required": ["stage", "player", "field", "action"]}}


def repair_schema(manifest, case, representation):
    result = output_schema(manifest, case, "C")
    if representation == "rewrite":
        return result
    if representation != "patch":
        raise ValueError("unknown representation")
    return {"type": "object", "additionalProperties": False,
        "properties": {"edits": patch_schema(case["fields"]),
                       "proposal": deepcopy(result["properties"]["proposal"])},
        "required": ["edits", "proposal"]}


def apply_patch(table, fields, edits):
    """Simultaneous bit edits; duplicates, contradictory edits and no-ops fail.

    A malformed patch never mutates the caller's input. No reference is accepted.
    Unknown fields and bool-as-integer indexes are rejected, not coerced.
    """
    original = normalize_table(table, fields)
    if not isinstance(edits, list) or len(edits) > 4 * len(fields):
        raise ValueError("patch must be a bounded edit list")
    seen = set()
    for edit in edits:
        if not isinstance(edit, dict) or set(edit) != {"stage", "player", "field", "action"}:
            raise ValueError("exact edit keys required")
        s, p, f, action = (edit[k] for k in ("stage", "player", "field", "action"))
        if type(s) is not int or type(p) is not int or s not in (0, 1) or p not in (0, 1):
            raise ValueError("integer stage/player in 0..1 required")
        if not isinstance(f, str) or f not in fields or action not in ("add", "remove"):
            raise ValueError("unknown field or operation")
        key = (s, p, f)
        if key in seen:
            raise ValueError("one edit per visibility cell")
        seen.add(key)
        present = f in original[s][p]
        if present == (action == "add"):
            raise ValueError("no-op patch edit")
    result = deepcopy(original)
    for edit in edits:
        cell = result[edit["stage"]][edit["player"]]
        if edit["action"] == "add":
            cell.append(edit["field"])
        else:
            cell.remove(edit["field"])
    return normalize_table(result, fields)


def difference_patch(before, after, fields):
    """Offline oracle/diff helper, never used to supply a model's answer."""
    before, after = normalize_table(before, fields), normalize_table(after, fields)
    return [{"stage": s, "player": p, "field": f,
             "action": "add" if f in after[s][p] else "remove"}
            for s in range(2) for p in range(2) for f in fields
            if (f in before[s][p]) != (f in after[s][p])]


def expand_repair_output(payload, representation, original, fields):
    """Convert either interface to the old C envelope; never repair the proposal."""
    key = {"patch": "edits", "rewrite": "stage_table"}.get(representation)
    if key is None or not isinstance(payload, dict) or set(payload) != {key, "proposal"}:
        raise ValueError("exact repair envelope required")
    table = (apply_patch(original, fields, payload[key]) if representation == "patch"
             else normalize_table(payload[key], fields))
    return {"stage_table": table, "proposal": deepcopy(payload["proposal"])}


def cell_ledger(before, after, reference, fields):
    tables = [normalize_table(t, fields) for t in (before, after, reference)]
    rows = []
    for s in range(2):
        for p in range(2):
            for f in fields:
                a, b, r = [f in t[s][p] for t in tables]
                outcome = ("preserved_correct" if a == r else "fixed") if b == r else (
                    "introduced_error" if a == r else "retained_error")
                rows.append({"stage": s, "player": p, "field": f, "input": a,
                    "output": b, "reference": r, "outcome": outcome,
                    "edit": "unchanged" if a == b else ("add" if b else "remove")})
    return rows


def audit_trial(trial, bundle):
    seed = bundle["seeds"][trial["seed_id"]]
    item = bundle["cases"][trial["case_id"]]
    fields = tuple(item["case"]["fields"])
    original = seed["original_table"] if trial["seed_kind"] == "wrong" else seed["correct_control"]
    output = json.loads(trial["raw_text"])
    table, proposal = output["stage_table"], output["proposal"]
    reference = item["visibility_contexts"]
    ledger = cell_ledger(original, table, reference, fields)
    changes = change_witnesses(table)
    truth_changes = change_witnesses(reference)
    witness = proposal["witness"]
    table_correct = all(r["output"] == r["reference"] for r in ledger)
    witness_in_table, witness_in_reference = witness in changes, witness in truth_changes
    # All v11 inputs are dynamic; verify this scope rather than generalize silently.
    if item["kind"] != "dynamic" or proposal["decision"] != "refusal":
        raise ValueError("this audit requires dynamic refusal outputs")
    if table_correct != trial["evaluation"]["table_correct"] or witness_in_table != trial["evaluation"]["proposal_consistent_with_own_table"]:
        raise ValueError("direct ledger disagrees with frozen evaluation")
    classification = "not_selected"
    if not table_correct and trial["evaluation"]["legacy"]["correct"]:
        classification = "partial_witness_masks_other_cells" if witness_in_table else "table_witness_contradiction"
    return {k: trial[k] for k in ("trial_id", "case_id", "seed_id", "seed_kind", "feedback_arm")} | {
        "raw_text": trial["raw_text"], "raw_text_sha256": sha256(trial["raw_text"].encode()).hexdigest(),
        "input_table": deepcopy(original), "output_table": table, "reference_table": deepcopy(reference),
        "input_changes": change_witnesses(original), "output_changes": changes,
        "reference_changes": truth_changes, "proposal": proposal,
        "witness_in_own_table": witness_in_table, "witness_in_reference": witness_in_reference,
        "observable_class": classification, "hidden_cognitive_cause": "not_identified",
        "cell_ledger": ledger, "cell_outcomes": dict(Counter(r["outcome"] for r in ledger)),
        "actual_edit_list": difference_patch(original, table, fields),
        "oracle_minimal_repair_edits": difference_patch(table, reference, fields),
        "oracle_edits_are_model_performance": False,
        "input_copied_as_sets": normalize_table(original, fields) == normalize_table(table, fields),
        "rule_text": item["case"]["rules"], "frozen_excerpts": deepcopy(bundle["evidence_registry"][trial["case_id"]]),
        "frozen_validation_status": trial["validation"]["status"]}


def audit_reports(reports, bundle):
    rows = [dict(audit_trial(t, bundle), model=tag) for tag, raw in reports.items() for t in raw["trials"]]
    selected = [r for r in rows if r["model"] == "luna6" and r["feedback_arm"] == "semantic"
                and r["observable_class"] != "not_selected"]
    grouped = {}
    for tag in reports:
        grouped[tag] = {}
        for arm in ("none", "local", "semantic"):
            grouped[tag][arm] = {}
            for kind in ("wrong", "correct_control"):
                subset = [r for r in rows if r["model"] == tag and r["feedback_arm"] == arm and r["seed_kind"] == kind]
                counts = Counter(outcome for r in subset for outcome, n in r["cell_outcomes"].items() for _ in range(n))
                grouped[tag][arm][kind] = {"outputs": len(subset), "cells": dict(counts),
                    "unchanged_tables": sum(r["input_copied_as_sets"] for r in subset)}
    return {"schema_version": "aip-gamespec-cell-audit-v12", "model_generation_calls": 0,
        "all_output_count": len(rows), "selected_count": len(selected),
        "selected_classes": dict(Counter(r["observable_class"] for r in selected)),
        "selected_input_kinds": dict(Counter(r["seed_kind"] for r in selected)),
        "selected_unchanged_tables": sum(r["input_copied_as_sets"] for r in selected),
        "by_model_arm_kind": grouped, "selected_rows": selected, "all_rows": rows,
        "primary_scores_changed": False, "new_manual_reference": False,
        "hidden_cause_identified": False, "statistical_significance_claimed": False,
        "runtime_authority": False, "adaptive_opponent_line_released": False,
        "interpretation": {
            "partial_witness": "A valid existential counterexample proves static visibility is inexpressible; it does not certify every cell. Correct partial reasoning is not evidence of luck or complete understanding.",
            "contradiction": "The observable table and proposal disagree. Format errors, late self-correction, anchoring or distinct representations remain hypotheses; generation-order causality is not established.",
            "semantic_treatment": "Full rules were already present. Added excerpts coexist with local transitions computed from the input table; salience, input anchoring and conflicting representations are not isolated.",
            "control": "Sol ceiling establishes feasibility under this interface, not a model-only causal diagnosis for Luna.",
            "patch": "Every binary visibility mismatch has an add/remove repair. Representability is not successful inference by a model; a failed patch cannot alone prove lack of rule understanding."}}
