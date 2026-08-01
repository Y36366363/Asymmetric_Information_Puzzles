import unittest

from aip.puzzles.auctions.models import AuctionMode, AuctionRules
from aip.puzzles.auctions.solver import AllPayAuctionAnalyzer, AllPayAuctionSimulator


class AllPayAuctionTests(unittest.TestCase):
    def test_symmetric_benchmark(self) -> None:
        result = AllPayAuctionAnalyzer.symmetric_benchmark(5, 100)
        self.assertAlmostEqual(result.expected_bid_per_player, 20)
        self.assertAlmostEqual(result.expected_total_bids, 100)
        self.assertAlmostEqual(result.expected_winning_bid, 500 / 9)
        self.assertEqual(result.expected_payoff_per_player, 0)

    def test_budget_and_wealth_accounting(self) -> None:
        rules = AuctionRules(player_count=4, rounds=8, prize_value=100, initial_budget=80)
        run = AllPayAuctionSimulator().run(rules, AuctionMode.NAIVE, seed=3)
        self.assertTrue(all(budget >= 0 for budget in run.final_budgets))
        prizes_awarded = sum(round_.winner is not None for round_ in run.rounds)
        self.assertEqual(
            sum(run.final_budgets) + run.auctioneer_revenue,
            rules.player_count * rules.initial_budget + prizes_awarded * rules.prize_value,
        )

    def test_cooperation_maximizes_group_surplus_in_simple_rotation(self) -> None:
        rules = AuctionRules(player_count=5, rounds=5, prize_value=100, initial_budget=10)
        run = AllPayAuctionSimulator().run(rules, AuctionMode.COOPERATIVE, seed=1)
        self.assertEqual(run.auctioneer_revenue, 5)
        self.assertEqual(run.final_budgets, (109, 109, 109, 109, 109))

    def test_analysis_is_reproducible(self) -> None:
        rules = AuctionRules(player_count=3, rounds=4, initial_budget=50)
        analyzer = AllPayAuctionAnalyzer()
        first = analyzer.analyze(rules, trials=20, seed=9)
        second = analyzer.analyze(rules, trials=20, seed=9)
        self.assertEqual(first.scenarios, second.scenarios)

    def test_price_only_tacit_norm_survives_without_deviation(self) -> None:
        rules = AuctionRules(player_count=4, rounds=6, tacit_deviation_probability=0)
        run = AllPayAuctionSimulator().run(rules, AuctionMode.TACIT, seed=2)
        self.assertIsNone(run.coordination_break_round)
        self.assertTrue(all(round_.public_price == 1 for round_ in run.rounds))
        self.assertTrue(all(round_.coordination_active_after for round_ in run.rounds))

    def test_public_price_detects_deviation_but_not_identity(self) -> None:
        rules = AuctionRules(player_count=4, rounds=3, tacit_deviation_probability=1)
        run = AllPayAuctionSimulator().run(rules, AuctionMode.TACIT, seed=2)
        self.assertEqual(run.coordination_break_round, 1)
        self.assertEqual(run.rounds[0].public_price, 2)
        self.assertFalse(run.rounds[0].coordination_active_after)
        self.assertTrue(run.rounds[0].coordination_active_before)

    def test_tacit_patience_threshold_is_high(self) -> None:
        threshold = AllPayAuctionAnalyzer.tacit_patience_threshold(5, 100)
        self.assertGreater(threshold, 0.8)
        self.assertLess(threshold, 1.0)


if __name__ == "__main__":
    unittest.main()
