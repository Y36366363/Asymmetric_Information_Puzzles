import unittest

from aip.puzzles.pirates.models import PirateRules, VoteThreshold
from aip.puzzles.pirates.solver import PirateSolver


class PirateSolverTests(unittest.TestCase):
    def test_classic_five_pirates_one_hundred_gold(self) -> None:
        solution = PirateSolver().solve(5, 100)
        final = solution.final_round
        self.assertTrue(final.passed)
        self.assertEqual(final.allocation, (98, 0, 1, 0, 1))
        self.assertEqual(final.yes_votes, 3)

    def test_strict_majority_changes_two_pirate_outcome(self) -> None:
        rules = PirateRules(threshold=VoteThreshold.STRICT_MAJORITY)
        final = PirateSolver(rules).solve(2, 100).final_round
        self.assertFalse(final.passed)
        self.assertEqual(final.allocation, (0, 100))

    def test_too_little_gold_can_kill_proposer(self) -> None:
        final = PirateSolver().solve(6, 0).final_round
        self.assertFalse(final.passed)
        self.assertFalse(final.alive[0])

    def test_invalid_inputs(self) -> None:
        for pirates, gold in ((0, 10), (2, -1)):
            with self.subTest(pirates=pirates, gold=gold):
                with self.assertRaises(ValueError):
                    PirateSolver().solve(pirates, gold)


if __name__ == "__main__":
    unittest.main()
