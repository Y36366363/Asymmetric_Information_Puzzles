import unittest
from pathlib import Path

from aip.core import (
    CFRArtifactExporter,
    CFRTrainer,
    PromotionEvidence,
    PromotionLevel,
    decide_promotion,
    run_independent_evaluation,
    strategy_profile_fingerprint,
)
from aip.core.linear_program import maximize_linear_program
from aip.puzzles.kuhn_poker import (
    KuhnCFRGame,
    KuhnIndependentEvaluator,
    audit_policy,
    build_kuhn_sequence_form,
    equilibrium_policy,
    kuhn_policy_from_cfr,
    kuhn_policy_profile,
    solve_kuhn_sequence_form,
)
from aip.puzzles.liars_dice import (
    OneDieLiarIndependentEvaluator,
    load_one_die_liar_policy,
    one_die_liar_exploitability,
)


class IndependentEquilibriumTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.evaluator = KuhnIndependentEvaluator()
        cls.sequence_solution = solve_kuhn_sequence_form()
        cls.sequence_report = run_independent_evaluation(
            cls.evaluator,
            cls.sequence_solution.policy,
            maximum_exploitability=1e-9,
        )

    def test_dependency_free_simplex_solves_a_small_lp(self) -> None:
        solution = maximize_linear_program(
            (3.0, 2.0),
            ((1.0, 1.0), (1.0, 0.0), (0.0, 1.0)),
            (4.0, 2.0, 3.0),
        )
        self.assertAlmostEqual(solution.objective, 10.0)
        self.assertEqual(tuple(round(value) for value in solution.variables), (2, 2))
        with self.assertRaisesRegex(ValueError, "infeasible"):
            maximize_linear_program((1.0,), ((1.0,), (-1.0,)), (0.0, -1.0))
        with self.assertRaisesRegex(ValueError, "unbounded"):
            maximize_linear_program((1.0,), ((-1.0,),), (-1.0,))
        with self.assertRaisesRegex(ValueError, "finite"):
            maximize_linear_program((float("nan"),), ((1.0,),), (1.0,))

    def test_kuhn_sequence_form_has_complete_flow_and_payoff_shapes(self) -> None:
        representation = build_kuhn_sequence_form()
        self.assertEqual(tuple(map(len, representation.player_sequences)), (13, 13))
        self.assertEqual(tuple(map(len, representation.flow_matrices)), (7, 7))
        self.assertEqual(len(representation.payoff_matrix), 13)
        self.assertTrue(all(len(row) == 13 for row in representation.payoff_matrix))
        self.assertAlmostEqual(self.sequence_solution.maximum_flow_residual, 0.0, delta=1e-12)
        self.assertAlmostEqual(self.sequence_solution.primal_dual_gap, 0.0, delta=1e-12)

    def test_analytic_exhaustive_and_sequence_form_agree(self) -> None:
        analytic = equilibrium_policy()
        analytic_report = run_independent_evaluation(
            self.evaluator,
            kuhn_policy_profile(analytic),
            maximum_exploitability=1e-12,
        )
        legacy_exhaustive = audit_policy(analytic)
        self.assertTrue(analytic_report.passed)
        self.assertTrue(self.sequence_report.passed)
        self.assertAlmostEqual(
            self.sequence_solution.value_to_player_0, -1 / 18, delta=1e-12
        )
        self.assertAlmostEqual(
            self.sequence_report.expected_value_to_player_0,
            analytic_report.expected_value_to_player_0,
            delta=1e-12,
        )
        self.assertAlmostEqual(
            self.sequence_report.nash_conv,
            float(legacy_exhaustive.nash_conv),
            delta=1e-12,
        )
        self.assertEqual(len(self.sequence_report.action_values), 12)

    def test_evaluator_interface_reports_value_response_and_action_values(self) -> None:
        profile = self.sequence_solution.policy
        value = self.evaluator.expected_value(profile)
        response_zero = self.evaluator.best_response(profile, 0)
        response_one = self.evaluator.best_response(profile, 1)
        self.assertAlmostEqual(value, -1 / 18, delta=1e-12)
        self.assertAlmostEqual(response_zero, value, delta=1e-12)
        self.assertAlmostEqual(response_one, -value, delta=1e-12)
        self.assertAlmostEqual(self.evaluator.nash_conv(profile), 0.0, delta=1e-12)
        self.assertAlmostEqual(self.evaluator.exploitability(profile), 0.0, delta=1e-12)
        self.assertEqual(set(self.evaluator.action_values(profile)), set(profile))
        with self.assertRaisesRegex(ValueError, "player"):
            self.evaluator.best_response(profile, 2)

    def test_undertrained_candidate_fails_independent_evaluation(self) -> None:
        result = CFRTrainer(KuhnCFRGame()).train(10)
        report = run_independent_evaluation(
            self.evaluator, result.policy, maximum_exploitability=0.01
        )
        self.assertFalse(report.passed)
        self.assertIn("exploitability_above_threshold", report.failures)
        self.assertGreater(report.exploitability, 0.01)

    def test_solver_artifact_accepts_only_a_passed_independent_report(self) -> None:
        result = CFRTrainer(KuhnCFRGame()).train(100)
        passed = run_independent_evaluation(
            self.evaluator, result.policy, maximum_exploitability=0.01
        )
        artifact = CFRArtifactExporter().build(
            result,
            game_id="canonical_kuhn_poker",
            independent_evaluation=passed,
        )
        self.assertEqual(
            artifact["independent_evaluation"]["evaluator_id"],
            "kuhn_exhaustive_best_response_v1",
        )
        failed = run_independent_evaluation(
            self.evaluator, result.policy, maximum_exploitability=0.001
        )
        with self.assertRaisesRegex(ValueError, "failed independent"):
            CFRArtifactExporter().build(
                result,
                game_id="canonical_kuhn_poker",
                independent_evaluation=failed,
            )
        with self.assertRaisesRegex(ValueError, "different strategy profile"):
            CFRArtifactExporter().build(
                result,
                game_id="canonical_kuhn_poker",
                independent_evaluation=self.sequence_report,
            )

    def test_promotion_ladder_never_skips_independent_evaluation(self) -> None:
        candidate = decide_promotion(PromotionEvidence())
        fingerprint = strategy_profile_fingerprint(self.sequence_solution.policy)
        labeled = decide_promotion(
            PromotionEvidence(
                artifact_complete=True,
                artifact_profile_fingerprint=fingerprint,
            )
        )
        checked = decide_promotion(
            PromotionEvidence(
                artifact_complete=True,
                artifact_profile_fingerprint=fingerprint,
                independent_report=self.sequence_report,
            )
        )
        verified = decide_promotion(
            PromotionEvidence(
                artifact_complete=True,
                artifact_profile_fingerprint=fingerprint,
                independent_report=self.sequence_report,
                cross_method_agreement=True,
            )
        )
        frozen = decide_promotion(
            PromotionEvidence(
                artifact_complete=True,
                artifact_profile_fingerprint=fingerprint,
                independent_report=self.sequence_report,
                cross_method_agreement=True,
                reproducible=True,
                artifact_frozen=True,
            )
        )
        self.assertEqual(
            (candidate.level, labeled.level, checked.level, verified.level, frozen.level),
            tuple(PromotionLevel),
        )
        self.assertFalse(labeled.epsilon_gto_runtime_allowed)
        self.assertTrue(checked.epsilon_gto_runtime_allowed)
        self.assertEqual(frozen.failures, ())
        mismatch = decide_promotion(
            PromotionEvidence(
                artifact_complete=True,
                artifact_profile_fingerprint="wrong-profile",
                independent_report=self.sequence_report,
            )
        )
        self.assertEqual(mismatch.level, PromotionLevel.LABELED)
        self.assertFalse(mismatch.epsilon_gto_runtime_allowed)
        self.assertIn("independent_report_profile_mismatch", mismatch.failures)

    def test_one_die_liar_uses_the_same_independent_report(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "src/aip/puzzles/liars_dice/one_die_cfr_policy.json"
        )
        result = load_one_die_liar_policy(source)
        self.assertEqual(result.algorithm.algorithm_id, "root_chance_sampling_cfr")
        self.assertEqual(result.algorithm.seed, 20260908)
        report = run_independent_evaluation(
            OneDieLiarIndependentEvaluator(),
            result.policy,
            maximum_exploitability=0.01,
        )
        self.assertTrue(report.passed, report.failures)
        self.assertAlmostEqual(report.exploitability, one_die_liar_exploitability(result))
        self.assertEqual(len(report.action_values), 348)
        promotion = decide_promotion(
            PromotionEvidence(
                artifact_complete=True,
                artifact_profile_fingerprint=strategy_profile_fingerprint(
                    result.policy
                ),
                independent_report=report,
            )
        )
        self.assertEqual(promotion.level, PromotionLevel.INDEPENDENTLY_CHECKED)
        self.assertTrue(promotion.epsilon_gto_runtime_allowed)


if __name__ == "__main__":
    unittest.main()
