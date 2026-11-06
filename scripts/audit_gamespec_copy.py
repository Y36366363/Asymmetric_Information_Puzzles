#!/usr/bin/env python3
"""Observe final table copying without claiming access to intermediate cognition."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re

from aip.benchmark.gamespec_attribution import normalize_table
from run_gamespec_feedback_repair import package, OUT, preserve_json, replay, validate

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "research/results/gamespec_copy_audit_2026-11-06.json"


def table_fragment(text):
    """Extract a top-level table value's original JSON spelling, not a re-dump."""
    decoder = json.JSONDecoder()
    pos = 0
    while pos < len(text) and text[pos].isspace(): pos += 1
    if pos == len(text) or text[pos] != "{": raise ValueError("object required")
    pos += 1
    while True:
        while pos < len(text) and text[pos].isspace(): pos += 1
        if pos == len(text) or text[pos] == "}": raise ValueError("missing stage_table")
        key, pos = decoder.raw_decode(text, pos)
        while pos < len(text) and text[pos].isspace(): pos += 1
        if text[pos:pos+1] != ":": raise ValueError("colon required")
        pos += 1
        while pos < len(text) and text[pos].isspace(): pos += 1
        start = pos
        _, pos = decoder.raw_decode(text, pos)
        if key == "stage_table": return text[start:pos]
        while pos < len(text) and text[pos].isspace(): pos += 1
        if text[pos:pos+1] != ",": raise ValueError("missing stage_table")
        pos += 1


def compare(input_text, output_text, fields):
    result = {"visible_edit_history": "not_observed", "changed_then_reverted": None}
    try:
        before = json.loads(input_text)["stage_table"]
        b = normalize_table(before, fields)
        output = json.loads(output_text)
        after = output["stage_table"]
        a = normalize_table(after, fields)
    except (ValueError, KeyError, TypeError):
        return result | {"class": "missing_or_invalid_table", "raw_fragment_equal": False,
            "whitespace_only_difference": False, "ordered_array_equal": False,
            "field_sets_equal": False, "changed_cells": None}
    i, o = table_fragment(input_text), table_fragment(output_text)
    return result | {"class": "same_final_cells" if a == b else "changed_final_cells",
        "raw_fragment_equal": i == o,
        "whitespace_only_difference": i != o and re.sub(r"\s+", "", i) == re.sub(r"\s+", "", o),
        "ordered_array_equal": before == after, "field_sets_equal": a == b,
        "changed_cells": [{"stage": s, "player": p, "field": f,
            "input": f in before[s][p], "output": f in after[s][p]}
            for s in range(2) for p in range(2) for f in fields
            if (f in before[s][p]) != (f in after[s][p])]}


def build():
    validate(); m, b = package("luna6")
    source = OUT / "luna6.json"; raw = json.loads(source.read_text())
    replay(m, b, raw)
    rows = []
    for t in raw["trials"]:
        if t["feedback_arm"] != "semantic" or t["seed_kind"] != "wrong": continue
        attempt = raw["attempts"][t["attempt_ids"][0]]
        input_text = attempt["messages"][1]["content"]
        row = compare(input_text, t["raw_text"], b["cases"][t["case_id"]]["case"]["fields"])
        rows.append(row | {"trial_id": t["trial_id"], "case_id": t["case_id"],
            "input_table_fragment": table_fragment(input_text),
            "output_table_fragment": table_fragment(t["raw_text"]),
            "input_sha256": sha256(input_text.encode()).hexdigest(),
            "output_sha256": sha256(t["raw_text"].encode()).hexdigest()})
    return {"schema_version": "aip-gamespec-copy-audit-v1", "model_generation_calls": 0,
        "source": str(source.relative_to(ROOT)), "source_sha256": sha256(source.read_bytes()).hexdigest(),
        "original_replay_agrees": True, "count": len(rows),
        "classes": dict(Counter(r["class"] for r in rows)),
        "raw_fragment_equal": sum(r["raw_fragment_equal"] for r in rows),
        "same_order_whitespace_only": sum(r["whitespace_only_difference"] for r in rows),
        "same_cells_different_order": sum(r["field_sets_equal"] and not r["ordered_array_equal"] for r in rows),
        "changed_then_reverted_count": None,
        "reason": "Single final replies contain no table-edit trace. Final equality cannot distinguish copying, independent reconstruction or a hidden edit followed by reversion. Missing/empty tables are observable; hidden edits are not.",
        "old_scores_changed": False, "rows": rows}


if __name__ == "__main__":
    result = build(); preserve_json(DEST, result)
    print(json.dumps({k: v for k, v in result.items() if k not in ("rows", "reason")}))
