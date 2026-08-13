import random
import unittest

from aip.puzzles.investment import InvestmentTournament, kelly_fraction


class InvestmentTests(unittest.TestCase):
    def test_fair_even_money_has_zero_kelly_stake(self) -> None:
        self.assertAlmostEqual(kelly_fraction(0.5, 1.0), 0.0)

    def test_positive_edge_has_expected_kelly_fraction(self) -> None:
        self.assertAlmostEqual(kelly_fraction(0.6, 1.0), 0.2)
        self.assertEqual(kelly_fraction(0.1, 5.0), 0.0)

    def test_tournament_eliminates_lowest_at_checkpoints(self) -> None:
        game = InvestmentTournament(random.Random(4))
        for _ in range(4):
            offer = max(game.offers, key=lambda item: item.expected_return)
            game.invest(offer.id, min(0.25, offer.kelly))
        self.assertEqual(sum(item.alive for item in game.contestants), 5)
        self.assertIsNotNone(game.history[-1]["eliminated"])

    def test_complete_seeded_tournament_is_reproducible(self) -> None:
        def run(seed: int):
            game = InvestmentTournament(random.Random(seed))
            while game.phase == "decision":
                offer = max(game.offers, key=lambda item: item.expected_return)
                game.invest(offer.id, min(0.5, offer.kelly))
            return game.winner, game.round_number, [(item.id, round(item.bankroll, 2)) for item in game.rankings]
        self.assertEqual(run(11), run(11))


if __name__ == "__main__":
    unittest.main()
