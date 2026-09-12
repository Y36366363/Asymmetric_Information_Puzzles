import unittest

from aip.core import CFRResult, ExternalSamplingCFRTrainer
from aip.puzzles.love_letter import (
    LoveLetterCFRGame,
    LoveLetterState,
    audit_complete_tree,
    certify_love_letter_subgame,
    complete_information_set_actions,
    love_letter_subgame_exploitability,
)
from aip.puzzles.love_letter.solver import CARD_COUNTS, Play


def card_counts(*cards: int) -> tuple[int, ...]:
    return tuple(cards.count(value) for value in range(1, 9))


class LoveLetterExtensiveFormTests(unittest.TestCase):
    def test_full_round_root_is_the_complete_sixteen_card_deck(self) -> None:
        game = LoveLetterCFRGame()
        root = game.initial_state()
        outcomes = game.chance_outcomes(root)
        self.assertEqual(root.remaining, tuple(CARD_COUNTS.values()))
        self.assertEqual({action for action, _ in outcomes}, set(range(1, 9)))
        self.assertAlmostEqual(sum(probability for _, probability in outcomes), 1)
        self.assertEqual(
            dict(outcomes)[1], CARD_COUNTS[1] / sum(CARD_COUNTS.values())
        )
        with self.assertRaisesRegex(OverflowError, "exceeds 10000 histories"):
            audit_complete_tree(game, maximum_histories=10_000)

    def test_information_set_excludes_opponent_hand_deck_and_burn(self) -> None:
        game = LoveLetterCFRGame()
        common = dict(
            stage="play",
            face_up=(5, 6, 7),
            hands=((1, 2), (3,)),
            actor=0,
            private_history=((('initial_hand', 1), ('draw', 0, 2)), ()),
        )
        first = LoveLetterState(
            **common, remaining=card_counts(4, 8), burn=5
        )
        second = LoveLetterState(
            **{**common, "hands": ((1, 2), (4,))},
            remaining=card_counts(3, 7),
            burn=6,
        )
        self.assertEqual(game.information_set(first), game.information_set(second))
        self.assertNotEqual(game.hidden_world(first, 0), game.hidden_world(second, 0))

    def test_countess_prince_king_and_princess_rules_are_in_tree_model(self) -> None:
        game = LoveLetterCFRGame()
        countess = LoveLetterState(
            stage="play", remaining=card_counts(1), hands=((6, 7), (2,)), actor=0
        )
        self.assertEqual(game.legal_actions(countess), (Play(7),))

        prince = LoveLetterState(
            stage="play",
            remaining=card_counts(1),
            hands=((2, 5), (8,)),
            actor=0,
        )
        prince_end = game.next_state(prince, Play(5, "ai"))
        self.assertTrue(game.is_terminal(prince_end))
        self.assertEqual(prince_end.winner, 0)

        king = LoveLetterState(
            stage="play",
            remaining=card_counts(1),
            hands=((2, 6), (3,)),
            actor=0,
        )
        after_king = game.next_state(king, Play(6, "ai"))
        self.assertEqual(after_king.hands, ((3,), (2,)))
        self.assertIn(("king_received", 0, 3), after_king.private_history[0])
        self.assertIn(("king_received", 0, 2), after_king.private_history[1])

        princess = LoveLetterState(
            stage="play",
            remaining=card_counts(1),
            hands=((2, 8), (3,)),
            actor=0,
        )
        princess_end = game.next_state(princess, Play(8))
        self.assertTrue(game.is_terminal(princess_end))
        self.assertEqual(princess_end.winner, 1)

    def test_four_card_subgame_has_a_complete_hidden_information_tree(self) -> None:
        audit = audit_complete_tree(LoveLetterCFRGame.late_round_subgame())
        self.assertTrue(audit.passed)
        self.assertEqual(audit.histories, 1_081)
        self.assertEqual(audit.terminal_histories, 624)
        self.assertEqual(audit.information_sets, 60)
        self.assertEqual(audit.hidden_information_sets, 60)
        self.assertEqual(audit.maximum_depth, 5)

    def test_independent_best_response_detects_and_then_certifies_policy(self) -> None:
        game = LoveLetterCFRGame.late_round_subgame()
        tables = complete_information_set_actions(game)
        uniform = CFRResult(
            iterations=1,
            policy={
                key: {action: 1 / len(actions) for action in actions}
                for key, actions in tables.items()
            },
            information_set_visits={key: 1 for key in tables},
            average_positive_regret=(1, 1),
        )
        self.assertAlmostEqual(
            love_letter_subgame_exploitability(game, uniform), 0.375
        )

        result = ExternalSamplingCFRTrainer(game, seed=20260912).train(20_000)
        report = certify_love_letter_subgame(game, result)
        self.assertTrue(report.passed, report.failures)
        self.assertEqual(result.information_set_count, 60)
        self.assertGreaterEqual(min(result.information_set_visits.values()), 1_000)
        self.assertLessEqual(report.exploitability, 0.001)


if __name__ == "__main__":
    unittest.main()
