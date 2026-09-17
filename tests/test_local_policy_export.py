import json
from pathlib import Path
import runpy
import unittest

from aip.core import CFRGameProperties, compile_sequence_form, solve_sequence_form, run_independent_evaluation
from aip.puzzles.love_letter import LoveLetterCFRGame, LoveLetterIndependentEvaluator
from aip.puzzles.love_letter.solver import Play


class LocalPolicyExportTests(unittest.TestCase):
    def test_portable_json_roundtrip_preserves_independent_equilibrium(self):
        root = Path(__file__).resolve().parents[1]
        exporter = runpy.run_path(str(root/'scripts/advance_love_letter_local.py'))['portable_policy']
        game = LoveLetterCFRGame.late_round_subgame()
        solution = solve_sequence_form(compile_sequence_form(
            game, game_properties=CFRGameProperties(2, True, True, True)))
        report = run_independent_evaluation(LoveLetterIndependentEvaluator(game),
                                            solution.policy, maximum_exploitability=1e-12)
        payload = json.loads(json.dumps(exporter(solution.policy, report)))
        def freeze(value):
            return tuple(map(freeze, value)) if isinstance(value, list) else value
        recovered = {(r['player'], freeze(r['information_set'])):
                     {Play(**d['action']): d['probability'] for d in r['distribution']}
                     for r in payload['policy']}
        self.assertEqual(recovered, solution.policy)
        checked = run_independent_evaluation(LoveLetterIndependentEvaluator(game),
                                             recovered, maximum_exploitability=1e-12)
        self.assertTrue(checked.passed)
        self.assertFalse(payload['full_round_runtime_allowed'])
        self.assertEqual(payload['scope'], 'four_card_late_round_subgame_only')
        wrong = {key: dict(dist) for key, dist in solution.policy.items()}
        key = next(iter(wrong))
        wrong[key] = {a: 0.0 for a in wrong[key]}
        with self.assertRaisesRegex(ValueError, 'profile-bound'):
            exporter(wrong, report)
