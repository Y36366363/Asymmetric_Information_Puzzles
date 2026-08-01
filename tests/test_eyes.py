import unittest

from aip.puzzles.eyes.models import EyeRules
from aip.puzzles.eyes.solver import EyeVillageSolver


class EyeVillageSolverTests(unittest.TestCase):
    def test_one_target_acts_on_first_night(self) -> None:
        solution = EyeVillageSolver().solve(1, 9)
        self.assertEqual(solution.action_day, 1)
        self.assertTrue(solution.days[0].target_group_knows)

    def test_three_targets_act_together_on_third_night(self) -> None:
        solution = EyeVillageSolver().solve(3, 7)
        self.assertEqual(solution.action_day, 3)
        self.assertEqual(len(solution.days), 3)
        self.assertFalse(solution.days[1].target_group_knows)
        self.assertTrue(solution.days[2].target_group_knows)

    def test_colours_are_configurable(self) -> None:
        rules = EyeRules(target_color="blue", other_color="brown")
        solution = EyeVillageSolver(rules).solve(2, 4)
        self.assertEqual(solution.action_day, 2)
        self.assertIn("blue", solution.conclusion)

    def test_no_public_announcement_has_no_guaranteed_day(self) -> None:
        rules = EyeRules(public_announcement=False)
        solution = EyeVillageSolver(rules).solve(3, 7)
        self.assertIsNone(solution.action_day)
        self.assertEqual(solution.days, ())

    def test_zero_targets_means_no_action(self) -> None:
        solution = EyeVillageSolver().solve(0, 10)
        self.assertIsNone(solution.action_day)


if __name__ == "__main__":
    unittest.main()
