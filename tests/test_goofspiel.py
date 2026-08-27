import unittest
from fractions import Fraction

from aip.puzzles.goofspiel import GoofspielSolver
from aip.puzzles.goofspiel.solver import solve_zero_sum_matrix


class GoofspielTests(unittest.TestCase):
    def test_matrix_solver_finds_matching_pennies_equilibrium(self) -> None:
        solution = solve_zero_sum_matrix(
            ((Fraction(1), Fraction(-1)), (Fraction(-1), Fraction(1)))
        )
        self.assertEqual(solution.value, 0)
        self.assertEqual(solution.row_strategy, (Fraction(1, 2), Fraction(1, 2)))
        self.assertEqual(solution.column_strategy, (Fraction(1, 2), Fraction(1, 2)))

    def test_initial_four_card_game_has_zero_value(self) -> None:
        solver = GoofspielSolver(4)
        self.assertEqual(solver.state_value(solver.cards, solver.cards, solver.cards), 0)

    def test_every_equilibrium_distribution_is_normalized(self) -> None:
        solver = GoofspielSolver(4)
        for prize in solver.cards:
            solution = solver.round_solution(solver.cards, solver.cards, solver.cards, prize)
            self.assertEqual(sum(solution.row_strategy), 1)
            self.assertEqual(sum(solution.column_strategy), 1)
            self.assertTrue(all(probability >= 0 for probability in solution.row_strategy))
            self.assertTrue(all(probability >= 0 for probability in solution.column_strategy))

    def test_seeded_play_is_reproducible(self) -> None:
        solver = GoofspielSolver(4)
        self.assertEqual(solver.play(71, "equilibrium"), solver.play(71, "equilibrium"))

    def test_exact_ai_punishes_simple_high_card_policy(self) -> None:
        solver = GoofspielSolver(4)
        summaries = {item.policy: item for item in solver.compare(200, seed=500)}
        self.assertLess(summaries["high_card"].player_mean_difference, -0.5)
        self.assertGreaterEqual(summaries["equilibrium"].player_mean_difference, -0.5)

    def test_match_prize_ai_has_exactly_two_points_of_exploitability(self) -> None:
        solver = GoofspielSolver(4)
        self.assertEqual(
            solver.best_response_value_against_match_prize(
                solver.cards, solver.cards, solver.cards
            ),
            Fraction(2),
        )


if __name__ == "__main__":
    unittest.main()
