"""Regression tests for evidence-backed game readiness classifications."""

import json

from scripts.audit_game_readiness import (
    FIVE_DIE_STEPWISE_PROGRESS,
    LOVE_PROGRESS,
    report,
)


def test_readiness_keeps_exact_variants_separate_from_larger_uncertified_games():
    value = report()
    games = value["games"]
    assert games["one-die-stepwise-liars-dice"]["status"] == (
        "complete_declared_variant"
    )
    assert games["one-die-stepwise-liars-dice"]["exploitability"] == 0
    assert games["five-die-liars-dice"]["status"] == "heuristic_only_not_gto"
    assert games["five-die-liars-dice"]["runtimeEpsilonGtoAllowed"] is False
    assert games["five-die-liars-dice"]["stepwiseCandidateStatus"] == (
        "joint_stratification_candidate_failed_preregistered_gates"
    )
    assert games["five-die-liars-dice"]["stepwiseCandidateRulesId"] == (
        "five_die_liar_two_player_stepwise_v1"
    )
    assert games["five-die-liars-dice"]["stepwiseCandidateEstimatedHistories"] == 43_818_013
    stepwise_latest = json.loads(FIVE_DIE_STEPWISE_PROGRESS.read_text())["chunks"][-1]
    assert games["five-die-liars-dice"]["stepwiseHistoriesAudited"] == (
        stepwise_latest["histories"]
    )
    assert games["five-die-liars-dice"]["stepwiseInformationSetsObserved"] == (
        stepwise_latest["information_sets"]
    )
    assert games["five-die-liars-dice"]["stepwiseStructuralFailures"] == []
    assert games["five-die-liars-dice"]["stepwiseStructuralAuditComplete"] is False
    assert games["five-die-liars-dice"]["stepwiseCandidateExploitability"] > 0.05
    assert games["five-die-liars-dice"]["stepwiseCandidateSampledCoverage"] > 0.5
    assert games["five-die-liars-dice"]["stepwiseCandidateSampledCoverage"] < 0.6
    assert games["five-die-liars-dice"]["stepwiseCoverageGatePassed"] is False
    assert games["five-die-liars-dice"]["stepwiseIndependentGatePassed"] is False
    assert games["five-die-liars-dice"]["stepwiseRetainedBaselineExploitability"] > 0.05
    assert games["five-die-liars-dice"]["stepwiseCandidateIterations"] == 62_208
    assert games["five-die-liars-dice"]["stepwiseJointChanceMarginalsExact"] is True
    assert games["goofspiel-four-card"]["exploitability"] == 0
    assert games["kuhn-poker"]["maximumUnilateralDeviationGain"] == 0
    assert games["e-card-single-round"]["exploitability"] == 0
    guess = games["guess-who-strategic-three-character"]
    assert guess["status"] == "complete_certified_research_subgame"
    assert guess["histories"] == 1_651
    assert guess["informationSets"] == 404
    assert guess["exploitability"] < 1e-10
    assert guess["explicitGuessAction"] is True
    assert guess["frozenRulesId"] == "strategic_guess_who_simultaneous_v1"
    assert guess["signalingExperimentStatus"] == (
        "valid_zero_result_with_cfr_crosscheck_failure_retained"
    )
    assert guess["maximumRootPolicyL1ByPrivateSecret"] < 1e-8
    assert guess["privateCostExperimentStatus"] == (
        "valid_zero_result_all_preregistered_crosschecks_passed"
    )
    assert guess["privateCostMaximumRootPolicyL1"] < 1e-8
    assert guess["privateCostRulesId"] == (
        "strategic_guess_who_private_question_cost_v2"
    )
    assert guess["runtimeEpsilonGtoAllowed"] is False


def test_love_letter_subgame_pass_does_not_promote_incomplete_full_round():
    games = report()["games"]
    subgame = games["love-letter-four-card-subgame"]
    full = games["love-letter-full-round"]
    assert subgame["exploitability"] == 0
    assert subgame["informationSets"] == 60
    assert subgame["runtimeFullRoundAllowed"] is False
    assert full["status"] == "blocked_on_complete_structural_enumeration"
    latest_checkpoint = json.loads(LOVE_PROGRESS.read_text())["chunks"][-1]
    assert full["historiesTraversed"] == latest_checkpoint["histories"]
    assert full["historiesTraversed"] >= 1_352_853
    assert latest_checkpoint["complete"] is False
    assert full["structuralAuditComplete"] is False
    assert full["runtimeEpsilonGtoAllowed"] is False
    prior = subgame["combinatorialPrior"]
    assert prior["status"] == "implemented_and_independently_audited"
    assert prior["positiveReachInformationSets"] == 17
    assert prior["zeroReachInformationSets"] == 43
    assert prior["usesUniformActionBaseline"] is False
    assert subgame["structuredExperimentStatus"] == (
        "retired_as_belief_update_target_no_identifiable_post_action_hidden_state"
    )
    assert subgame["fixedPolicyPositiveReachInformationSets"] == 60
    assert subgame["fixedPolicyMaximumPosteriorL1Shift"] == 0
    assert subgame["fixedPolicyExploitability"] > 0.001
    assert subgame["collapsedPosteriorSupportSizeCounts"] == {"1": 48, "2": 12}
    assert subgame["postActionNontrivialHiddenStateInformationSets"] == 0


def test_redefined_liar_gate_and_identical_goofspiel_protocol_pass():
    games = report()["games"]
    liar = games["one-die-stepwise-liars-dice"]
    goofspiel = games["goofspiel-four-card"]
    assert liar["originalAmbiguousPosteriorCheck"] == "failed_retained"
    assert liar["fixedPolicyV1Check"] == "failed_retained"
    assert liar["fixedPolicyV2Check"] == "passed"
    assert liar["fixedPolicyV2RepeatActionAgreement"] == 1
    assert goofspiel["fixedPolicyV2Check"] == "passed"
    assert goofspiel["fixedPolicyV2RepeatActionAgreement"] == 5 / 6
