from copy import deepcopy
from itertools import product
import importlib.util
import inspect
import json
from pathlib import Path
import socket
import sys
import urllib.request

import pytest

from aip.benchmark.gamespec_attribution import derive_proposal, normalize_table
from aip.benchmark.gamespec_local_checks import check_local
from aip.benchmark.gamespec_boundary_panel import partition_proposal
from aip.benchmark.gamespec_prospective import projection, score

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
try:
    s=importlib.util.spec_from_file_location("local_check_audit",ROOT/"scripts/audit_gamespec_local_checks.py")
    D=importlib.util.module_from_spec(s);s.loader.exec_module(D)
finally:
    sys.path.pop(0)
M,B=D.package("luna6")


def cases():return list(B["cases"].items())


def test_checker_has_no_reference_or_rules_inputs_and_empty_input_cannot_pass():
    assert set(inspect.signature(check_local).parameters)=={"fields","table","proposal","require_observer"}
    e=check_local(["f"])
    assert e["status"]=="reject_local" and not e["semantic_certification_allowed"]


@pytest.mark.parametrize("case_id,item",cases(),ids=[c for c,_ in cases()])
def test_frozen_correct_tables_and_proposals_have_no_false_rejection(case_id,item):
    t=item["visibility_contexts"];fields=tuple(item["case"]["fields"])
    p=derive_proposal(t,fields)
    e=check_local(fields,table=t,proposal=p)
    assert not e["violations"] and e["status"]=="locally_consistent_unverified"
    assert e["semantic_verdict"]=="not_assessed" and not e["semantic_certification_allowed"]


def test_never_visible_field_is_language_scoped_not_a_universal_game_rule():
    table=[[[],[]],[[],[]]]
    restricted=check_local(["nature_only"],table=table)
    relaxed=check_local(["nature_only"],table=table,require_observer=False)
    assert restricted["status"]=="reject_local"
    assert relaxed["status"]=="locally_consistent_unverified"
    assert not relaxed["semantic_certification_allowed"]


@pytest.mark.parametrize("fault",["duplicate","unknown","phase","player","nonstring"])
def test_table_interface_faults_are_rejected_without_gold(fault):
    item=cases()[0][1];t=deepcopy(item["visibility_contexts"])
    if fault=="duplicate":t[0][0].append(t[0][0][0])
    elif fault=="unknown":t[0][0].append("out_of_vocabulary")
    elif fault=="phase":t.pop()
    elif fault=="player":t[0].pop()
    else:t[0][0].append(True)
    r=check_local(tuple(item["case"]["fields"]),table=t)
    assert r["status"]=="reject_local" and r["violations"][0]["code"]=="table_contract_error"


def test_non_change_witness_can_be_rejected_without_rules_or_table():
    field=next(iter(cases()[0][1]["case"]["fields"]))
    proposal={"decision":"refusal","candidates":[],"witness":{
        "field":field,"player":0,"before_visible":True,"after_visible":True}}
    r=check_local(tuple(cases()[0][1]["case"]["fields"]),proposal=proposal)
    assert {v["code"] for v in r["violations"]}=={"non_change_witness"}


def test_candidate_and_witness_inconsistency_with_own_table_is_local():
    item=next(i for _,i in cases() if i["kind"]=="dynamic")
    fields=tuple(item["case"]["fields"]);t=item["visibility_contexts"]
    p=derive_proposal(t,fields);p["witness"]["before_visible"]=not p["witness"]["before_visible"]
    assert "witness_disagrees_with_declared_table" in {v["code"] for v in check_local(fields,table=t,proposal=p)["violations"]}
    p=partition_proposal(dict.fromkeys(fields,"public"))
    assert "candidate_disagrees_with_declared_table" in {v["code"] for v in check_local(fields,table=t,proposal=p)["violations"]}


def test_self_consistent_wrong_owner_remains_unverified_not_certified():
    item=next(i for _,i in cases() if i["kind"]=="static")
    fields=tuple(item["case"]["fields"])
    correct=item["case"]["reference_owners"]
    wrong_count=0
    for values in product(("public","player_0","player_1"),repeat=len(fields)):
        owners=dict(zip(fields,values))
        if owners==correct:continue
        views=[sorted(projection(owners,p)) for p in (0,1)]
        proposal=partition_proposal(owners)
        local=check_local(fields,table=[views,views],proposal=proposal)
        assert local["status"]=="locally_consistent_unverified" and not local["semantic_certification_allowed"]
        assert not score(json.dumps(proposal),item)["correct"]
        wrong_count+=1
    assert wrong_count==3**len(fields)-1


def test_local_verdict_invariant_under_field_rename_and_player_swap():
    item=next(i for _,i in cases() if i["kind"]=="dynamic")
    fields=tuple(item["case"]["fields"]);t=deepcopy(item["visibility_contexts"]);p=derive_proposal(t,fields)
    before=check_local(fields,table=t,proposal=p)
    rename={f:f"arbitrary_{i}" for i,f in enumerate(fields)}
    changed=[[[rename[f] for f in view] for view in phase[::-1]] for phase in t]
    rp=deepcopy(p);rp["witness"]["field"]=rename[rp["witness"]["field"]];rp["witness"]["player"]=1-rp["witness"]["player"]
    after=check_local(tuple(rename.values()),table=changed,proposal=rp)
    assert before["status"]==after["status"] and before["violations"]==after["violations"]


def test_all_360_existing_outputs_audited_with_network_blocked_and_files_unchanged(monkeypatch):
    def forbid(*args,**kwargs):raise AssertionError("Network/model calls forbidden in offline audit")
    monkeypatch.setattr(socket,"create_connection",forbid)
    monkeypatch.setattr(urllib.request,"urlopen",forbid)
    p={tag:D.package(tag) for tag in ("luna6","sol61")}
    paths=[ROOT/f"research/results/gamespec_attribution_v8_2026-10-30/{tag}.json" for tag in p]
    before=[x.read_bytes() for x in paths]
    report=D.audit_reports(p,{t:json.loads(raw) for t,raw in zip(p,before)})
    assert report["all_raw_replays_agree"] and len(report["rows"])==360
    assert report["model_generation_calls"]==0 and report["model_cost_usd"]==0
    assert report["summary"]["false_local_rejections_of_reference_correct_outputs"]==0
    assert report["derived_controls"]["reference_tables"]==12
    assert report["derived_controls"]["single_cell_mutations"]==192
    assert report["derived_controls"]["false_local_rejections"]==0
    assert report["derived_controls"]["all_remain_semantically_uncertified"]
    assert all(not r["local"]["semantic_certification_allowed"] for r in report["rows"])
    assert [x.read_bytes() for x in paths]==before
