import unittest

from aip.core import CFRThresholds, CFRTrainer
from aip.puzzles.kuhn_poker import (
    KuhnCFRGame,
    audit_policy,
    certify_kuhn_cfr,
    game_value,
    kuhn_policy_from_cfr,
    policy_value,
)


class ReverseChanceKuhn(KuhnCFRGame):
    def chance_outcomes(self, state):
        return tuple(reversed(super().chance_outcomes(state)))


class ReverseActionKuhn(KuhnCFRGame):
    def legal_actions(self, state):
        return tuple(reversed(super().legal_actions(state)))


def canonical_policy(result):
    return {
        key: dict(sorted(distribution.items()))
        for key, distribution in result.policy.items()
    }


class BatchedFullTreeCFRTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.forward = CFRTrainer(KuhnCFRGame()).train(10_000)
        cls.reverse_chance = CFRTrainer(ReverseChanceKuhn()).train(10_000)
        cls.reverse_actions = CFRTrainer(ReverseActionKuhn()).train(10_000)
        cls.policy = kuhn_policy_from_cfr(cls.forward)

    def test_chance_outcome_order_is_exactly_invariant(self) -> None:
        self.assertEqual(
            canonical_policy(self.forward), canonical_policy(self.reverse_chance)
        )

    def test_action_enumeration_order_is_exactly_invariant_after_normalization(self) -> None:
        self.assertEqual(
            canonical_policy(self.forward), canonical_policy(self.reverse_actions)
        )

    def test_known_kuhn_value_and_cross_project_metrics(self) -> None:
        value = float(policy_value(self.policy, self.policy, hero_first=True))
        audit = audit_policy(self.policy)
        self.assertAlmostEqual(value, float(game_value(True)), delta=0.0001)
        self.assertAlmostEqual(value, -0.055563518262057715, places=12)
        self.assertAlmostEqual(
            float(audit.nash_conv), 0.00022664891572794083, delta=1e-9
        )
        self.assertAlmostEqual(
            float(audit.exploitability), 0.00011332445786397041, delta=1e-9
        )
        self.assertEqual(self.forward.information_set_count, 12)

    def test_independent_best_response_gate_passes_without_relaxation(self) -> None:
        report = certify_kuhn_cfr(
            self.forward,
            CFRThresholds(
                min_iterations=10_000,
                min_information_sets=12,
                min_visits_per_information_set=10_000,
                max_average_positive_regret=0.01,
                max_exploitability=0.01,
            ),
        )
        self.assertTrue(report.passed, report.failures)
        self.assertLess(report.exploitability, 0.01)
        self.assertEqual(
            set(report.evaluation.to_report()),
            {
                "nash_conv",
                "exploitability",
                "player_0_deviation_gain",
                "player_1_deviation_gain",
                "maximum_unilateral_deviation_gain",
            },
        )
        self.assertNotEqual(
            report.exploitability, report.maximum_unilateral_deviation_gain
        )

    def test_undertrained_negative_control_still_fails(self) -> None:
        report = certify_kuhn_cfr(CFRTrainer(KuhnCFRGame()).train(100))
        self.assertFalse(report.passed)
        self.assertIn("insufficient_iterations", report.failures)
        self.assertTrue(
            {
                "average_positive_regret_above_threshold",
                "exploitability_above_threshold",
            }
            & set(report.failures)
        )

    def test_policy_distributions_are_normalized(self) -> None:
        for distribution in self.forward.policy.values():
            self.assertTrue(all(probability >= 0 for probability in distribution.values()))
            self.assertAlmostEqual(sum(distribution.values()), 1.0, places=15)

    def test_information_set_action_inconsistency_is_rejected(self) -> None:
        class InconsistentActions(KuhnCFRGame):
            def legal_actions(self, state):
                actions = super().legal_actions(state)
                if state.cards == ("K", "J"):
                    return tuple(reversed(actions))
                return actions

        with self.assertRaisesRegex(ValueError, "inconsistent legal actions"):
            CFRTrainer(InconsistentActions()).train(1)

    def test_invalid_chance_probability_is_rejected(self) -> None:
        class InvalidChance(KuhnCFRGame):
            def chance_outcomes(self, state):
                outcomes = super().chance_outcomes(state)
                return tuple((action, probability * 0.9) for action, probability in outcomes)

        with self.assertRaisesRegex(ValueError, "sum to one"):
            CFRTrainer(InvalidChance()).train(1)


if __name__ == "__main__":
    unittest.main()
