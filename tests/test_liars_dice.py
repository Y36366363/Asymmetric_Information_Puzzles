import unittest

from aip.puzzles.liars_dice.models import BidderType, DiceBid, LiarsDiceRules
from aip.puzzles.liars_dice.solver import LiarsDiceAnalyzer


class LiarsDiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.analyzer = LiarsDiceAnalyzer()

    def test_exact_probability_with_wild_ones(self) -> None:
        rules = LiarsDiceRules(player_count=2, dice_per_player=2, wild_ones=True)
        analysis = self.analyzer.analyze_bid((1, 3), DiceBid(3, 3), rules)
        self.assertEqual(analysis.own_matches, 2)
        self.assertAlmostEqual(analysis.probability_bid_true, 5 / 9)

    def test_ones_are_not_double_counted_when_wild(self) -> None:
        rules = LiarsDiceRules(player_count=2, dice_per_player=2, wild_ones=True)
        analysis = self.analyzer.analyze_bid((1, 3), DiceBid(2, 1), rules)
        self.assertEqual(analysis.own_matches, 1)
        self.assertAlmostEqual(analysis.hidden_match_probability, 1 / 6)

    def test_challenge_threshold_accounts_for_asymmetric_cost(self) -> None:
        rules = LiarsDiceRules(player_count=2, dice_per_player=1, wild_ones=False)
        analysis = self.analyzer.analyze_bid(
            (2,),
            DiceBid(2, 6),
            rules,
            correct_challenge_reward=1,
            wrong_challenge_cost=3,
        )
        self.assertEqual(analysis.challenge_threshold, 0.25)
        self.assertEqual(analysis.recommendation, "challenge")

    def test_raise_order_and_safest_raise(self) -> None:
        rules = LiarsDiceRules(player_count=2, dice_per_player=2, wild_ones=False)
        raises = self.analyzer.safest_raises((4, 4), DiceBid(1, 3), rules, limit=1)
        self.assertEqual(raises[0].bid, DiceBid(1, 4))
        self.assertEqual(raises[0].probability_true, 1.0)

    def test_incredible_bid_increases_bluffer_posterior(self) -> None:
        posterior = self.analyzer.infer_bidder_type(0.1, honest_prior=0.5)
        bluffer_probability = next(
            probability
            for hypothesis, probability in posterior.beliefs.items()
            if hypothesis.bidder_type is BidderType.BLUFFER
        )
        self.assertGreater(bluffer_probability, 0.8)

    def test_monte_carlo_tracks_exact_probability(self) -> None:
        rules = LiarsDiceRules(player_count=3, dice_per_player=2)
        check = self.analyzer.validate_probability(
            (1, 5), DiceBid(4, 5), rules, trials=20_000, seed=7
        )
        self.assertLess(check.absolute_error, 0.015)


if __name__ == "__main__":
    unittest.main()
