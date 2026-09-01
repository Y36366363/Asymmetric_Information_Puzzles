import unittest

from aip.benchmark import (
    EvidenceLevel,
    V1_ABLATIONS,
    default_protocol,
    environment_spec,
    metric_eligibility,
    run_repeated_guess_who_pilot,
)


class BenchmarkProtocolTests(unittest.TestCase):
    def test_metric_names_follow_reference_strength(self) -> None:
        exact = metric_eligibility(environment_spec("guess-who"))
        equilibrium = metric_eligibility(environment_spec("kuhn-poker"))
        heuristic = metric_eligibility(environment_spec("mastermind"))
        self.assertTrue(exact.regret)
        self.assertFalse(exact.exploitability)
        self.assertEqual(exact.policy_agreement, "exact_optimal_policy_agreement")
        self.assertTrue(equilibrium.exploitability)
        self.assertEqual(
            equilibrium.policy_agreement,
            "equilibrium_support_or_distribution_agreement",
        )
        self.assertFalse(heuristic.regret)
        self.assertFalse(heuristic.exploitability)
        self.assertEqual(
            heuristic.policy_agreement, "heuristic_reference_agreement"
        )

    def test_ablation_matrix_is_full_factorial_and_marks_supervised_ceiling(self) -> None:
        self.assertEqual(len(V1_ABLATIONS), 8)
        axes = {
            (item.game_specific_prompt, item.memory, item.cross_game_experience)
            for item in V1_ABLATIONS
        }
        self.assertEqual(len(axes), 8)
        self.assertTrue(
            all(
                item.eligible_for_primary_transfer_comparison
                == (not item.game_specific_prompt)
                for item in V1_ABLATIONS
            )
        )

    def test_protocol_expands_every_axis_without_holdout_leakage(self) -> None:
        protocol = default_protocol(("model-a", "model-b"))
        trials = protocol.trials()
        expected = 3 * 2 * 6 * 8 * 4 * 4
        self.assertEqual(len(trials), expected)
        self.assertEqual(protocol.held_out_environment_id, "mastermind")
        self.assertNotIn("mastermind", protocol.training_environment_ids)
        held_out = [trial for trial in trials if trial.held_out]
        self.assertTrue(held_out)
        self.assertTrue(
            all(
                trial.eligible_for_primary_transfer_comparison
                == trial.condition_id.startswith("prompt-generic")
                for trial in held_out
            )
        )
        payload = protocol.as_dict()
        self.assertEqual(payload["trialCount"], expected)
        self.assertEqual(
            payload["metricEligibility"]["mastermind"]["evidenceLevel"],
            EvidenceLevel.STRONG_HEURISTIC.value,
        )

    def test_repeated_pilot_uses_disjoint_seeds_and_reports_missing_belief(self) -> None:
        report = run_repeated_guess_who_pilot(
            repeats=3, seeds_per_repeat=3, base_seed=50
        )
        self.assertEqual(
            report["seedBlocks"],
            [[50, 51, 52], [53, 54, 55], [56, 57, 58]],
        )
        self.assertEqual(
            report["notEvidenceFor"],
            ["held_out_transfer", "multi_model_comparison"],
        )
        self.assertIsNone(report["aggregate"]["genericWeakBeliefBrier"])
        self.assertGreater(report["aggregate"]["policyAgreementGainMean"], 0)
        self.assertGreater(report["aggregate"]["regretReductionMean"], 0)
        for replicate in report["replicates"]:
            self.assertEqual(replicate["oracle"]["mean_action_regret"], 0.0)
            self.assertEqual(
                replicate["singleGamePromptedProxy"]["belief_output_rate"], 1.0
            )

    def test_repeated_pilot_is_reproducible(self) -> None:
        first = run_repeated_guess_who_pilot(
            repeats=2, seeds_per_repeat=2, base_seed=7
        )
        second = run_repeated_guess_who_pilot(
            repeats=2, seeds_per_repeat=2, base_seed=7
        )
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
