import unittest

from aip.puzzles.beans.models import BeanRules
from aip.puzzles.beans.solver import BeanSolver


class BeanSolverTests(unittest.TestCase):
    def test_exact_count_analysis_is_consistent_with_action_risk(self) -> None:
        solution = BeanSolver().solve(12, 16)
        for analysis in solution.analyses:
            for risk in solution.action_risks:
                self.assertEqual(
                    risk.action in analysis.safe_actions,
                    analysis.beans in risk.safe_counts,
                )

    def test_single_bean_has_no_safe_action(self) -> None:
        solution = BeanSolver().solve(1, 1)
        self.assertFalse(solution.has_zero_risk_action)
        self.assertEqual(solution.analyses[0].safe_actions, ())

    def test_information_set_covers_interval(self) -> None:
        rules = BeanRules(player_count=5, min_take=1, max_take=3)
        solution = BeanSolver(rules).solve(8, 10)
        self.assertEqual(
            tuple(state.beans for state in solution.information_set.possible_states),
            (8, 9, 10),
        )

    def test_interval_can_have_one_robust_action(self) -> None:
        solution = BeanSolver().solve(4, 7)
        self.assertEqual(solution.robust_actions, (3,))
        self.assertEqual(solution.recommended_action, 3)


if __name__ == "__main__":
    unittest.main()
