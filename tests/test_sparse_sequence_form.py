import importlib.util
import unittest
from unittest.mock import patch

from aip.core import (
    CFRGameProperties, compile_sequence_form, solve_sequence_form,
    FullTreeBestResponseEvaluator, run_independent_evaluation,
)
from aip.core.sequence_form import SparseMatrix
from aip.puzzles.kuhn_poker import KuhnCFRGame
from aip.puzzles.e_card import ECardTimingCFRGame
from aip.puzzles.love_letter import LoveLetterCFRGame


PROPERTIES = CFRGameProperties(2, True, True, True)


class SparseSequenceFormTests(unittest.TestCase):
    def test_sparse_compilation_avoids_dense_cell_budget_and_exports_equivalently(self):
        game = LoveLetterCFRGame.late_round_subgame()
        sparse = compile_sequence_form(game, game_properties=PROPERTIES,
                                       sparse=True, maximum_matrix_cells=1)
        dense = compile_sequence_form(game, game_properties=PROPERTIES)
        self.assertIsInstance(sparse.payoff_matrix, SparseMatrix)
        for field in ('flow_entries', 'payoff_shape'):
            self.assertEqual(sparse.to_artifact()[field], dense.to_artifact()[field])
        self.assertEqual(sorted(sparse.to_artifact()['payoff_entries']),
                         sorted(dense.to_artifact()['payoff_entries']))
        with self.assertRaisesRegex(ValueError, 'requires scipy_highs'):
            solve_sequence_form(sparse)

    def test_nonzero_budget_and_invalid_backend_fail_closed(self):
        with self.assertRaisesRegex(OverflowError, 'nonzero budget'):
            compile_sequence_form(KuhnCFRGame(), game_properties=PROPERTIES,
                                  sparse=True, maximum_nonzeros=1)
        form = compile_sequence_form(KuhnCFRGame(), game_properties=PROPERTIES)
        with self.assertRaisesRegex(ValueError, 'unknown'):
            solve_sequence_form(form, backend='fake')
        with self.assertRaisesRegex(ValueError, 'time limit'):
            solve_sequence_form(form, time_limit=float('nan'))

    @unittest.skipUnless(importlib.util.find_spec('scipy'), 'optional scipy unavailable')
    def test_sparse_highs_matches_dense_and_independent_oracle_for_three_games(self):
        for game in (KuhnCFRGame(), ECardTimingCFRGame(),
                     LoveLetterCFRGame.late_round_subgame()):
            with self.subTest(game=type(game).__name__):
                sparse = compile_sequence_form(game, game_properties=PROPERTIES, sparse=True)
                result = solve_sequence_form(sparse, backend='scipy_highs')
                reference = solve_sequence_form(compile_sequence_form(
                    game, game_properties=PROPERTIES))
                self.assertAlmostEqual(result.value_to_player_0,
                                       reference.value_to_player_0, places=12)
                report = run_independent_evaluation(
                    FullTreeBestResponseEvaluator(game, evaluator_id='independent_test'),
                    result.policy, maximum_exploitability=1e-12)
                self.assertTrue(report.passed)
                self.assertEqual(result.backend, 'scipy_highs')

    @unittest.skipUnless(importlib.util.find_spec('scipy'), 'optional scipy unavailable')
    def test_failed_backend_result_cannot_become_a_policy(self):
        from types import SimpleNamespace
        form = compile_sequence_form(KuhnCFRGame(), game_properties=PROPERTIES, sparse=True)
        with patch('scipy.optimize.linprog', return_value=SimpleNamespace(
                success=False, status=1, message='time limit exceeded')):
            with self.assertRaisesRegex(ValueError, 'time limit exceeded'):
                solve_sequence_form(form, backend='scipy_highs')
