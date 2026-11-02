from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import socket
import sys
from types import SimpleNamespace

import pytest

from aip.benchmark.gamespec_attribution import AttributionClient, derive_proposal, messages_for, parameters
from aip.benchmark.gamespec_validation import inspect_observation, state_counts, verify_frozen_output
from aip.core.cfr import CFRCertificationGate
from aip.core.evaluation import PromotionEvidence, decide_promotion
from aip.core.observation_validation import (ObservationStatus, ObservationValidation,
    ObservationValidationError, require_reference_verified, require_strategy_observation_authority)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
try:
    spec = importlib.util.spec_from_file_location("targeted_c_dispatch", ROOT / "scripts/run_gamespec_targeted_c.py")
    D = importlib.util.module_from_spec(spec); spec.loader.exec_module(D)
finally:
    sys.path.pop(0)


def payload(item):
    table = deepcopy(item["visibility_contexts"])
    return {"stage_table": table, "proposal": derive_proposal(table, tuple(item["case"]["fields"]))}


class Client:
    def __init__(self, bundle, fault=None):
        self.b, self.fault, self.requests = bundle, fault, []
        self.chat = self.completions = self

    def create(self, **kwargs):
        self.requests.append(kwargs)
        if self.fault == "timeout": raise TimeoutError("PRIVATE provider message must not be logged")
        p = self.b["plan"][len(self.requests) - 1]
        item = self.b["cases"][p["case_id"]]
        result = payload(item)
        if self.fault == "export" and item["kind"] == "dynamic":
            result["proposal"]["witness"]["player"] = 1 - result["proposal"]["witness"]["player"]
        if self.fault == "table" and item["kind"] == "dynamic":
            # Wrong quota owner; voucher witness remains correct.
            result["stage_table"][0][0].append("quota")
            result["stage_table"][1][0].append("quota")
        text = "{" if self.fault == "invalid_json" else json.dumps(result)
        reason = "length" if self.fault == "truncated" else "stop"
        raw = {"model": kwargs["model"], "usage": {"prompt_tokens": 200, "completion_tokens": 120},
               "choices": [{"finish_reason": reason, "message": {"content": text}}]}
        return SimpleNamespace(model=kwargs["model"], usage=SimpleNamespace(prompt_tokens=200, completion_tokens=120),
            choices=[SimpleNamespace(finish_reason=reason, message=SimpleNamespace(content=text, refusal=None))],
            model_dump=lambda **_: raw)


def mock_run(tmp_path, tag="luna6", fault=None):
    m, b = D.package(tag)
    raw = Client(b, fault); client = AttributionClient(raw)
    r = D.TargetedRunner(m, b, client, tmp_path / f"{tag}.json", lambda _: 100, halt_path=tmp_path / "halt.json")
    client.runner = r
    return m, b, raw, r.run()


def test_exact_two_cases_twenty_calls_and_old_C_requests_unchanged():
    for tag in ("luna6", "sol61"):
        m, b = D.package(tag); om, ob = D.old_package(tag)
        assert len(b["plan"]) == 10 and m["schedule"]["maximum_calls"] == 10
        assert len({p["trial_id"] for p in b["plan"]}) == 10
        assert {p["case_id"] for p in b["plan"]} == {"case_417", "case_345"}
        assert b["cases"] == ob["cases"] and m["model"] == om["model"]
        for p in b["plan"]:
            assert messages_for(m, b, p) == messages_for(om, ob, p)
            assert parameters(m, b, p) == parameters(om, ob, p)
        assert ("temperature" in parameters(m, b, b["plan"][0])) == (tag == "luna6")


@pytest.mark.parametrize("tag", ["luna6", "sol61"])
def test_mock_success_replays_offline_and_has_no_automatic_runtime_authority(tmp_path, monkeypatch, tag):
    m, b, raw, report = mock_run(tmp_path, tag)
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: pytest.fail("offline replay used network"))
    assert D.replay(m, b, report)["raw_rescoring_agrees"]
    assert report["analysis"]["overall"]["states"] == {"reject_local": 0, "locally_consistent_unverified": 0, "verified": 10}
    assert not report["analysis"]["old_A_latent_error_layer_identified"]
    assert not report["runtime_epsilon_gto_allowed"]
    assert len(raw.requests) == 10


@pytest.mark.parametrize("fault", ["export", "table", "invalid_json", "truncated"])
def test_failure_quadrants_and_interfaces_preserved(tmp_path, fault):
    m, b, _, report = mock_run(tmp_path, fault=fault)
    assert D.replay(m, b, report)["raw_rescoring_agrees"]
    overall = report["analysis"]["overall"]
    if fault == "export":
        assert overall["quadrants"]["table_correct_proposal_wrong"] == 5
    elif fault == "table":
        assert overall["quadrants"]["table_wrong_proposal_correct"] == 5
        assert overall["states"]["locally_consistent_unverified"] == 5
    else:
        assert overall["quadrants"]["interface_or_transport_error"] == 10
        assert overall["states"]["verified"] == 0


def test_timeout_stops_no_retry_and_retains_ten_assigned_denominator(tmp_path):
    m, b, raw, report = mock_run(tmp_path, fault="timeout")
    assert report["status"] == "stopped" and len(raw.requests) == 1
    assert report["analysis"]["overall"]["assigned"] == 10
    assert report["analysis"]["overall"]["completed"] == 0
    assert report["attempts"][0]["errors"] == ["timeout"]
    assert "PRIVATE" not in json.dumps(report)
    assert D.replay(m, b, report)["raw_rescoring_agrees"]
    with pytest.raises(FileExistsError):
        mock_run(tmp_path)


def test_oracle_disagreement_journals_and_stops(tmp_path, monkeypatch):
    def disagree(*a, **k): raise ValueError("oracle paths disagree")
    monkeypatch.setattr(D, "verify_frozen_output", disagree)
    _, _, raw, report = mock_run(tmp_path)
    assert len(raw.requests) == 1 and report["status"] == "stopped"
    assert (tmp_path / "halt.json").exists()
    assert report["oracle_counterexample"]["raw_text"]


@pytest.mark.parametrize("change", ["request", "cost", "score", "raw", "assignment", "summary"])
def test_replay_rejects_tampering(tmp_path, change):
    m, b, _, report = mock_run(tmp_path)
    if change == "request": report["attempts"][0]["messages"][0]["content"] += "changed"
    elif change == "cost": report["attempts"][0]["cost_usd"] += 1
    elif change == "score": report["trials"][0]["evaluation"]["table_correct"] = False
    elif change == "raw": report["trials"][0]["raw_text"] = "{}"
    elif change == "assignment": report["trials"][0]["case_id"] = "case_345"
    else: report["analysis"]["overall"]["completed"] = 0
    with pytest.raises(ValueError): D.replay(m, b, report)


def test_three_states_never_implicitly_truthy_and_no_dict_certificates():
    item = D.package("luna6")[1]["cases"]["case_345"]
    p = payload(item)
    local, _, subject = inspect_observation(tuple(item["case"]["fields"]), table=p["stage_table"], proposal=p["proposal"])
    verified, _, subject, _ = verify_frozen_output(json.dumps(p), "C", item)
    rejected, _, _ = inspect_observation(tuple(item["case"]["fields"]), table=[])
    assert require_reference_verified(verified, subject, item) is verified
    for record in (local, rejected, verified):
        with pytest.raises(ObservationValidationError): bool(record)
        for invalid in (record, record.to_artifact(), {"status": "verified"}):
            with pytest.raises(ObservationValidationError): require_strategy_observation_authority(invalid)
            with pytest.raises(ObservationValidationError): decide_promotion(PromotionEvidence(observation_validation=invalid))
            with pytest.raises(ObservationValidationError): CFRCertificationGate().evaluate(None, evaluation=None, observation_validation=invalid)
    for bad in (local, rejected, verified.to_artifact()):
        with pytest.raises(ObservationValidationError): require_reference_verified(bad, subject, item)
    with pytest.raises(ObservationValidationError): require_reference_verified(verified, {}, item)
    with pytest.raises(ObservationValidationError): require_reference_verified(verified, subject, {})
    with pytest.raises(ObservationValidationError): ObservationValidation(ObservationStatus.VERIFIED, "forged")
    assert state_counts([local, rejected, verified]) == {"assigned": 3,
        "states": {"reject_local": 1, "locally_consistent_unverified": 1, "verified": 1},
        "combined_pass_rate": None, "reason": "local consistency and reference verification are separate endpoints"}


def test_accidentally_correct_witness_does_not_verify_wrong_table():
    item = D.package("luna6")[1]["cases"]["case_345"]
    p = payload(item)
    for phase in p["stage_table"]: phase[0].append("quota")
    record, _, _, e = verify_frozen_output(json.dumps(p), "C", item)
    assert e["legacy"]["correct"] and not e["table_correct"]
    assert record.status is ObservationStatus.UNVERIFIED and record.semantic_result == "mismatched"


def test_legacy_promotion_without_observation_evidence_remains_compatible():
    assert decide_promotion(PromotionEvidence()).failures == ("artifact_incomplete",)


def test_old_360_and_192_control_denominators_remain_distinct_offline(monkeypatch):
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: pytest.fail("offline audit used network"))
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import audit_gamespec_validation
        result = audit_gamespec_validation.audit()
    finally:
        sys.path.pop(0)
    assert result["states"]["assigned"] == 360
    assert result["states"]["states"] == {"reject_local": 10, "locally_consistent_unverified": 12, "verified": 338}
    coverage = result["local_coverage"]
    assert coverage["actual_model_outputs"]["residual_wrong_tables"] == 12
    assert coverage["derived_mutation_controls"]["unflagged_wrong_tables"] == 151
    assert "151/192" in coverage["boundary_warning"]
    assert result["all_204_reference_and_mutation_local_records_blocked"]
