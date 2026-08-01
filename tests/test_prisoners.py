import unittest

from aip.puzzles.prisoners.models import DeclarationGoal, InitialLight
from aip.puzzles.prisoners.solver import PrisonerLightSolver


class PrisonerLightSolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.solver = PrisonerLightSolver()

    def test_known_off_strategy_declares_after_each_non_counter_signals(self) -> None:
        plan = self.solver.create_plan(3, InitialLight.OFF)
        result = self.solver.run_schedule(plan, [0, 0, 1, 0, 2, 0])
        self.assertTrue(result.completed)
        self.assertEqual(result.declaration_day, 6)
        self.assertTrue(result.declaration_was_safe)
        self.assertEqual(result.signal_counts, (1, 1, 1))

    def test_unknown_initial_on_cannot_create_unsafe_declaration(self) -> None:
        plan = self.solver.create_plan(
            3, InitialLight.UNKNOWN, DeclarationGoal.VISITED
        )
        # Initial-on creates one phantom count. Prisoner 1 can add only two;
        # without prisoner 2 the threshold of four remains unreachable.
        incomplete = self.solver.run_schedule(
            plan, [0, 1, 0, 1, 0, 0], actual_initial_on=True
        )
        self.assertFalse(incomplete.completed)
        result = self.solver.run_schedule(
            plan, [0, 1, 0, 1, 0, 2, 0], actual_initial_on=True
        )
        self.assertTrue(result.completed)
        self.assertTrue(result.declaration_was_safe)

    def test_random_simulation_is_reproducible_and_safe(self) -> None:
        plan = self.solver.create_plan(20, InitialLight.OFF)
        first = self.solver.simulate(plan, seed=42)
        second = self.solver.simulate(plan, seed=42)
        self.assertEqual(first.declaration_day, second.declaration_day)
        self.assertTrue(first.declaration_was_safe)

    def test_unknown_light_and_literal_turned_on_goal(self) -> None:
        plan = self.solver.create_plan(3, InitialLight.UNKNOWN)
        result = self.solver.run_schedule(
            plan,
            [0, 0, 0, 1, 0, 1, 0, 2, 0],
            actual_initial_on=True,
        )
        self.assertTrue(result.completed)
        self.assertTrue(result.declaration_was_safe)
        self.assertTrue(all(signal >= 1 for signal in result.signal_counts))

    def test_one_prisoner_declares_on_first_visit(self) -> None:
        plan = self.solver.create_plan(1, InitialLight.OFF)
        result = self.solver.run_schedule(plan, [0])
        self.assertTrue(result.completed)
        self.assertTrue(result.declaration_was_safe)
        self.assertEqual(result.signal_counts, (1,))


if __name__ == "__main__":
    unittest.main()
