import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RESULT = (
    ROOT
    / "research/results/five_die_observation_stratification_confirmation_2026-10-15.json"
)


def report():
    return json.loads(RESULT.read_text())


def test_bounded_confirmation_passes_every_frozen_gate():
    value = report()
    assert value["audit_completed"] is True
    assert value["bounded_confirmation_passed"] is True
    assert value["passed"] is True
    assert all(value["gates"].values())
    assert value["observation_replicas"] == 4


def test_candidate_improves_observation_coverage_without_changing_regret_trace():
    value = report()
    baseline = value["baseline"]["metrics"]
    candidate = value["candidate"]["metrics"]
    assert baseline["positive_observation_weight_information_sets"] == 23_198
    assert candidate["positive_observation_weight_information_sets"] == 28_486
    assert value["paired_observation_coverage_gain"] == pytest.approx(
        5_288 / 87_192
    )
    assert candidate["fallback_fraction"] == pytest.approx(58_706 / 87_192)
    assert value["gates"]["regret_trace_parity"] is True
    assert value["gates"]["visit_trace_parity"] is True


def test_exploitability_is_noninferior_but_not_claimed_superior():
    value = report()
    baseline = value["baseline"]["independent_evaluation"]["exploitability"]
    candidate = value["candidate"]["independent_evaluation"]["exploitability"]
    assert baseline == pytest.approx(0.10059022900019668)
    assert candidate == pytest.approx(0.103625435866181)
    assert value["paired_exploitability_increase"] == pytest.approx(
        candidate - baseline
    )
    assert value["gates"]["exploitability_noninferiority"] is True
    assert value["runtime_epsilon_gto_enabled"] is False
    assert value["full_budget_training_performed"] is False
