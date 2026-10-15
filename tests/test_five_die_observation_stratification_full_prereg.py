import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN = (
    ROOT
    / "configs/five_die_observation_stratification_full_preregistration_2026-10-15.json"
)


def plan():
    return json.loads(PLAN.read_text())


def test_full_study_requires_passed_bounded_confirmation_and_complete_epochs():
    value = plan()
    confirmation = json.loads((ROOT / value["bounded_confirmation"]).read_text())
    assert value["status"] == "frozen_before_full_budget_training"
    assert confirmation["bounded_confirmation_passed"] is True
    assert value["iterations"] == value["epoch_size"] * value["epochs"]
    assert value["checkpoints"][-1] == value["iterations"]


def test_full_study_keeps_paired_mechanism_and_independent_br_gates():
    value = plan()
    assert value["observation_replicas"] == 4
    assert value["paired_design"]["same_regret_seed_and_chance_schedule"] is True
    gates = value["mechanism_gates"]
    assert gates["minimum_absolute_coverage_gain_vs_paired_baseline"] == 0.05
    assert gates["maximum_final_independent_exploitability"] == 0.05
    assert gates["independent_best_response_at_every_checkpoint"] is True


def test_mechanism_study_cannot_relax_runtime_certification():
    boundary = plan()["interpretation_boundary"]
    assert boundary["this_is_a_coverage_mechanism_study"] is True
    assert boundary[
        "passing_does_not_satisfy_prior_0_40_fallback_certification_gate"
    ] is True
    assert boundary["passing_does_not_enable_runtime_epsilon_gto"] is True
    assert boundary["complete_tree_audit_still_required"] is True
