"""Regression tests for evidence-backed game readiness classifications."""

from scripts.audit_game_readiness import report


def test_readiness_keeps_exact_variants_separate_from_larger_uncertified_games():
    value = report()
    games = value["games"]
    assert games["one-die-stepwise-liars-dice"]["status"] == (
        "complete_declared_variant"
    )
    assert games["one-die-stepwise-liars-dice"]["exploitability"] == 0
    assert games["five-die-liars-dice"]["status"] == "heuristic_only_not_gto"
    assert games["five-die-liars-dice"]["runtimeEpsilonGtoAllowed"] is False
    assert games["goofspiel-four-card"]["exploitability"] == 0
    assert games["kuhn-poker"]["maximumUnilateralDeviationGain"] == 0
    assert games["e-card-single-round"]["exploitability"] == 0


def test_love_letter_subgame_pass_does_not_promote_incomplete_full_round():
    games = report()["games"]
    subgame = games["love-letter-four-card-subgame"]
    full = games["love-letter-full-round"]
    assert subgame["exploitability"] == 0
    assert subgame["informationSets"] == 60
    assert subgame["runtimeFullRoundAllowed"] is False
    assert full["status"] == "blocked_on_complete_structural_enumeration"
    assert full["historiesTraversed"] == 1_142_965
    assert full["structuralAuditComplete"] is False
    assert full["runtimeEpsilonGtoAllowed"] is False
