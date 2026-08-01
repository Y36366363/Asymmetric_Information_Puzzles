import unittest

from aip.puzzles.auctions.coordination import (
    LeadershipCandidate,
    PublicPriceCoordinationSolver,
)


class PublicPriceCoordinationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.solver = PublicPriceCoordinationSolver()
        self.candidates = (
            LeadershipCandidate(0, 101, 1),
            LeadershipCandidate(1, 105, 5),
            LeadershipCandidate(2, 130, 25),
        )

    def test_highest_bid_and_majority_leadership_can_differ(self) -> None:
        result = self.solver.solve(self.candidates, (1, 1, 5, 25, 25))
        self.assertEqual(result.raw_high_bid_leader, 2)
        self.assertEqual(result.equilibrium_price, 5)
        self.assertEqual(result.majority_recognized_leader, 1)

    def test_one_is_economically_best_for_identical_players(self) -> None:
        result = self.solver.solve(self.candidates, (1, 1, 1, 1, 1))
        self.assertEqual(result.equilibrium_price, 1)
        votes = {vote.price: vote for vote in result.votes}
        self.assertGreater(votes[1].group_surplus, votes[5].group_surplus)
        self.assertFalse(votes[25].economically_viable)

    def test_leadership_escalation_needs_private_control_value(self) -> None:
        result = self.solver.solve(
            self.candidates,
            (1, 1, 5, 25, 25),
            remaining_rounds=10,
            discount_factor=0.9,
            leadership_bonus_per_round=1,
        )
        self.assertLess(result.maximum_rational_leadership_bid, 130)
        self.assertFalse(result.raw_leader_bid_is_rational)


if __name__ == "__main__":
    unittest.main()
