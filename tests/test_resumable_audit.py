import tempfile
import unittest
from pathlib import Path

from aip.core.resumable_audit import ResumableTreeAudit
from aip.core.tree_evaluation import audit_small_extensive_form
from aip.puzzles.kuhn_poker import KuhnCFRGame
from aip.puzzles.love_letter import LoveLetterCFRGame
from test_game_compatibility import ForgetfulGame, BadChanceGame


class ResumableAuditTests(unittest.TestCase):
    def test_reopened_chunks_equal_complete_reference_for_two_games(self):
        for game in (KuhnCFRGame(), LoveLetterCFRGame.late_round_subgame()):
            with self.subTest(game=type(game).__name__), tempfile.TemporaryDirectory() as folder:
                path = Path(folder)/'audit.sqlite'
                expected = audit_small_extensive_form(game)
                report = None
                while report is None or report['status'] == 'paused':
                    auditor = ResumableTreeAudit(game, path, revision='test_v1')
                    report = auditor.advance(maximum_histories=37)
                    auditor.close()
                self.assertTrue(report['structural_audit_passed'])
                self.assertFalse(report['equilibrium_certified'])
                for field in ('histories', 'terminal_histories', 'chance_histories',
                              'decision_histories', 'information_sets', 'maximum_depth'):
                    self.assertEqual(report[field], getattr(expected, field))

    def test_partial_checkpoint_is_not_certificate_and_revision_must_match(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'audit.sqlite'
            auditor = ResumableTreeAudit(KuhnCFRGame(), path, revision='v1')
            report = auditor.advance(maximum_histories=1)
            auditor.close()
            self.assertFalse(report['structural_audit_passed'])
            self.assertGreater(report['frontier_nodes'], 0)
            with self.assertRaisesRegex(ValueError, 'revision mismatch'):
                ResumableTreeAudit(KuhnCFRGame(), path, revision='v2')

    def test_bad_games_fail_even_across_restarts(self):
        for game in (ForgetfulGame(), BadChanceGame()):
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder)/'audit.sqlite'
                auditor = ResumableTreeAudit(game, path, revision='invalid')
                report = auditor.advance(maximum_histories=100)
                auditor.close()
                self.assertEqual(report['status'], 'failed')
                self.assertFalse(report['structural_audit_passed'])

    def test_exception_rolls_back_entire_chunk(self):
        class Broken(KuhnCFRGame):
            def next_state(self, state, action):
                raise RuntimeError('simulated interruption')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'audit.sqlite'
            auditor = ResumableTreeAudit(Broken(), path, revision='broken')
            with self.assertRaises(RuntimeError):
                auditor.advance(maximum_histories=10)
            self.assertEqual(auditor.report()['histories'], 0)
            auditor.close()
