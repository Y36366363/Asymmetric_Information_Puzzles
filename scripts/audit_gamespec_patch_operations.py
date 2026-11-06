#!/usr/bin/env python3
"""Post-run descriptive operation audit; does not reinterpret or rescore edits."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from aip.benchmark.gamespec_cell_audit import apply_patch, difference_patch
from aip.benchmark.gamespec_scope_ablation import strict_json
from run_gamespec_patch_diagnostic import OUT, package, input_table, preserve_json, replay, validate

ROOT = Path(__file__).resolve().parents[1]


def build():
    validate(); m, b = package(); source = OUT / "luna6.json"
    raw = json.loads(source.read_text()); replay(m, b, raw)
    rows = []
    for t in raw["trials"]:
        if t["representation"] != "patch": continue
        item = b["cases"][t["case_id"]]; fields = tuple(item["case"]["fields"])
        original = input_table(b, t); reference = item["visibility_contexts"]
        edits = strict_json(t["raw_text"])["edits"]
        ops = []; seen = set()
        for edit in edits:
            # This post-run audit targets already parsed, schema-shaped outputs.
            s, p, f, action = (edit[k] for k in ("stage", "player", "field", "action"))
            if type(s) is not int or type(p) is not int or s not in (0, 1) or p not in (0, 1) or f not in fields or action not in ("add", "remove"):
                raise ValueError("unexpected operation shape: preserve before extending post-run taxonomy")
            key = (s, p, f); present = f in original[s][p]; target = action == "add"
            ops.append(dict(edit, input_present=present, reference_present=f in reference[s][p],
                applicable=present != target, repeated_cell=key in seen,
                effect="noop_add" if present and target else "noop_remove" if not present and not target else
                    "fixes_error" if target == (f in reference[s][p]) else "introduces_error"))
            seen.add(key)
        noops = [o for o in ops if not o["applicable"]]
        repeated = [o for o in ops if o["repeated_cell"]]
        expected_invalid = bool(noops or repeated)
        if expected_invalid != t["metrics"]["invalid_patch"]: raise ValueError("audit disagrees with frozen patch rejection")
        # Reapply only strict valid edits. No permissive/idempotent fallback exists.
        if not expected_invalid:
            if apply_patch(original, fields, edits) != t["expanded_output"]["stage_table"]:
                raise ValueError("independent strict reapplication changed")
        rows.append({k: t[k] for k in ("trial_id", "seed_id", "seed_kind", "feedback")} | {
            "raw_text": t["raw_text"], "edits": edits, "operation_labels": ops,
            "contains_noop": bool(noops), "contains_repeated_cell": bool(repeated),
            "invalid_patch": expected_invalid, "empty_patch": not edits,
            "table_correct": t["metrics"]["table_correct"],
            "proposal_correct": t["metrics"]["reference_proposal_correct"],
            "own_table_consistent": t["metrics"]["own_table_consistent"],
            "oracle_minimal_edits_for_explanation_only": difference_patch(original, reference, fields)})
    return {"schema_version": "aip-gamespec-patch-operation-audit-v1", "analysis_timing": "post_run_exploratory_failure_description",
        "model_generation_calls": 0, "primary_scores_changed": False, "noops_reinterpreted_as_valid": False,
        "patch_outputs": len(rows), "invalid_patches": sum(r["invalid_patch"] for r in rows),
        "outputs_containing_noop": sum(r["contains_noop"] for r in rows),
        "outputs_containing_repeated_cell": sum(r["contains_repeated_cell"] for r in rows),
        "empty_patch_outputs": sum(r["empty_patch"] for r in rows),
        "valid_patch_outputs": sum(not r["invalid_patch"] for r in rows),
        "valid_wrong_input_patch_outputs": sum(not r["invalid_patch"] and r["seed_kind"] == "wrong" for r in rows),
        "valid_wrong_input_patch_repairs": sum(not r["invalid_patch"] and r["seed_kind"] == "wrong" and r["table_correct"] for r in rows),
        "operation_counts": dict(Counter(o["effect"] for r in rows for o in r["operation_labels"])),
        "rows": rows, "sources_sha256": {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in (source, Path(__file__))},
        "interpretation": "No-op edits are compatible with confusing desired visibility assignments with relative edits; this is a hypothesis, not a hidden-comprehension diagnosis. Valid edits can still break correct cells. No old scores are relaxed."}


if __name__ == "__main__":
    result = build(); preserve_json(OUT / "operation_audit.json", result)
    print(json.dumps({k: v for k, v in result.items() if k not in ("rows", "sources_sha256", "interpretation")}))
