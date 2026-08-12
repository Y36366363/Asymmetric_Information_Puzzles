import random
import unittest

from aip.puzzles.love_letter.solver import LoveLetterGame, Play


class LoveLetterTests(unittest.TestCase):
    def test_two_player_setup_and_hidden_belief(self) -> None:
        game = LoveLetterGame(random.Random(7))
        self.assertEqual(len(game.face_up_removed), 3)
        self.assertEqual(len(game.hands["player"]), 2)
        self.assertEqual(len(game.hands["ai"]), 1)
        self.assertGreaterEqual(sum(game.belief("player").values()), 1)

    def test_countess_is_forced_with_king_or_prince(self) -> None:
        game = LoveLetterGame(random.Random(1))
        game.hands["player"] = [7, 6]
        self.assertEqual(game.legal_cards("player"), [7])
        with self.assertRaises(ValueError):
            game.play("player", Play(6, "ai"))

    def test_princess_discard_loses_round(self) -> None:
        game = LoveLetterGame(random.Random(2))
        game.hands["player"] = [8, 1]
        game.play("player", Play(8))
        self.assertEqual(game.round_winner, "ai")
        self.assertEqual(game.round_reason, "princess")

    def test_advice_is_repeatable_and_does_not_consume_randomness(self) -> None:
        game = LoveLetterGame(random.Random(17))
        before = game.rng.getstate()
        self.assertEqual(game.choose_play("player"), game.choose_play("player"))
        self.assertEqual(game.rng.getstate(), before)

    def test_belief_policy_beats_random_over_seeded_matches(self) -> None:
        wins = 0
        matches = 300
        for seed in range(matches):
            game = LoveLetterGame(random.Random(seed))
            while game.phase != "match_finished":
                if game.phase == "round_finished":
                    game.start_round()
                    continue
                actor = "player" if game.phase == "player_turn" else "ai"
                policy = "belief" if actor == "player" else "random"
                game.play(actor, game.choose_play(actor, policy))
            wins += game.round_winner == "player"
        self.assertGreater(wins / matches, 0.57)


if __name__ == "__main__":
    unittest.main()
