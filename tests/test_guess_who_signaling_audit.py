import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "research/results/guess_who_signaling_2026-10-03.json"
POSTHOC = ROOT / "research/results/guess_who_signaling_posthoc_2026-10-03.json"


def test_preregistered_signal_endpoint_is_a_valid_zero_result():
    report = json.loads(AUDIT.read_text())
    assert report["primary_endpoint"]["classification"] == "zero_result"
    assert report["primary_endpoint"]["value"] <= 1e-8
    assert report["primary_endpoint"]["reversed_enumeration_value"] <= 1e-8
    assert report["checks"]["frozen_rules_match"] is True
    assert report["checks"]["tree_audit"] is True
    assert report["checks"]["independent_exploitability_gate"] is True
    assert report["checks"]["endpoint_enumeration_invariance"] is True
    assert report["runtime_epsilon_gto_allowed"] is False


def test_preregistered_cfr_failure_is_retained_without_relaxing_gate():
    report = json.loads(AUDIT.read_text())
    algorithms = report["regret_minimization_cross_check"]
    assert algorithms["cfr_plus"]["independent_evaluation"]["passed"] is True
    assert algorithms["dcfr"]["independent_evaluation"]["passed"] is True
    assert algorithms["vanilla_cfr"]["independent_evaluation"]["passed"] is False
    assert algorithms["vanilla_cfr"]["independent_evaluation"]["exploitability"] > 0.001
    assert report["checks"]["all_cfr_cross_checks"] is False
    assert report["passed"] is False
    assert report["undertrained_negative_control"]["passed_gate"] is False


def test_posthoc_budget_diagnostic_does_not_rewrite_preregistration():
    result = json.loads(POSTHOC.read_text())
    assert result["label"] == "posthoc_budget_diagnostic_not_preregistered"
    assert result["iterations"] == 5_000
    assert result["exploitability"] < 0.001
    assert result["passed_original_0_001_threshold"] is True
