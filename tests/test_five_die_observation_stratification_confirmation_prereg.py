import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN = (
    ROOT
    / "configs/five_die_observation_stratification_confirmation_2026-10-15.json"
)


def plan():
    return json.loads(PLAN.read_text())


def test_confirmation_uses_selected_dose_new_seed_and_complete_epochs():
    value = plan()
    pilot = json.loads((ROOT / value["pilot_artifact"]).read_text())
    assert value["status"] == "frozen_before_confirmation"
    assert value["selected_observation_replicas"] == (
        pilot["selected_observation_replicas"]
    )
    assert value["seed"] != 731201
    assert value["iterations"] == 7_776 * value["complete_chance_epochs"]


def test_confirmation_has_paired_coverage_and_exploitability_gates():
    gates = plan()["gates"]
    assert gates["minimum_absolute_observation_coverage_gain_vs_paired_baseline"] == 0.05
    assert gates["maximum_exploitability_increase_vs_paired_baseline"] == 0.02
    assert gates["maximum_absolute_independent_exploitability"] == 0.15
    assert gates["regret_and_visit_trace_parity"] is True


def test_bounded_confirmation_cannot_promote_runtime():
    boundary = plan()["scope_boundary"]
    assert boundary["confirmation_is_not_full_candidate_certification"] is True
    assert boundary["runtime_epsilon_gto_allowed"] is False
    assert boundary["do_not_extend_if_failed"] is True
