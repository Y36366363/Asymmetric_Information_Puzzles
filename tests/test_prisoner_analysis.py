import unittest

from aip.puzzles.prisoners.analysis import PrisonerTimingAnalyzer


class PrisonerTimingAnalyzerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.analyzer = PrisonerTimingAnalyzer()

    def test_two_prisoner_exact_expectations(self) -> None:
        analysis = self.analyzer.analyze(2, max_days=100)
        self.assertAlmostEqual(analysis.expected_visit_day, 3.0)
        self.assertAlmostEqual(analysis.expected_proof_day, 4.0)

    def test_two_prisoner_cdfs(self) -> None:
        visit = self.analyzer.everyone_visited_cdf(2, 2)
        proof = self.analyzer.single_counter_cdf(2, 2)
        self.assertAlmostEqual(visit[2], 0.5)
        self.assertAlmostEqual(proof[2], 0.25)

    def test_hundred_prisoner_expectations(self) -> None:
        analysis = self.analyzer.analyze(100, max_days=30_000)
        self.assertAlmostEqual(analysis.expected_visit_day, 518.7377518, places=5)
        self.assertAlmostEqual(analysis.expected_proof_day, 10_417.7377518, places=5)
        self.assertGreater(analysis.confidence_days[-1].proof_day, 10_000)

    def test_monte_carlo_is_reproducible(self) -> None:
        first = self.analyzer.monte_carlo(5, 100, seed=7)
        second = self.analyzer.monte_carlo(5, 100, seed=7)
        self.assertEqual(first, second)

    def test_custom_planning_grid(self) -> None:
        analysis = self.analyzer.analyze(
            10,
            max_days=1000,
            sample_days=(25, 50),
            confidences=(0.8, 0.99),
        )
        self.assertEqual([point.day for point in analysis.points], [25, 50])
        self.assertEqual(
            [item.confidence for item in analysis.confidence_days], [0.8, 0.99]
        )


if __name__ == "__main__":
    unittest.main()
