from collections import Counter
from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import socket
import sys

import pytest

from aip.benchmark.gamespec_cell_audit import (
    apply_patch, audit_reports, cell_ledger, difference_patch, expand_repair_output, repair_schema,
)
from aip.benchmark.gamespec_attribution import derive_proposal, normalize_table, output_schema
from aip.benchmark.gamespec_validation import verify_frozen_output

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
try:
    spec = importlib.util.spec_from_file_location("cell_audit_dispatch", ROOT / "scripts/audit_gamespec_cells.py")
    D = importlib.util.module_from_spec(spec); spec.loader.exec_module(D)
finally:
    sys.path.pop(0)


@pytest.fixture(scope="module")
def bundle():
    return D.package("luna6")[1]


def test_offline_replay_and_all_seventeen_classifications(monkeypatch):
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: pytest.fail("offline audit used network"))
    a = D.build()
    assert a["both_original_replays_agree"] and a["all_output_count"] == 144
    assert a["selected_count"] == 17 and a["selected_unchanged_tables"] == 10
    assert a["selected_classes"] == {"table_witness_contradiction": 7, "partial_witness_masks_other_cells": 10}
    assert a["selected_input_kinds"] == {"wrong": 11, "correct_control": 6}
    assert a["model_generation_calls"] == 0 and not a["hidden_cause_identified"]
    for r in a["selected_rows"]:
        assert r["witness_in_reference"]
        if r["observable_class"] == "partial_witness_masks_other_cells":
            assert r["case_id"] == "case_608" and r["proposal"]["witness"]["field"] == "assay"
            assert {c["field"] for c in r["cell_ledger"] if c["output"] != c["reference"]} == {"handbook"}
        else:
            assert not r["witness_in_own_table"]
    assert Counter(r["case_id"] for r in a["selected_rows"] if not r["witness_in_own_table"]) == {"case_281": 6, "case_608": 1}


def test_ledger_conserves_cells_and_actual_edits_reconstruct_every_reply(bundle):
    reports = {tag: json.loads((D.SOURCE / f"{tag}.json").read_text()) for tag in ("luna6", "sol61")}
    a = audit_reports(reports, bundle)
    for r in a["all_rows"]:
        fields = tuple(bundle["cases"][r["case_id"]]["case"]["fields"])
        assert len(r["cell_ledger"]) == sum(r["cell_outcomes"].values()) == 16
        assert apply_patch(r["input_table"], fields, r["actual_edit_list"]) == normalize_table(r["output_table"], fields)
        assert apply_patch(r["output_table"], fields, r["oracle_minimal_repair_edits"]) == normalize_table(r["reference_table"], fields)
    assert a["by_model_arm_kind"]["luna6"]["semantic"]["wrong"]["cells"] == {
        "fixed": 2, "introduced_error": 3, "preserved_correct": 175, "retained_error": 12}


def test_three_seed_patterns_have_one_two_one_edit_repairs_and_old_scoring(bundle):
    lengths = []
    for seed_id in ("s00", "s05", "s07"):
        s = bundle["seeds"][seed_id]; item = bundle["cases"][s["case_id"]]
        fields = tuple(item["case"]["fields"])
        edits = difference_patch(s["original_table"], s["correct_control"], fields)
        lengths.append(len(edits))
        payload = {"edits": edits, "proposal": derive_proposal(s["correct_control"], fields)}
        expanded = expand_repair_output(payload, "patch", s["original_table"], fields)
        record, _, _, score = verify_frozen_output(json.dumps(expanded), "C", item)
        assert score["whole_response_correct"] and record.to_artifact()["runtime_or_strategy_authority"] is False
        bad = expand_repair_output(dict(payload, edits=[]), "patch", s["original_table"], fields)
        _, _, _, score = verify_frozen_output(json.dumps(bad), "C", item)
        assert score["legacy"]["correct"] and not score["whole_response_correct"]
    assert lengths == [1, 2, 1]


def test_all_cell_directions_and_multi_cell_completeness():
    fields = ("a", "b", "c", "d")
    empty = [[[], []], [[], []]]
    full = [[list(fields), list(fields)], [list(fields), list(fields)]]
    assert apply_patch(empty, fields, difference_patch(empty, full, fields)) == full
    assert apply_patch(full, fields, difference_patch(full, empty, fields)) == empty
    for s in range(2):
        for p in range(2):
            for f in fields:
                one = deepcopy(empty); one[s][p] = [f]
                for original, target in ((empty, one), (one, empty)):
                    edits = difference_patch(original, target, fields)
                    assert len(edits) == 1 and apply_patch(original, fields, edits) == target


def test_empty_patch_preserves_correct_table_without_aliasing(bundle):
    s = bundle["seeds"]["s00"]; fields = bundle["cases"][s["case_id"]]["case"]["fields"]
    before = deepcopy(s["correct_control"])
    after = apply_patch(before, fields, [])
    assert after == normalize_table(before, fields)
    after[0][0].clear()
    assert before == s["correct_control"]


@pytest.mark.parametrize("edits", [None, {}, [None],
    [{"stage": True, "player": 0, "field": "x", "action": "add"}],
    [{"stage": 0.0, "player": 0, "field": "x", "action": "add"}],
    [{"stage": 2, "player": 0, "field": "x", "action": "add"}],
    [{"stage": 0, "player": -1, "field": "x", "action": "add"}],
    [{"stage": 0, "player": 0, "field": "unknown", "action": "add"}],
    [{"stage": 0, "player": 0, "field": "x", "action": "replace"}],
    [{"stage": 0, "player": 0, "field": "x", "action": "remove"}],
    [{"stage": 0, "player": 0, "field": "x", "action": "add", "verified": True}],
    [{"stage": 0, "player": 0, "field": "x", "action": a} for a in ("add", "add")],
    [{"stage": 0, "player": 0, "field": "x", "action": a} for a in ("add", "remove")],
    [{"stage": 0, "player": 0, "field": "x", "action": "add"}] * 5])
def test_invalid_patches_fail_atomically(edits):
    before = [[[], []], [[], []]]
    with pytest.raises(ValueError): apply_patch(before, ("x",), edits)
    assert before == [[[], []], [[], []]]


def test_illegal_input_and_noop_add_not_silently_cleaned():
    with pytest.raises(ValueError): apply_patch([[[], []]], ("x",), [])
    with pytest.raises(ValueError): apply_patch([[["x", "x"], []], [[], []]], ("x",), [])
    with pytest.raises(ValueError): apply_patch([[["x"], []], [[], []]], ("x",), [
        {"stage": 0, "player": 0, "field": "x", "action": "add"}])


def test_schema_only_representation_changes_and_proposal_is_never_repaired(bundle):
    m, _ = D.package("luna6"); case = bundle["cases"]["case_608"]["case"]
    r = repair_schema(m, case, "rewrite"); p = repair_schema(m, case, "patch")
    assert r == output_schema(m, case, "C")
    assert r["properties"]["proposal"] == p["properties"]["proposal"]
    assert p["properties"]["edits"]["maxItems"] == 16
    original = bundle["seeds"]["s05"]["original_table"]
    bad_proposal = {"decision": "bad"}
    e = expand_repair_output({"edits": [], "proposal": bad_proposal}, "patch", original, case["fields"])
    assert e["proposal"] == bad_proposal  # The original scorer must reject it.
    with pytest.raises(ValueError): expand_repair_output({"edits": [], "proposal": bad_proposal, "stage_table": original}, "patch", original, case["fields"])
    with pytest.raises(ValueError): repair_schema(m, case, "unknown")


def test_preregistered_luna_plan_preserves_controls_and_contract(bundle):
    protocol = json.loads((ROOT / "configs/gamespec_patch_diagnostic_v12_2026-11-05.json").read_text())
    assert protocol["model_generation_calls"] == 0
    assert protocol["model"]["model_id"] == "gpt-6-luna"
    assert protocol["model"]["temperature"] == 0 and protocol["model"]["reasoning_effort"] == "none"
    plan = protocol["schedule"]["plan"]
    assert len(plan) == len({r["trial_id"] for r in plan}) == 72
    assert Counter(r["seed_kind"] for r in plan) == {"wrong": 36, "correct_control": 36}
    assert set(Counter((r["seed_id"], r["seed_kind"], r["feedback"], r["representation"]) for r in plan).values()) == {3}
    first_per_pattern = {}
    for sid, s in bundle["seeds"].items(): first_per_pattern.setdefault(s["canonical_pattern"], sid)
    assert list(first_per_pattern.values()) == protocol["selection"]["seed_ids"] == ["s00", "s05", "s07"]
    m, _ = D.package("luna6")
    for cid, schemas in protocol["schemas"].items():
        for fmt, schema in schemas.items(): assert schema == repair_schema(m, bundle["cases"][cid]["case"], fmt)
    for p, expected in protocol["sources_sha256"].items():
        assert sha256((ROOT / p).read_bytes()).hexdigest() == expected


def test_stored_audit_reproduces_without_replacing_old_results():
    stored = json.loads(D.OUT.read_text())
    assert D.build() == stored
