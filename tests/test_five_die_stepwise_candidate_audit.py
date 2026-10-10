import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "research/results/five_die_stepwise_candidate_2026-10-08.json"
PROGRESS = ROOT / "research/results/five_die_stepwise_progress_2026-10-08.json"


def test_fixed_seed_mccfr_candidate_is_complete_but_fails_independent_gate():
    report = json.loads(CANDIDATE.read_text())
    assert report["algorithm"]["algorithm_id"] == "external_sampling_mccfr"
    assert report["algorithm"]["seed"] == 20261008
    assert report["iterations"] == 5_000
    assert report["required_information_sets"] == 87_192
    assert report["sampled_information_sets"] == 25_945
    assert report["uniformly_completed_information_sets"] == 61_247
    evaluation = report["independent_evaluation"]
    assert evaluation["action_value_information_sets"] == 87_192
    assert evaluation["exploitability"] > 0.05
    assert evaluation["passed"] is False
    assert evaluation["failures"] == ["exploitability_above_threshold"]
    assert report["promotion"]["candidate_exploitability_gate_passed"] is False
    assert report["promotion"]["runtime_epsilon_gto_allowed"] is False
    assert report["audit_completed"] is True
    assert report["passed"] is False


def test_both_unilateral_deviation_gains_are_reported_independently():
    evaluation = json.loads(CANDIDATE.read_text())["independent_evaluation"]
    assert evaluation["player_0_deviation_gain"] > 0.05
    assert evaluation["player_1_deviation_gain"] > 0.05
    assert evaluation["nash_conv"] == (
        evaluation["player_0_deviation_gain"]
        + evaluation["player_1_deviation_gain"]
    )
    assert evaluation["exploitability"] == evaluation["nash_conv"] / 2


def test_resumable_audit_has_real_progress_but_is_not_a_certificate():
    progress = json.loads(PROGRESS.read_text())
    latest = progress["chunks"][-1]
    assert progress["rules_id"] == "five_die_liar_two_player_stepwise_v1"
    assert latest["histories"] >= 80_000
    assert latest["information_sets"] >= 20_316
    assert latest["failures"] == []
    assert latest["complete"] is False
    assert latest["structural_audit_passed"] is False
    assert progress["candidate_trained"] is True
    assert progress["candidate_path"].endswith(
        "five_die_stepwise_joint_stratification_2026-10-10.json"
    )
    assert progress["independent_evaluation_complete"] is True
    assert progress["candidate_independent_gate_passed"] is False
    assert progress["candidate_exploitability"] == pytest.approx(
        0.06383412635222224
    )
    assert progress["runtime_epsilon_gto_allowed"] is False
