import unittest
from fractions import Fraction

from aip.puzzles.kuhn_poker import (
    audit_policy,
    basic_policy,
    equilibrium_policy,
    game_value,
    legacy_policy,
    policy_value,
)


class KuhnPokerStrategyTests(unittest.TestCase):
    def test_exact_policy_has_zero_exploitability_from_both_seats(self) -> None:
        audit = audit_policy(equilibrium_policy())
        self.assertEqual(audit.first_seat_best_response, game_value(True))
        self.assertEqual(audit.second_seat_best_response, game_value(False))
        self.assertEqual(audit.maximum_exploitability, 0)

    def test_legacy_queen_call_frequency_was_exploitable_from_second_seat(self) -> None:
        audit = audit_policy(legacy_policy())
        self.assertEqual(audit.first_seat_exploitability, 0)
        self.assertEqual(audit.second_seat_best_response, Fraction(1, 6))
        self.assertEqual(audit.second_seat_exploitability, Fraction(1, 9))

    def test_equilibrium_uses_position_specific_queen_call_frequencies(self) -> None:
        policy = equilibrium_policy()
        self.assertEqual(policy.first_call_after_check_bet["Q"], Fraction(2, 3))
        self.assertEqual(policy.second_call_open_bet["Q"], Fraction(1, 3))

    def test_second_seat_gto_has_positive_value_against_both_modes(self) -> None:
        gto = equilibrium_policy()
        self.assertEqual(policy_value(gto, gto, hero_first=True), Fraction(-1, 18))
        self.assertEqual(policy_value(gto, gto, hero_first=False), Fraction(1, 18))
        self.assertEqual(
            policy_value(gto, basic_policy(), hero_first=False), Fraction(1, 18)
        )

    def test_basic_ai_exposes_additional_second_seat_value(self) -> None:
        audit = audit_policy(basic_policy())
        self.assertEqual(audit.second_seat_best_response, Fraction(1, 6))
        self.assertEqual(audit.second_seat_exploitability, Fraction(1, 9))


if __name__ == "__main__":
    unittest.main()
