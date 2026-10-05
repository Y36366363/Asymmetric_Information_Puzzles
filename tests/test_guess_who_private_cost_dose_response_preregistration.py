import json
from pathlib import Path

from aip.puzzles.guess_who import PrivateCostStrategicGuessWhoGame


ROOT = Path(__file__).resolve().parents[1]
PREREGISTRATION = (
    ROOT
    / "configs/guess_who_private_cost_dose_response_preregistration_2026-10-05.json"
)


def test_dose_response_design_is_frozen_and_bound_to_v2_rules():
    preregistration = json.loads(PREREGISTRATION.read_text())
    assert preregistration["frozen_before_outcome_evaluation"] is True
    assert preregistration["rules_id"] == PrivateCostStrategicGuessWhoGame.RULES_ID
    assert preregistration["robustness"][
        "do_not_select_or_refine_dose_grid_after_outcomes"
    ] is True
    assert preregistration["reporting"]["no_posthoc_single_cost_replacement"] is True


def test_dose_grid_and_cost_shape_are_explicit_and_consistent():
    preregistration = json.loads(PREREGISTRATION.read_text())
    design = preregistration["private_question_cost_shape"]
    units = design["unit_cost_levels"]
    maxima = design["maximum_single_question_cost_by_level"]
    shape = design["integer_matrix_by_roster_and_question_order"]
    assert units == [0.0, 0.005, 0.01, 0.02, 0.04, 0.08, 0.16]
    assert len(maxima) == len(units)
    assert all(max(row) == 2 for row in shape)
    assert maxima == [2 * unit for unit in units]
    assert preregistration["solver"]["cfr_cross_check_unit_cost"] == units[-1]


def test_dose_response_keeps_independent_certification_and_runtime_barriers():
    preregistration = json.loads(PREREGISTRATION.read_text())
    assert preregistration["solver"]["maximum_exploitability"] == 1e-10
    assert preregistration["solver"][
        "reverse_roster_and_question_enumeration_at_every_dose"
    ] is True
    assert preregistration["primary_endpoint"]["positive_signal_threshold"] == 1e-6
    assert preregistration["primary_endpoint"]["null_result_threshold"] == 1e-8
    assert preregistration["reporting"]["no_runtime_epsilon_gto_promotion"] is True
    assert preregistration["reporting"]["no_transfer_to_24_character_game"] is True
