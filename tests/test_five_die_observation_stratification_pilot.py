import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RESULT = (
    ROOT / "research/results/five_die_observation_stratification_pilot_2026-10-15.json"
)


def report():
    return json.loads(RESULT.read_text())


def test_pilot_is_noncertifying_and_all_doses_are_semantically_valid():
    value = report()
    assert value["status"] == "exploratory_pilot_not_certification"
    assert value["passed"] is False
    assert value["runtime_epsilon_gto_enabled"] is False
    assert value["separate_confirmation_required"] is True
    assert all(dose["valid"] for dose in value["doses"])
    assert all(all(dose["gates"].values()) for dose in value["doses"])


def test_observation_doses_increase_coverage_with_diminishing_returns():
    value = report()
    baseline = value["baseline"]["raw_observation_weight_coverage"]
    doses = value["doses"]
    assert baseline == pytest.approx(18_574 / 87_192)
    assert [dose["positive_observation_weight_information_sets"] for dose in doses] == [
        21_044,
        22_505,
        24_287,
    ]
    coverages = [dose["raw_observation_weight_coverage"] for dose in doses]
    assert baseline < coverages[0] < coverages[1] < coverages[2]
    efficiency = [dose["coverage_gain_per_replica"] for dose in doses]
    assert efficiency[0] > efficiency[1] > efficiency[2]


def test_frozen_rule_selects_four_replicas_without_claiming_success():
    value = report()
    assert value["selected_observation_replicas"] == 4
    assert max(
        dose["raw_observation_weight_coverage"] for dose in value["doses"]
    ) < 0.4
    assert value["audit_completed"] is True
