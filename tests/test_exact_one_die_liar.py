import importlib.util
import json
import unittest
from pathlib import Path

from aip.core import PromotionEvidence, PromotionLevel, decide_promotion
from aip.core.evaluation import run_independent_evaluation, strategy_profile_fingerprint
from aip.puzzles.liars_dice import (
    OneDieLiarIndependentEvaluator, load_one_die_liar_policy,
    solve_one_die_liar_exact,
)


@unittest.skipUnless(importlib.util.find_spec('scipy'), 'optional scipy unavailable')
class ExactOneDieLiarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.form, cls.solution = solve_one_die_liar_exact()
        cls.report = run_independent_evaluation(
            OneDieLiarIndependentEvaluator(), cls.solution.policy,
            maximum_exploitability=1e-10)

    def test_sparse_sequence_form_is_exact_and_complete(self):
        self.assertEqual(tuple(map(len, self.form.player_sequences)), (343, 343))
        self.assertEqual(self.form.audit.histories, 4_141)
        self.assertEqual(len(self.solution.policy), 348)
        self.assertAlmostEqual(self.solution.value_to_player_0, 0.5, places=12)
        self.assertLess(self.solution.primal_dual_gap, 1e-12)
        self.assertLess(self.solution.maximum_flow_residual, 1e-12)
        self.assertTrue(self.report.passed)
        self.assertLess(self.report.exploitability, 1e-12)

    def test_exact_solution_strictly_improves_frozen_cfr_candidate(self):
        old = load_one_die_liar_policy(Path(__file__).resolve().parents[1]/
            'src/aip/puzzles/liars_dice/one_die_cfr_policy.json')
        old_report = run_independent_evaluation(
            OneDieLiarIndependentEvaluator(), old.policy,
            maximum_exploitability=0.01)
        self.assertGreater(old_report.exploitability, self.report.exploitability)
        self.assertAlmostEqual(old_report.exploitability, 0.0023538635972168154)

    def test_exact_cross_checked_artifact_reaches_frozen_without_runtime_change(self):
        fingerprint = strategy_profile_fingerprint(self.solution.policy)
        promotion = decide_promotion(PromotionEvidence(
            artifact_complete=True, artifact_profile_fingerprint=fingerprint,
            independent_report=self.report, cross_method_agreement=True,
            reproducible=True, artifact_frozen=True))
        self.assertEqual(promotion.level, PromotionLevel.FROZEN)
        for distribution in self.solution.policy.values():
            self.assertAlmostEqual(sum(distribution.values()), 1.0)

    def test_frozen_research_artifact_contains_complete_policy(self):
        path = Path(__file__).resolve().parents[1]/(
            'research/results/one_die_liar_exact_2026-09-18.json')
        artifact = json.loads(path.read_text())
        self.assertTrue(artifact['passed'])
        self.assertTrue(artifact['live_runtime_unchanged'])
        self.assertEqual(len(artifact['policy']), len(self.solution.policy))
        # The sparse LP can return another realization-equivalent equilibrium
        # across HiGHS versions.  Bind the frozen fingerprint to the policy that
        # was actually frozen instead of requiring a fresh solve to reproduce a
        # particular member of a non-unique equilibrium set bit for bit.
        frozen_policy = {}
        for record in artifact['policy']:
            information_set = (
                int(record['die']),
                tuple(tuple(map(int, bid)) for bid in record['bids']),
            )
            key = (int(record['player']), information_set)
            self.assertNotIn(key, frozen_policy)
            distribution = {}
            for item in record['distribution']:
                raw_action = item['action']
                action = ('challenge' if raw_action == 'challenge'
                          else tuple(map(int, raw_action)))
                distribution[action] = float(item['probability'])
            frozen_policy[key] = distribution

        fingerprint = strategy_profile_fingerprint(frozen_policy)
        self.assertEqual(artifact['profile_fingerprint'], fingerprint)
        self.assertEqual(
            artifact['independent_evaluation']['profile_fingerprint'], fingerprint
        )
        frozen_report = run_independent_evaluation(
            OneDieLiarIndependentEvaluator(), frozen_policy,
            maximum_exploitability=1e-10,
        )
        self.assertTrue(frozen_report.passed, frozen_report.failures)
        self.assertAlmostEqual(
            frozen_report.exploitability,
            artifact['independent_evaluation']['exploitability'],
            places=12,
        )
