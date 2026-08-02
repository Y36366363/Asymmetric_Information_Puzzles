import unittest

from aip.puzzles.cases.models import BankerProfile, CaseGameRules, RiskPreferences
from aip.puzzles.cases.solver import CaseGameAnalyzer


class CaseGameTests(unittest.TestCase):
    def setUp(self) -> None:
        self.analyzer = CaseGameAnalyzer()

    def test_risk_neutral_certainty_equivalent_is_mean(self) -> None:
        analysis = self.analyzer.analyze_offer((1.0, 10.0, 100.0), 30.0)
        self.assertEqual(analysis.expected_value, 37.0)
        self.assertEqual(analysis.certainty_equivalent, 37.0)
        self.assertEqual(analysis.reservation_recommendation, "no-deal")

    def test_risk_aversion_lowers_reservation_value(self) -> None:
        analysis = self.analyzer.analyze_offer(
            (0.0, 100.0), 40.0, RiskPreferences(risk_tolerance=30.0)
        )
        self.assertLess(analysis.certainty_equivalent, analysis.expected_value)
        self.assertEqual(analysis.reservation_recommendation, "deal")

    def test_next_offer_expectation_preserves_mean_times_multiplier(self) -> None:
        projection = self.analyzer.project_next_offer((1.0, 2.0, 9.0), 1, 0.8, 3.0)
        self.assertEqual(projection.outcomes, 3)
        self.assertAlmostEqual(projection.expected_offer, 3.2)
        self.assertAlmostEqual(projection.minimum_offer, 1.2)
        self.assertAlmostEqual(projection.maximum_offer, 4.4)

    def test_high_offer_shifts_posterior_to_generous_banker(self) -> None:
        stingy = BankerProfile("stingy", (0.4,))
        generous = BankerProfile("generous", (0.9,))
        prior = self.analyzer.banker_information_set((stingy, generous))
        posterior = self.analyzer.update_banker_beliefs(
            prior, 85.0, (50.0, 100.0, 150.0), 0
        )
        generous_probability = next(
            probability
            for hypothesis, probability in posterior.beliefs.items()
            if hypothesis.profile.name == "generous"
        )
        self.assertGreater(generous_probability, 0.99)

    def test_simulation_is_reproducible_and_accounts_for_payout(self) -> None:
        rules = CaseGameRules((1.0, 10.0, 100.0), (1, 1))
        banker = BankerProfile("test", (0.5, 1.0))
        first = self.analyzer.play(rules, banker, seed=7)
        second = self.analyzer.play(rules, banker, seed=7)
        self.assertEqual(first, second)
        self.assertGreaterEqual(first.payout, 0)


if __name__ == "__main__":
    unittest.main()
