import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREREGISTRATION = (
    ROOT / "configs/standard_sampling_fallback_confirmation_2026-10-13.json"
)


def plan():
    return json.loads(PREREGISTRATION.read_text())


def test_confirmation_is_frozen_and_uses_a_separate_algorithm():
    value = plan()
    assert value["frozen_before_confirmation"] is True
    assert value["candidate_algorithm_id"] == (
        "coverage_aware_external_sampling_mccfr_v1"
    )
    assert value["paired_comparison_algorithm_id"] == "external_sampling_mccfr"


def test_confirmation_seeds_are_disjoint_from_pilot():
    value = plan()
    confirmation = value["confirmation_seeds"]
    pilot = value["pilot_seeds_must_be_excluded"]
    assert len(confirmation) == len(set(confirmation)) == 5
    assert set(confirmation).isdisjoint(pilot)


def test_thresholds_are_fixed_without_a_superiority_claim():
    value = plan()
    assert value["threshold_selection_basis"]["superiority_claim_allowed"] is False
    for game in value["games"].values():
        assert game["maximum_independent_exploitability_each_seed"] == 0.01
        assert game["maximum_mean_exploitability_increase_vs_paired_legacy"] == 0.0005
        assert game["maximum_single_seed_exploitability_increase_vs_paired_legacy"] == 0.001


def test_confirmation_cannot_train_or_promote_five_die():
    boundary = plan()["scope_boundary"]
    assert boundary["train_five_die_in_this_experiment"] is False
    assert boundary["enable_runtime_epsilon_gto_in_this_experiment"] is False
    assert boundary["retain_all_prior_failed_artifacts"] is True
