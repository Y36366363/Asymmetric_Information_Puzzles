import unittest

from aip.puzzles.hats.solver import HatSolver


class HatSolverTests(unittest.TestCase):
    def test_three_target_hats_are_known_on_round_three(self) -> None:
        solution = HatSolver().solve("BBBRR", "B", "R")
        self.assertEqual(solution.discovery_round, 3)
        self.assertEqual(solution.rounds[-1].knowers, (0, 1, 2))
        self.assertEqual(
            [round_.possible_world_count for round_ in solution.rounds],
            [31, 26, 16],
        )

    def test_one_target_hat_is_known_immediately(self) -> None:
        solution = HatSolver().solve("BRRR", "B", "R")
        self.assertEqual(solution.discovery_round, 1)
        self.assertEqual(solution.rounds[0].knowers, (0,))

    def test_public_announcement_must_be_true(self) -> None:
        with self.assertRaises(ValueError):
            HatSolver().solve("RR", "B", "R")


if __name__ == "__main__":
    unittest.main()
