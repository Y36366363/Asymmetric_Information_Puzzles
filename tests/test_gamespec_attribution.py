from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

import aip.benchmark.gamespec_attribution as core
from aip.benchmark.gamespec_interface import messages_for as old_messages, parameters as old_parameters
from aip.benchmark.gamespec_prospective import change_witnesses

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
try:
    s=importlib.util.spec_from_file_location("attribution_dispatch",ROOT/"scripts/run_gamespec_attribution.py")
    D=importlib.util.module_from_spec(s); s.loader.exec_module(D)
finally:
    sys.path.pop(0)
M,B=D.package("luna6")


def table(item):
    return core.normalize_table(item["visibility_contexts"],item["case"]["fields"])


class Client:
    def __init__(self,bundle,fail=False,export_error=False):
        self.b=bundle; self.fail=fail; self.export_error=export_error; self.requests=[]
        self.chat=SimpleNamespace(completions=self)

    def create(self,**kwargs):
        self.requests.append(kwargs)
        if self.fail: raise RuntimeError("SECRET must stay private")
        p=self.b["plan"][len(self.requests)-1]
        item=self.b["cases"][p["case_id"]]
        t=table(item); proposal=core.derive_proposal(t,item["case"]["fields"])
        if self.export_error and p["condition"]=="C" and item["kind"]=="dynamic":
            proposal["witness"]["player"]=1-proposal["witness"]["player"]
        payload=proposal if p["condition"]=="A" else {"stage_table":t}
        if p["condition"]=="C": payload["proposal"]=proposal
        text=json.dumps(payload)
        raw={"model":kwargs["model"],"usage":{"prompt_tokens":200,"completion_tokens":120},
             "choices":[{"finish_reason":"stop","message":{"content":text}}]}
        return SimpleNamespace(model=kwargs["model"],usage=SimpleNamespace(prompt_tokens=200,completion_tokens=120),
            choices=[SimpleNamespace(finish_reason="stop",message=SimpleNamespace(content=text,refusal=None))],
            model_dump=lambda **_:raw)


def run_mock(tmp_path,tag="luna6",**kwargs):
    m,b=D.package(tag); raw=Client(b,**kwargs); client=core.AttributionClient(raw)
    r=core.AttributionRunner(m,b,client,tmp_path/f"{tag}.json",lambda _:200,halt_path=tmp_path/"halt.json")
    client.runner=r
    return m,b,raw,r.run()


def test_frozen_reference_and_exact_A_prompt_and_parameters():
    for tag in ("luna6","sol61"):
        m,b=D.package(tag); oldm,oldb=D.v7_package(tag)
        assert m["model"]==oldm["model"] and b["cases"]==oldb["cases"] and b["pairs"]==oldb["pairs"]
        assert len(b["plan"])==180 and len({p["trial_id"] for p in b["plan"]})==180
        for p in b["plan"]:
            msgs=core.messages_for(m,b,p)
            assert msgs[0]==old_messages(oldm,oldb,p)[0]
            assert "reference_owners" not in json.dumps(msgs) and "visibility_contexts" not in json.dumps(msgs)
            if p["condition"]=="A":
                assert msgs==old_messages(oldm,oldb,p)
                assert core.parameters(m,b,p)==old_parameters(oldm,oldb,p)
    with pytest.raises(ValueError): D.package("mini41")
    bad=D.specification(); bad["schedule"]["repeats"]=2
    with pytest.raises(ValueError): core.materialize(*D.v7_package("luna6"),bad)


def test_all_frozen_references_roundtrip_without_new_truth_labels():
    assert len(D.preflight())==12
    for p in B["plan"]:
        schema=core.output_schema(M,B["cases"][p["case_id"]]["case"],p["condition"])
        assert schema["additionalProperties"] is False
        if p["condition"]!="A":
            t=schema["properties"]["stage_table"]
            assert t["minItems"]==t["maxItems"]==2
            assert set(t["items"]["items"]["items"]["enum"])==set(B["cases"][p["case_id"]]["case"]["fields"])


@pytest.mark.parametrize("case_id",list(B["cases"]))
def test_table_cell_faults_are_scored_even_when_export_accidentally_correct(case_id):
    item=B["cases"][case_id]; correct=table(item)
    for phase in range(2):
        for player in range(2):
            for field in item["case"]["fields"]:
                wrong=deepcopy(correct)
                if field in wrong[phase][player]: wrong[phase][player].remove(field)
                else: wrong[phase][player].append(field)
                e=core.evaluate(json.dumps({"stage_table":wrong}),"B",item)
                assert e["table_correct"] is False and len(e["table_cell_differences"])==1
                assert "stage_table_mismatch" in e["categories"]


def test_wrong_table_correct_witness_is_not_understanding_success():
    item=next(i for i in B["cases"].values() if i["kind"]=="dynamic")
    wrong=table(item)
    public=next(f for f in item["case"]["fields"] if f in wrong[0][0] and f in wrong[0][1])
    for phase in range(2): wrong[phase][0].remove(public)
    e=core.evaluate(json.dumps({"stage_table":wrong}),"B",item)
    assert e["legacy"]["correct"] and not e["table_correct"] and not e["whole_response_correct"]
    assert "wrong_table_correct_reference_proposal" in e["categories"]


def test_program_export_is_reference_free_and_never_visible_is_explicit_failure():
    item=next(iter(B["cases"].values())); t=table(item)
    fields=item["case"]["fields"]
    assert core.derive_proposal(t,fields)==core.derive_proposal(t,list(fields))
    invisible=[[[],[]],[[],[]]]
    with pytest.raises(ValueError,match="never-visible"): core.derive_proposal(invisible,fields)
    e=core.evaluate(json.dumps({"stage_table":invisible}),"B",item)
    assert "deterministic_export_failure" in e["categories"]


@pytest.mark.parametrize("fault",["duplicate","unknown","shape","extra_key","nonfinite"])
def test_bad_stage_interfaces_are_not_silently_repaired(fault):
    item=next(iter(B["cases"].values())); payload={"stage_table":table(item)}
    if fault=="duplicate": payload["stage_table"][0][0].append(payload["stage_table"][0][0][0])
    elif fault=="unknown": payload["stage_table"][0][0].append("unknown_field")
    elif fault=="shape": payload["stage_table"].pop()
    elif fault=="extra_key": payload["reference"]=True
    text=json.dumps(payload) if fault!="nonfinite" else '{"stage_table":NaN}'
    e=core.evaluate(text,"B",item)
    assert not e["whole_response_correct"] and e["interface_errors"]


@pytest.mark.parametrize("tag",["luna6","sol61"])
def test_all_180_assignments_replay_and_tamper_checks(tmp_path,tag):
    m,b,raw,r=run_mock(tmp_path,tag)
    result=core.replay(m,b,r)
    assert r["status"]=="completed" and len(raw.requests)==180 and len(result["rows"])==180
    for c,a in result["summary"]["conditions"].items():
        assert a["assigned"]==60 and a["dynamic_witness_correct"]["numerator"]==30
        if c!="A": assert a["table_correct_all"]["numerator"]==60
    for fault in ("request","cost","score","raw"):
        bad=deepcopy(r)
        if fault=="request": bad["attempts"][0]["provider_parameters"]["reasoning_effort"]="high"
        elif fault=="cost": bad["attempts"][0]["cost_usd"]=0
        elif fault=="raw": bad["attempts"][0]["raw_response"]["choices"][0]["message"]["content"]="{}"
        else: bad["trials"][0]["evaluation"]["table_correct"]=True
        with pytest.raises(ValueError): core.replay(m,b,bad)


def test_correct_table_wrong_witness_is_direct_export_evidence(tmp_path):
    m,b,raw,r=run_mock(tmp_path,export_error=True)
    a=core.replay(m,b,r)["summary"]
    assert a["conditions"]["C"]["table_correct_dynamic"]["numerator"]==30
    assert a["conditions"]["C"]["dynamic_witness_correct"]["numerator"]==0
    assert a["conditions"]["C"]["correct_table_wrong_witness_conditional"]["rate"]==1
    assert a["conditions"]["C"]["correct_table_valid_proposal_wrong_witness"]["rate"]==1
    assert len(a["all_failures"])==30


def test_provider_failure_preserves_180_assignments_and_no_secret_message(tmp_path):
    m,b,raw,r=run_mock(tmp_path,fail=True)
    assert r["status"]=="stopped" and len(raw.requests)==1 and len(r["analysis"]["all_failures"])==180
    assert "SECRET" not in json.dumps(r)
    assert core.replay(m,b,r)["summary"]["provider_attempts"]==1


def test_oracle_disagreement_writes_global_stop_and_stops_other_model(tmp_path,monkeypatch):
    def disagree(*args,**kwargs): raise ValueError("independent_table_oracle_disagreement")
    monkeypatch.setattr(core,"score",disagree)
    _,_,raw,r=run_mock(tmp_path)
    assert r["stop_reason"]=="independent_table_oracle_disagreement" and len(raw.requests)==1
    assert (tmp_path/"halt.json").exists() and "oracle_counterexample" in r
    _,_,raw2,r2=run_mock(tmp_path,tag="sol61")
    assert r2["stop_reason"]=="global_oracle_stop" and not raw2.requests


def test_exploratory_statistics_keep_rule_clusters_and_holm_floor_visible():
    one={"dynamic_pair_differences":{"B":[1]*6,"C":[0]*6}}
    rows=core.compare_statistics({"luna6":one,"sol61":one})
    for row in rows:
        assert len(row["pair_differences"])==6
        assert row["two_sided_p"]==(2/64 if row["contrast"]=="B-A" else 1)
        assert row["holm_adjusted_p"]>=0.125
        assert not row["exploratory_below_005"]
