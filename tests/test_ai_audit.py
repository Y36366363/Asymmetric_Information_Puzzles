import unittest

from aip.puzzles.battleship.models import FleetRules
from research.audit_battleship_ai import evolution_audit, paired_tail_audit


class BattleshipAIAuditTests(unittest.TestCase):
    def test_paired_audit_is_reproducible_and_accounts_for_every_game(self) -> None:
        first = paired_tail_audit(12, 20260807)
        second = paired_tail_audit(12, 20260807)

        self.assertEqual(first, second)
        self.assertEqual(
            first.probability_better + first.tied + first.probability_worse,
            first.games,
        )
        self.assertLess(first.mean_shot_delta, 0)

    def test_cluster_consistent_density_beats_its_legacy_baseline(self) -> None:
        result = evolution_audit(300, 20260814)
        self.assertEqual(
            result.enhanced_better + result.tied + result.enhanced_worse,
            result.games,
        )
        self.assertLess(result.mean_shot_delta, 0)
        self.assertLessEqual(result.enhanced_p90, result.legacy_p90)

        large = evolution_audit(12, 20260814, FleetRules(15, (7, 6, 5, 4, 4, 3, 2)))
        self.assertEqual(large.mean_shot_delta, 0)
        self.assertEqual(large.enhanced_p90, large.legacy_p90)


if __name__ == "__main__":
    unittest.main()
