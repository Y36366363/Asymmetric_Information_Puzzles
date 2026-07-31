import unittest

from aip.puzzles.worm.solver import WormSolver


class WormSolverTests(unittest.TestCase):
    def test_five_hole_shortest_strategy(self) -> None:
        solution = WormSolver().solve(5)
        self.assertEqual(solution.checks, (2, 3, 4, 2, 3, 4))
        self.assertEqual(solution.maximum_checks, 6)
        self.assertTrue(solution.steps[-1].guarantees_capture)

    def test_belief_trace_for_five_holes(self) -> None:
        solution = WormSolver().solve(5)
        self.assertEqual(
            [step.possible_after_miss_and_move for step in solution.steps],
            [(2, 3, 4, 5), (1, 3, 4, 5), (2, 4), (3, 5), (4,), ()],
        )

    def test_one_hole_is_immediate(self) -> None:
        solution = WormSolver().solve(1)
        self.assertEqual(solution.checks, (1,))


if __name__ == "__main__":
    unittest.main()
