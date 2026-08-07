import unittest

from research.audit_battleship_ai import paired_tail_audit


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


if __name__ == "__main__":
    unittest.main()
