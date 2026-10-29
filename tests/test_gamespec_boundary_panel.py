from copy import deepcopy
import importlib.util
from itertools import product
import json
from pathlib import Path
import sys

import pytest

from aip.benchmark.gamespec_boundary_panel import analyze, package, preflight, partition_proposal, failure_categories
from aip.benchmark.gamespec_interface import ParameterClient, messages_for
from aip.benchmark.gamespec_prospective import change_witnesses, score
from test_gamespec_prospective import Client

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
try:
    spec = importlib.util.spec_from_file_location("boundary_dispatch", ROOT / "scripts/run_gamespec_boundary_panel.py")
    D = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(D)
finally:
    sys.path.pop(0)
M, B = D.package("luna6")


def test_selected_configuration_and_hidden_references_unchanged():
    for tag in ("luna6", "sol61"):
        m, b = D.package(tag)
        old, _ = D.v4_package(tag)
        assert m["model"] == old["model"]
        for key in ("system_prompt", "source_priority_prompt", "output_contract"):
            assert m["interface_spec"][key] == old["interface_spec"][key]
        assert len(b["plan"]) == 24 and {p["task"] for p in b["plan"]} == {"scope"}
        for p in b["plan"]:
            text = json.dumps(messages_for(m, b, p))
            for hidden in ("reference_owners", "dynamic_visibility", "required_witness", "additional_witnesses", "all_valid_changes"):
                assert hidden not in text
            assert len(messages_for(m, b, p)) == 2
    with pytest.raises(ValueError): D.package("mini41")


@pytest.mark.parametrize("fault", ["pair_id", "missing", "duplicate", "extra", "repeats", "budget"])
def test_incomplete_or_duplicate_schedule_cannot_hide_under_equal_budget(fault):
    s = D.specification()
    if fault == "pair_id": s["pairs"][1]["pair_id"] = s["pairs"][0]["pair_id"]
    elif fault == "missing": s["schedule"]["scope_case_order"].pop()
    elif fault == "duplicate": s["schedule"]["scope_case_order"][0] = s["schedule"]["scope_case_order"][1]
    elif fault == "extra": s["schedule"]["scope_case_order"][0] = "unknown"
    elif fault == "repeats": s["schedule"]["repeats"] = 3
    else: s["schedule"]["maximum_generation_calls"] += 1
    with pytest.raises(ValueError): package(*D.v4_package("luna6"), s)


def test_exhaustive_partition_and_multichange_answer_matrix():
    audit = preflight(B)
    assert audit["passed"] and not audit["main_scorer_changed"]
    assert [len(r["all_valid_changes"]) for r in audit["rows"]] == [1, 1, 4, 2, 1, 2]
    assert sum(r["partitions_checked_per_side"] for r in audit["rows"]) == 486
    assert sum(r["witnesses_checked_per_side"] for r in audit["rows"]) == 192


def test_multiple_candidates_still_require_verified_reference_not_all_alternatives():
    p = B["pairs"][0]; item = B["cases"][p["static_id"]]
    right = partition_proposal(p["owners"])
    wrong = partition_proposal(dict.fromkeys(p["fields"], "public"))
    mixed = deepcopy(right); mixed["candidates"] += wrong["candidates"]
    assert score(json.dumps(mixed), item)["correct"]
    assert not score(json.dumps(wrong), item)["correct"]


@pytest.mark.parametrize("pair", B["pairs"], ids=lambda p:p["pair_id"])
def test_reporting_categories_use_all_valid_changes_without_scoring_override(pair):
    item = B["cases"][pair["dynamic_id"]]
    changes = change_witnesses(item["visibility_contexts"])
    for field, player, before, after in product(pair["fields"], (0, 1), (False, True), (False, True)):
        witness = dict(field=field, player=player, before_visible=before, after_visible=after)
        payload = {"decision":"refusal", "candidates":[], "witness":witness}
        assert (not failure_categories(payload, item)) == (witness in changes)


@pytest.mark.parametrize("tag", ["luna6", "sol61"])
def test_alternative_witness_raw_replay_and_no_reference_mutation(tmp_path, tag):
    m, b = D.package(tag)
    before = deepcopy(b)
    class AlternativeClient(Client):
        def create(self, **kwargs):
            result = super().create(**kwargs)
            raw = result.model_dump()
            payload = json.loads(raw["choices"][0]["message"]["content"])
            case_id = kwargs["messages"][-1]["content"].split("Case: ")[1].split("\n")[0]
            item = b["cases"][case_id]
            if item["kind"] == "dynamic":
                payload["witness"] = deepcopy(change_witnesses(item["visibility_contexts"])[-1])
                text = json.dumps(payload)
                raw["choices"][0]["message"]["content"] = text
                result.choices[0].message.content = text
            return result
    from aip.benchmark.gamespec_prospective import ProspectiveRunner
    raw = AlternativeClient(b); client = ParameterClient(raw)
    runner = ProspectiveRunner(m, b, client, tmp_path / "report.json", lambda _:200); client.runner=runner
    report = runner.run(); a = analyze(m, b, report)
    assert b == before and len(raw.requests) == 24 and a["joint_correct"] == 12
    assert not a["all_failures"] and not a["independent_held_out"] and not a["deployment_permission"]
    assert a["authored_pair_count"] == 6 and a["independently_sampled_rule_instances"] == 0
    assert report["analysis"]["groups"]["repair"]["assigned"] == 0
    for fault in ("parameters", "score", "raw"):
        bad = deepcopy(report)
        if fault == "parameters": bad["attempts"][0]["provider_parameters"]["reasoning_effort"] = "high"
        elif fault == "score": bad["trials"][0]["evaluation"]["correct"] = False
        else: bad["attempts"][0]["raw_response"]["model"] = "another-model"
        with pytest.raises(ValueError): analyze(m, b, bad)


@pytest.mark.parametrize("provider_error", [False, True])
def test_failed_model_and_incomplete_runs_preserve_all_assignments(tmp_path, provider_error):
    from aip.benchmark.gamespec_prospective import ProspectiveRunner
    raw = Client(B, wrong=True, fail=provider_error); client = ParameterClient(raw)
    runner = ProspectiveRunner(M, B, client, tmp_path / "report.json", lambda _:200); client.runner=runner
    report = runner.run(); a = analyze(M, B, report)
    assert len(a["all_failures"]) == 24 and a["joint_correct"] == 0
    assert a["groups"]["static"]["assigned"] == a["groups"]["dynamic"]["assigned"] == 12
    assert "SECRET" not in json.dumps(report)
    if provider_error: assert len(raw.requests) == 1 and report["status"] == "stopped"
