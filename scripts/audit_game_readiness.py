#!/usr/bin/env python3
"""Recompute evidence-backed completion status for the main exact-game targets."""

from __future__ import annotations

import json
from pathlib import Path

from aip.benchmark import evaluate_goofspiel_policy, evaluate_kuhn_policy
from aip.core import (
    CFRGameProperties,
    compile_sequence_form,
    run_independent_evaluation,
    solve_sequence_form,
)
from aip.core.tree_evaluation import FullTreeBestResponseEvaluator
from aip.puzzles.e_card import (
    DUELS,
    e_card_exploitability,
    solve_e_card_timing_game,
)
from aip.puzzles.kuhn_poker import equilibrium_policy
from aip.puzzles.liars_dice import (
    OneDieLiarIndependentEvaluator,
    solve_one_die_liar_exact,
)
from aip.puzzles.love_letter import LoveLetterCFRGame, LoveLetterIndependentEvaluator
from aip.puzzles.guess_who import (
    DEFAULT_QUESTIONS,
    DEFAULT_ROSTER,
    StrategicGuessWhoGame,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "research/results/game_readiness_2026-09-26.json"
LOVE_PROGRESS = ROOT / "research/results/love_letter_local_progress_2026-09-17.json"
LIAR_STRUCTURED_ORIGINAL = (
    ROOT / "research/results/liar_structured_manipulation_2026-09-27/report.json"
)
LIAR_FIXED_POLICY_V1 = (
    ROOT / "research/results/liar_fixed_policy_value_check_2026-09-28/report.json"
)
LIAR_FIXED_POLICY_V2 = (
    ROOT / "research/results/liar_fixed_policy_value_check_v2_2026-09-28/report.json"
)
GOOFSPIEL_FIXED_POLICY_V2 = (
    ROOT / "research/results/goofspiel_fixed_policy_value_check_v2_2026-09-28/report.json"
)
GUESS_SIGNALING = ROOT / "research/results/guess_who_signaling_2026-10-03.json"
GUESS_PRIVATE_COST_SIGNALING = (
    ROOT / "research/results/guess_who_private_cost_signaling_2026-10-04.json"
)
GUESS_PRIVATE_COST_DOSE_RESPONSE = (
    ROOT / "research/results/guess_who_private_cost_dose_response_2026-10-05.json"
)
LOVE_FIXED_POLICY_CONDITIONING = (
    ROOT / "research/results/love_letter_fixed_policy_conditioning_2026-10-06.json"
)
LOVE_COLLAPSED_POSTERIOR = (
    ROOT / "research/results/love_letter_collapsed_posterior_2026-10-07.json"
)
FIVE_DIE_LIAR_FEASIBILITY = (
    ROOT / "research/results/five_die_liar_feasibility_2026-10-07.json"
)
FIVE_DIE_STEPWISE_PROGRESS = (
    ROOT / "research/results/five_die_stepwise_progress_2026-10-08.json"
)
FIVE_DIE_STEPWISE_CANDIDATE = (
    ROOT / "research/results/five_die_stepwise_candidate_2026-10-08.json"
)
FIVE_DIE_STEPWISE_COVERAGE = (
    ROOT / "research/results/five_die_stepwise_coverage_2026-10-09.json"
)
FIVE_DIE_STEPWISE_JOINT_STRATIFICATION = (
    ROOT
    / "research/results/five_die_stepwise_joint_stratification_2026-10-10.json"
)


def report() -> dict[str, object]:
    _, liar_solution = solve_one_die_liar_exact()
    liar_report = run_independent_evaluation(
        OneDieLiarIndependentEvaluator(),
        liar_solution.policy,
        maximum_exploitability=1e-10,
    )
    goof = evaluate_goofspiel_policy("equilibrium")
    kuhn = evaluate_kuhn_policy(equilibrium_policy())
    e_card = solve_e_card_timing_game()
    e_card_profile = dict(zip(DUELS, map(float, e_card.emperor_strategy)))

    guess_game = StrategicGuessWhoGame(
        (DEFAULT_ROSTER[0], DEFAULT_ROSTER[6], DEFAULT_ROSTER[12]),
        DEFAULT_QUESTIONS[:3],
    )
    guess_form = compile_sequence_form(
        guess_game,
        game_properties=CFRGameProperties(2, True, True, True),
        sparse=True,
    )
    guess_solution = solve_sequence_form(guess_form, backend="scipy_highs")
    guess_report = run_independent_evaluation(
        FullTreeBestResponseEvaluator(
            guess_game, evaluator_id="strategic_guess_who_v1"
        ),
        guess_solution.policy,
        maximum_exploitability=1e-10,
    )

    love_game = LoveLetterCFRGame.late_round_subgame()
    love_solution = solve_sequence_form(
        compile_sequence_form(
            love_game,
            game_properties=CFRGameProperties(2, True, True, True),
            sparse=True,
        ),
        backend="scipy_highs",
    )
    love_evaluator = LoveLetterIndependentEvaluator(love_game)
    love_report = run_independent_evaluation(
        love_evaluator,
        love_solution.policy,
        maximum_exploitability=1e-12,
    )
    progress = json.loads(LOVE_PROGRESS.read_text(encoding="utf-8"))
    latest = progress["chunks"][-1]
    def load_optional(path: Path):
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    structured_original = load_optional(LIAR_STRUCTURED_ORIGINAL)
    fixed_v1 = load_optional(LIAR_FIXED_POLICY_V1)
    fixed_v2 = load_optional(LIAR_FIXED_POLICY_V2)
    goof_fixed_v2 = load_optional(GOOFSPIEL_FIXED_POLICY_V2)
    guess_signaling = load_optional(GUESS_SIGNALING)
    guess_private_cost = load_optional(GUESS_PRIVATE_COST_SIGNALING)
    guess_private_cost_dose_response = load_optional(
        GUESS_PRIVATE_COST_DOSE_RESPONSE
    )
    love_fixed_policy = load_optional(LOVE_FIXED_POLICY_CONDITIONING)
    love_collapsed_posterior = load_optional(LOVE_COLLAPSED_POSTERIOR)
    five_die_feasibility = load_optional(FIVE_DIE_LIAR_FEASIBILITY)
    five_die_progress = load_optional(FIVE_DIE_STEPWISE_PROGRESS)
    five_die_candidate = load_optional(FIVE_DIE_STEPWISE_CANDIDATE)
    five_die_coverage = load_optional(FIVE_DIE_STEPWISE_COVERAGE)
    five_die_joint = load_optional(FIVE_DIE_STEPWISE_JOINT_STRATIFICATION)
    latest_five_die_candidate = (
        five_die_joint["checkpoints"][-1]
        if five_die_joint is not None
        else five_die_coverage["checkpoints"][-1]
        if five_die_coverage is not None
        else None
    )

    games = {
        "one-die-stepwise-liars-dice": {
            "status": "complete_declared_variant",
            "solver": "exact_sequence_form_plus_certified_runtime_cfr",
            "independentEvaluator": True,
            "exploitability": liar_report.exploitability,
            "runtimeEpsilonGtoAllowed": True,
            "valueDecomposition": "complete_30_state_panel",
            "originalAmbiguousPosteriorCheck": (
                "not_run" if structured_original is None
                else "passed" if structured_original["gatePassed"]
                else "failed_retained"
            ),
            "fixedPolicyV1Check": (
                "not_run" if fixed_v1 is None
                else "passed" if fixed_v1["gatePassed"] else "failed_retained"
            ),
            "fixedPolicyV2Check": (
                "not_run" if fixed_v2 is None
                else "passed" if fixed_v2["gatePassed"] else "failed_retained"
            ),
            "fixedPolicyV2RepeatActionAgreement": (
                None if fixed_v2 is None
                else fixed_v2["summary"]["repeatActionAgreement"]
            ),
            "remainingWork": [
                "retain supplied-policy scope; do not relabel it as equilibrium discovery",
                "new certificate required for any expanded bidding rules",
            ],
        },
        "five-die-liars-dice": {
            "status": "heuristic_only_not_gto",
            "solver": "transparent_probability_heuristic",
            "independentEvaluator": False,
            "runtimeEpsilonGtoAllowed": False,
            "valueDecomposition": "not_applicable_to_current_heuristic_rules",
            "stepwiseCandidateStatus": (
                "not_audited"
                if (
                    five_die_candidate is None
                    and five_die_coverage is None
                    and five_die_joint is None
                )
                else (
                    "joint_stratification_candidate_failed_preregistered_gates"
                    if five_die_joint is not None
                    else "coverage_improved_candidate_failed_independent_gate"
                    if five_die_coverage is not None
                    else "adapter_implemented_candidate_failed_independent_gate"
                )
            ),
            "stepwiseCandidateRulesId": (
                None
                if five_die_feasibility is None
                else five_die_feasibility["rules_id"]
            ),
            "stepwiseCandidateEstimatedHistories": (
                None
                if five_die_feasibility is None
                else five_die_feasibility["stepwise_candidate"]
                ["estimated_complete_histories_with_two_layer_histogram_chance"]
            ),
            "liveArbitraryRaisePublicHistories": (
                None
                if five_die_feasibility is None
                else five_die_feasibility["live_arbitrary_raise_mode"]
                ["nonempty_public_bid_histories"]
            ),
            "stepwiseHistoriesAudited": (
                None
                if five_die_progress is None
                else five_die_progress["chunks"][-1]["histories"]
            ),
            "stepwiseInformationSetsObserved": (
                None
                if five_die_progress is None
                else five_die_progress["chunks"][-1]["information_sets"]
            ),
            "stepwiseStructuralFailures": (
                None
                if five_die_progress is None
                else five_die_progress["chunks"][-1]["failures"]
            ),
            "stepwiseStructuralAuditComplete": (
                False
                if five_die_progress is None
                else five_die_progress["chunks"][-1]["complete"]
            ),
            "stepwiseCandidateExploitability": (
                None
                if latest_five_die_candidate is None and five_die_candidate is None
                else latest_five_die_candidate["independent_evaluation"]
                ["exploitability"]
                if latest_five_die_candidate is not None
                else five_die_candidate["independent_evaluation"]["exploitability"]
            ),
            "stepwiseCandidateSampledCoverage": (
                None
                if latest_five_die_candidate is None and five_die_candidate is None
                else latest_five_die_candidate["visited_coverage"]
                if latest_five_die_candidate is not None
                else five_die_candidate["sampled_coverage"]
            ),
            "stepwiseRetainedBaselineExploitability": (
                None
                if five_die_joint is None
                else five_die_joint["retained_experiments"][-1]
                ["independent_exploitability"]
            ),
            "stepwiseCoverageGatePassed": (
                False
                if five_die_joint is None
                else five_die_joint["gates"]["visited_coverage_passed"]
            ),
            "stepwiseIndependentGatePassed": (
                False
                if five_die_joint is None
                else five_die_joint["gates"]
                ["independent_exploitability_passed"]
            ),
            "stepwiseCandidateIterations": (
                None
                if latest_five_die_candidate is None
                else latest_five_die_candidate["iterations"]
            ),
            "stepwiseJointChanceMarginalsExact": (
                False
                if five_die_joint is None
                else five_die_joint["schedule_audit"]["exact_true_marginals"]
            ),
            "remainingWork": [
                "continue the resumable stepwise structural audit",
                "retain all three failed candidates; do not post-hoc increase the joint-stratification budget",
                "audit and separately preregister any average-policy estimator change on small controls before another five-die run",
                "retain complete histogram-state best response as the promotion gate",
            ],
        },
        "goofspiel-four-card": {
            "status": "complete_exact_solver_and_benchmark",
            "solver": "exact_backward_induction_zero_sum_matrices",
            "independentEvaluator": True,
            "exploitability": float(goof.exploitability),
            "runtimeExactEquilibriumMode": True,
            "valueDecomposition": "complete_30_state_panel",
            "fixedPolicyV2Check": (
                "not_run" if goof_fixed_v2 is None
                else "passed" if goof_fixed_v2["gatePassed"]
                else "failed_retained"
            ),
            "fixedPolicyV2RepeatActionAgreement": (
                None if goof_fixed_v2 is None
                else goof_fixed_v2["summary"]["repeatActionAgreement"]
            ),
            "remainingWork": [
                "retain exact-tie-aware interpretation of repeat action differences"
            ],
        },
        "kuhn-poker": {
            "status": "complete_exact_reference",
            "solver": "analytic_plus_sequence_form_plus_best_response",
            "independentEvaluator": True,
            "maximumUnilateralDeviationGain": float(
                kuhn.maximum_unilateral_deviation_gain
            ),
            "remainingWork": ["optional second adversarial model target"],
        },
        "e-card-single-round": {
            "status": "complete_solver_control",
            "solver": "exact_timing_matrix",
            "exploitability": e_card_exploitability(
                e_card_profile,
                dict(zip(DUELS, map(float, e_card.slave_strategy))),
            ),
            "runtimeScope": "multi-round adaptation remains strong heuristic",
            "remainingWork": ["retain as exact solver control, not primary agent task"],
        },
        "guess-who-strategic-three-character": {
            "status": "complete_certified_research_subgame",
            "solver": "sparse_sequence_form_scipy_highs_plus_full_tree_best_response",
            "independentEvaluator": True,
            "histories": guess_form.audit.histories,
            "informationSets": guess_form.audit.information_sets,
            "expectedValueToPlayer0": guess_report.expected_value_to_player_0,
            "exploitability": guess_report.exploitability,
            "explicitGuessAction": True,
            "incorrectGuessPenalty": "immediate_loss",
            "frozenRulesId": StrategicGuessWhoGame.RULES_ID,
            "signalingExperimentStatus": (
                "not_run" if guess_signaling is None
                else "valid_zero_result_with_cfr_crosscheck_failure_retained"
            ),
            "maximumRootPolicyL1ByPrivateSecret": (
                None if guess_signaling is None
                else guess_signaling["primary_endpoint"]["value"]
            ),
            "privateCostExperimentStatus": (
                "not_run" if guess_private_cost is None
                else "valid_zero_result_all_preregistered_crosschecks_passed"
            ),
            "privateCostMaximumRootPolicyL1": (
                None if guess_private_cost is None
                else guess_private_cost["primary_endpoint"]["value"]
            ),
            "privateCostRulesId": (
                None if guess_private_cost is None
                else guess_private_cost["frozen_rules"]["rules_id"]
            ),
            "privateCostDoseResponseStatus": (
                "not_run"
                if guess_private_cost_dose_response is None
                else "valid_zero_result_none_in_preregistered_grid"
            ),
            "privateCostDoseResponseFirstPositiveUnitCost": (
                None
                if guess_private_cost_dose_response is None
                else guess_private_cost_dose_response["primary_endpoint"]
                ["smallest_preregistered_unit_cost_with_positive_signal"]
            ),
            "privateCostDoseResponseMaximumSingleCost": (
                None
                if guess_private_cost_dose_response is None
                else max(
                    level["maximum_single_question_cost"]
                    for level in guess_private_cost_dose_response["dose_response"]
                )
            ),
            "runtimeEpsilonGtoAllowed": False,
            "remainingWork": [
                "retain the fixed-grid private-cost zero result and pause this cost-shape signaling branch",
                "use a new rules ID and separate preregistration for any structurally different signaling mechanism",
                "do not generalize certificate to the 24-character game",
            ],
        },
        "love-letter-four-card-subgame": {
            "status": "complete_certified_research_subgame",
            "solver": "sparse_sequence_form_scipy_highs",
            "independentEvaluator": True,
            "histories": love_evaluator.audit.histories,
            "informationSets": len(love_report.action_values),
            "expectedValueToPlayer0": love_report.expected_value_to_player_0,
            "exploitability": love_report.exploitability,
            "runtimeFullRoundAllowed": False,
            "valueDecomposition": "17_positive_reach_43_zero_reach_information_sets",
            "combinatorialPrior": {
                "status": "implemented_and_independently_audited",
                "methodId": "love_letter_chance_reach_combinatorial_prior_v1",
                "positiveReachInformationSets": 17,
                "zeroReachInformationSets": 43,
                "usesUniformActionBaseline": False,
                "policyConditioningShiftOnPositiveReachPanel": False,
            },
            "structuredExperimentStatus": (
                "not_run"
                if love_collapsed_posterior is None
                else "retired_as_belief_update_target_no_identifiable_post_action_hidden_state"
            ),
            "fixedPolicyPositiveReachInformationSets": (
                None
                if love_fixed_policy is None
                else love_fixed_policy["fixed_policy_panel"]
                ["positive_reach_information_sets"]
            ),
            "fixedPolicyMaximumPosteriorL1Shift": (
                None
                if love_fixed_policy is None
                else love_fixed_policy["primary_result"]
                ["maximum_posterior_l1_shift"]
            ),
            "fixedPolicyExploitability": (
                None
                if love_fixed_policy is None
                else love_fixed_policy["fixed_policy"]
                ["independent_evaluation"]["exploitability"]
            ),
            "collapsedPosteriorSupportSizeCounts": (
                None
                if love_collapsed_posterior is None
                else love_collapsed_posterior["panel"]["support_size_counts"]
            ),
            "postActionNontrivialHiddenStateInformationSets": (
                None
                if love_collapsed_posterior is None
                else love_collapsed_posterior["panel"]
                ["information_sets_with_nontrivial_support_after_observed_opponent_action"]
            ),
            "remainingWork": [
                "retain the current-hand fixed-policy zero result",
                "retain the collapsed-target stopping result and use this subgame only as an exact value-decomposition control",
                "do not generalize certificate to full round",
            ],
        },
        "love-letter-full-round": {
            "status": "blocked_on_complete_structural_enumeration",
            "solver": "none_complete",
            "independentEvaluator": False,
            "historiesTraversed": latest["histories"],
            "informationSetsObserved": latest["information_sets"],
            "frontierNodes": latest["frontier_nodes"],
            "maximumDepth": latest["maximum_depth"],
            "structuralFailures": latest["failures"],
            "structuralAuditComplete": latest["complete"],
            "runtimeEpsilonGtoAllowed": False,
            "remainingWork": [
                "close resumable structural audit",
                "compile and solve complete candidate",
                "run complete independent best response",
                "bind profile fingerprint to promotion evidence",
            ],
        },
    }
    return {
        "schemaVersion": "aip-game-readiness-v1",
        "date": "2026-10-10",
        "games": games,
        "conclusion": {
            "basicConstructionComplete": [
                "one-die-stepwise-liars-dice",
                "goofspiel-four-card",
                "kuhn-poker",
                "e-card-single-round",
                "guess-who-strategic-three-character",
                "love-letter-four-card-subgame",
            ],
            "notComplete": ["five-die-liars-dice", "love-letter-full-round"],
            "nextPriority": (
                "retain the preregistered Guess Who dose-response zero result and pause "
                "that cost-shape branch; retain the five-die joint-stratification failures, "
                "audit any average-policy estimator on small controls before preregistration, and continue "
                "its structural audit; continue bounded full-round Love Letter audit"
            ),
        },
    }


def main() -> int:
    value = report()
    OUTPUT.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(value["conclusion"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
