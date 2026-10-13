import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RESULT = (
    ROOT / "research/results/standard_sampling_fallback_confirmation_2026-10-13.json"
)


def report():
    return json.loads(RESULT.read_text())


def test_both_games_pass_every_frozen_confirmation_gate():
    value = report()
    assert value["passed"] is True
    assert value["all_small_game_gates_passed"] is True
    for game in value["games"].values():
        assert game["passed"] is True
        assert all(game["gates"].values())
        assert len(game["runs"]) == 5


def test_kuhn_is_exactly_legacy_when_no_fallback_is_used():
    game = report()["games"]["canonical_kuhn_poker"]
    assert game["summary"]["candidate_mean_exploitability"] == pytest.approx(
        0.003060405291647067
    )
    assert game["summary"]["mean_paired_exploitability_difference"] == 0
    assert all(run["diagnostics"]["fallback_fraction"] == 0 for run in game["runs"])


def test_one_die_passes_absolute_and_paired_noninferiority_gates():
    game = report()["games"]["one_die_stepwise_liars_dice"]
    assert game["summary"]["candidate_mean_exploitability"] == pytest.approx(
        0.0006522001130431665
    )
    assert game["summary"]["maximum_candidate_exploitability"] == pytest.approx(
        0.0007946375757844348
    )
    assert game["summary"]["mean_paired_exploitability_difference"] < 0
    for run in game["runs"]:
        assert run["paired_exploitability_difference"] < 0
        assert run["diagnostics"]["fallback_fraction"] <= 0.5
        assert run["diagnostics"]["trace_parity_with_paired_legacy"] is True
        assert run["diagnostics"]["fallback_exactly_equals_zero_weight_set"] is True


def test_confirmation_only_unlocks_separate_five_die_preregistration():
    value = report()
    assert value["five_die_preregistration_allowed"] is True
    assert value["five_die_training_performed"] is False
    assert value["runtime_epsilon_gto_enabled"] is False
