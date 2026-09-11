import random
import unittest

from aip.core import (
    EquilibriumGameStructure,
    EquilibriumMethod,
    audit_stopping_time_compression,
    recommend_equilibrium_solver,
)
from aip.puzzles.e_card import e_card_equilibrium_structure
from aip.puzzles.love_letter import (
    LoveLetterGame,
    love_letter_equilibrium_structure,
)


class EquilibriumPipelineTests(unittest.TestCase):
    def test_e_card_passes_complete_stopping_time_matrix_gate(self) -> None:
        structure = e_card_equilibrium_structure()
        audit = audit_stopping_time_compression(structure.stopping_time)
        recommendation = recommend_equilibrium_solver(structure)
        self.assertTrue(audit.compressible)
        self.assertEqual(audit.matrix_shape, (5, 5))
        self.assertEqual(recommendation.primary, EquilibriumMethod.EXACT_MATRIX)
        self.assertEqual(recommendation.cross_check, EquilibriumMethod.VANILLA_CFR)

    def test_love_letter_fails_timing_compression_for_specific_reasons(self) -> None:
        structure = love_letter_equilibrium_structure()
        audit = audit_stopping_time_compression(structure.stopping_time)
        self.assertFalse(audit.compressible)
        self.assertEqual(
            set(audit.failures),
            {
                "private_information_not_fixed_at_start",
                "new_private_information_arrives",
                "strategic_actions_exist_before_stopping",
                "payoff_requires_more_than_stopping_times",
            },
        )
        recommendation = recommend_equilibrium_solver(structure)
        self.assertEqual(
            recommendation.primary, EquilibriumMethod.EXTERNAL_SAMPLING_MCCFR
        )
        self.assertEqual(recommendation.cross_check, EquilibriumMethod.SEQUENCE_FORM)

    def test_live_love_letter_really_draws_new_private_information(self) -> None:
        game = LoveLetterGame(random.Random(7))
        game.deck = [6]
        game.hands["ai"] = [2]
        game._begin_turn("ai")
        self.assertEqual(game.hands["ai"], [2, 6])
        self.assertEqual(game.deck, [])

    def test_multiplayer_general_sum_game_is_not_gto_gate_eligible(self) -> None:
        recommendation = recommend_equilibrium_solver(
            EquilibriumGameStructure(
                players=6,
                finite=True,
                zero_sum_or_constant_sum=False,
                perfect_recall=True,
                chance_after_initial_state=True,
            )
        )
        self.assertFalse(recommendation.eligible_for_gto_pipeline)
        self.assertEqual(recommendation.primary, EquilibriumMethod.UNSUPPORTED)
        self.assertEqual(
            set(recommendation.reasons),
            {"requires_two_players", "requires_zero_or_constant_sum"},
        )


if __name__ == "__main__":
    unittest.main()
