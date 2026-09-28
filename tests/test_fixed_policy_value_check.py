"""Regression tests for the explicit-prior/fixed-policy manipulation gate."""

import json

import pytest

from scripts.run_fixed_policy_value_check import (
    PROBE_COUNT,
    REPEATS,
    _reference,
    build_report,
    require_liar_gate,
)
from scripts.run_structured_value_manipulation import _game_material


def _rows(*, posterior_error=0.0, unstable=False):
    rows = []
    for probe in range(PROBE_COUNT):
        for repeat in range(1, REPEATS + 1):
            action = "best" if not (unstable and repeat == 2) else "other"
            rows.append({
                "probeId": f"probe-{probe}",
                "repeat": repeat,
                "status": "valid",
                "chosenActionId": action,
                "inputTokenMatch": True,
                "score": {
                    "basePriorBrier": 0.0,
                    "policyReachWeightMae": 0.0,
                    "posteriorBrier": posterior_error,
                    "immediateValueMae": 0.0,
                    "continuationValueMae": 0.0,
                    "totalValueMae": 0.0,
                    "maximumAdditivityResidual": 0.0,
                    "finalActionRegret": 0.0,
                    "optimalActionAgreement": True,
                    "decisionConsistentWithReportedValues": True,
                },
            })
    return rows


def test_fixed_policy_gate_passes_exact_rows_and_preserves_negative_controls():
    plan = {
        "game": "liar",
        "maxProviderCalls": PROBE_COUNT * REPEATS,
        "claimRestriction": "calculation only",
    }
    assert build_report(plan, _rows())["gatePassed"] is True
    inaccurate = build_report(plan, _rows(posterior_error=0.1))
    assert inaccurate["gatePassed"] is False
    assert inaccurate["gateChecks"]["conditionedPosteriorBrier"] is False
    unstable = build_report(plan, _rows(unstable=True))
    assert unstable["gatePassed"] is False
    assert unstable["gateChecks"]["repeatActionAgreement"] is False


def test_liar_and_goofspiel_use_same_conditioning_contract():
    for game in ("liar", "goofspiel"):
        probes, oracle = _game_material(game)
        reference = _reference(game, probes[0], oracle)
        assert len(reference.base_prior) == len(reference.values.posterior)
        assert sum(reference.base_prior.values()) == pytest.approx(1)
        assert reference.to_response_payload()["belief_update"]["target"]


def test_goofspiel_gate_rejects_failed_liar_report(tmp_path):
    path = tmp_path / "report.json"
    path.write_text(json.dumps({
        "schemaVersion": "aip-fixed-policy-value-report-v1",
        "game": "liar",
        "gatePassed": False,
    }))
    with pytest.raises(ValueError, match="blocked"):
        require_liar_gate(path)
