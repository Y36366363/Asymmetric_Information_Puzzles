from collections import Counter
import importlib.util
import json
from pathlib import Path
import socket
import sys

from aip.benchmark.gamespec_cell_audit import apply_patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
try:
    spec = importlib.util.spec_from_file_location("portable_patch_replay", ROOT / "scripts/replay_gamespec_patch_portable.py")
    D = importlib.util.module_from_spec(spec); spec.loader.exec_module(D)
finally:
    sys.path.pop(0)


def test_all_actual_replies_replay_without_sdk_network_or_host_match(monkeypatch):
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network forbidden")))
    # CI intentionally has no optional OpenAI SDK. Replaying must not inspect it.
    import importlib.metadata
    monkeypatch.setattr(importlib.metadata, "distribution", lambda *a, **k: (_ for _ in ()).throw(AssertionError("SDK metadata forbidden")))
    report = D.verify()
    assert report["raw_rescoring_agrees"] and not report["dispatch_authority"]


def test_noop_failures_and_control_rejections_are_not_applied_corruption():
    _, b = D.package()
    raw = json.loads((D.OUT / "luna6.json").read_text())
    audit = json.loads((D.OUT / "operation_audit.json").read_text())
    notes = json.loads((D.OUT / "measurement_notes.json").read_text())
    trials = {t["trial_id"]: t for t in raw["trials"]}
    assert audit["patch_outputs"] == 36 and audit["invalid_patches"] == audit["outputs_containing_noop"] == 20
    assert audit["outputs_containing_repeated_cell"] == 0 and audit["empty_patch_outputs"] == 2
    assert audit["valid_wrong_input_patch_outputs"] == 8 and audit["valid_wrong_input_patch_repairs"] == 0
    effects = Counter()
    for r in audit["rows"]:
        t = trials[r["trial_id"]]; seed = b["seeds"][t["seed_id"]]
        original = seed["original_table"] if t["seed_kind"] == "wrong" else seed["correct_control"]
        fields = b["cases"][t["case_id"]]["case"]["fields"]
        if r["invalid_patch"]:
            try: apply_patch(original, fields, r["edits"])
            except ValueError: pass
            else: raise AssertionError("invalid patch silently accepted")
            assert t["expanded_output"] is None and t["cell_ledger"] is None
        else:
            assert apply_patch(original, fields, r["edits"]) == t["expanded_output"]["stage_table"]
            effects.update(o["effect"] for o in r["operation_labels"])
    assert dict(effects) == notes["operation_counts_on_strictly_accepted_patches"]
    for f in ("none", "local"):
        for fmt in ("rewrite", "patch"):
            s = notes["control_preservation_denominators"][f][fmt]
            assert s["reference_correct"] + s["valid_result_table_wrong"] + s["invalid_or_missing_result_table"] == s["assigned"] == 9
            assert s["assigned_preservation_failures"] == s["valid_result_table_wrong"] + s["invalid_or_missing_result_table"]
