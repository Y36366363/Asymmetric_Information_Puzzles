import unittest

from aip.core import (
    CFRGameProperties, FullTreeBestResponseEvaluator, compile_sequence_form,
    solve_sequence_form, run_independent_evaluation,
)
from aip.puzzles.kuhn_poker import KuhnCFRGame, solve_kuhn_sequence_form
from aip.puzzles.e_card import ECardTimingCFRGame
from aip.puzzles.love_letter import LoveLetterCFRGame
from test_game_compatibility import ForgetfulGame, BadChanceGame


PROPERTIES = CFRGameProperties(2, True, True, True)


class SequenceFormCompilerTests(unittest.TestCase):
    def test_three_distinct_adapter_structures_solve_and_certify(self):
        for game, value, shape in (
            (KuhnCFRGame(), -1/18, (13, 13)),
            (ECardTimingCFRGame(), -0.2, (6, 6)),
            (LoveLetterCFRGame.late_round_subgame(), 1/6, (61, 145)),
        ):
            with self.subTest(game=type(game).__name__):
                form = compile_sequence_form(game, game_properties=PROPERTIES)
                self.assertEqual(tuple(map(len, form.player_sequences)), shape)
                solution = solve_sequence_form(form)
                self.assertAlmostEqual(solution.value_to_player_0, value, places=12)
                self.assertLess(solution.primal_dual_gap, 1e-12)
                self.assertLess(solution.maximum_flow_residual, 1e-12)
                evaluator = FullTreeBestResponseEvaluator(game, evaluator_id='test')
                report = run_independent_evaluation(
                    evaluator, solution.policy, maximum_exploitability=1e-12)
                self.assertTrue(report.passed)
                self.assertAlmostEqual(report.expected_value_to_player_0, value)
                self.assertEqual(len(solution.policy), form.audit.information_sets)
                artifact = form.to_artifact()
                self.assertEqual(artifact['payoff_shape'], list(shape))
                for distribution in solution.policy.values():
                    self.assertAlmostEqual(sum(distribution.values()), 1.0)

    def test_kuhn_specialized_lp_value_matches_generic(self):
        form = compile_sequence_form(KuhnCFRGame(), game_properties=PROPERTIES)
        self.assertAlmostEqual(solve_sequence_form(form).value_to_player_0,
                               solve_kuhn_sequence_form().value_to_player_0)

    def test_invalid_adapters_and_scope_fail_closed(self):
        for game in (ForgetfulGame(), BadChanceGame()):
            with self.assertRaisesRegex(ValueError, 'audit failed'):
                compile_sequence_form(game, game_properties=PROPERTIES)
        with self.assertRaisesRegex(ValueError, 'two-player'):
            compile_sequence_form(KuhnCFRGame(), game_properties=
                                  CFRGameProperties(3, True, False, True))
        with self.assertRaises(OverflowError):
            compile_sequence_form(KuhnCFRGame(), game_properties=PROPERTIES,
                                  maximum_histories=10)
        with self.assertRaisesRegex(OverflowError, 'cell budget'):
            compile_sequence_form(KuhnCFRGame(), game_properties=PROPERTIES,
                                  maximum_matrix_cells=10)

    def test_chance_order_does_not_change_compiled_representation(self):
        class ReversedKuhn(KuhnCFRGame):
            def chance_outcomes(self, state):
                return tuple(reversed(super().chance_outcomes(state)))
        normal = compile_sequence_form(KuhnCFRGame(), game_properties=PROPERTIES)
        reverse = compile_sequence_form(ReversedKuhn(), game_properties=PROPERTIES)
        self.assertEqual(normal.player_sequences, reverse.player_sequences)
        self.assertEqual(normal.flow_matrices, reverse.flow_matrices)
        self.assertEqual(normal.payoff_matrix, reverse.payoff_matrix)
        self.assertEqual(solve_sequence_form(normal).policy,
                         solve_sequence_form(reverse).policy)

    def test_nonfinite_solver_tolerance_is_rejected(self):
        form = compile_sequence_form(KuhnCFRGame(), game_properties=PROPERTIES)
        with self.assertRaisesRegex(ValueError, 'finite'):
            solve_sequence_form(form, tolerance=float('nan'))
