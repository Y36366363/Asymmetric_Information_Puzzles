import unittest
import json
import threading
from importlib.resources import files
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

from aip.ui.registry import (
    BlackjackSession,
    ECardSession,
    LiarDiceSession,
    LocalGameService,
    RestrictedRPSSession,
    build_default_registry,
)
from aip.ui.server import AIPRequestHandler


class LocalGameUITests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = LocalGameService(build_default_registry())

    def test_lobby_lists_one_playable_game_and_future_games(self) -> None:
        games = self.service.games()
        playable = [game["id"] for game in games if game["available"]]
        self.assertEqual(
            playable,
            [
                "cases",
                "blackjack",
                "restricted-rps",
                "mastermind",
                "battleship",
                "e-card",
                "pirates",
                "kuhn-poker",
                "liars-dice",
                "worm",
            ],
        )
        self.assertIn("liars-dice", [game["id"] for game in games])

    def test_battleship_hides_enemy_fleet_and_completes_against_ai(self) -> None:
        created = self.service.create_session("battleship", {"seed": 41})
        state = created["state"]
        self.assertEqual(state["phase"], "placement")
        self.assertEqual(sum(cell["ship"] for cell in state["playerBoard"]), 17)
        self.assertFalse(any(cell["ship"] for cell in state["enemyBoard"]))
        state = self.service.act(created["sessionId"], "start_battle")
        while state["phase"] == "player_turn":
            row, column = state["suggestedShot"]
            state = self.service.act(
                created["sessionId"], "fire", {"row": row, "column": column}
            )
        self.assertEqual(state["phase"], "finished")
        self.assertIn(state["winner"], {"player", "ai"})
        self.assertLessEqual(state["turn"], 100)
        self.assertTrue(any(cell["ship"] for cell in state["enemyBoard"]))

    def test_battleship_rejects_repeat_shots(self) -> None:
        created = self.service.create_session("battleship", {"seed": 17})
        self.service.act(created["sessionId"], "start_battle")
        self.service.act(created["sessionId"], "fire", {"row": 0, "column": 0})
        with self.assertRaisesRegex(ValueError, "same cell"):
            self.service.act(
                created["sessionId"], "fire", {"row": 0, "column": 0}
            )

    def test_blackjack_ace_totals_are_soft_until_ace_must_shrink(self) -> None:
        self.assertEqual(BlackjackSession._hand_value(["A", "6"]), (17, True))
        self.assertEqual(BlackjackSession._hand_value(["A", "6", "K"]), (17, False))
        self.assertEqual(BlackjackSession._hand_value(["A", "A", "9"]), (21, True))

    def test_blackjack_basic_strategy_is_rule_scoped_and_deterministic(self) -> None:
        session = BlackjackSession({"seed": 1})
        session.player_hand = ["10", "6"]
        session.dealer_hand = ["6", "K"]
        self.assertEqual(session._recommendation(), "stand")
        session.dealer_hand = ["10", "6"]
        self.assertEqual(session._recommendation(), "hit")
        session.player_hand = ["5", "6"]
        session.dealer_hand = ["6", "10"]
        self.assertEqual(session._recommendation(), "double")

    def test_blackjack_hides_dealer_hole_card_until_settlement(self) -> None:
        created = self.service.create_session("blackjack", {"seed": 6})
        state = created["state"]
        self.assertTrue(state["dealerHoleHidden"])
        self.assertEqual(len(state["dealerHand"]), 1)
        self.assertEqual(state["strategyScope"], "six_deck_s17_no_split_no_surrender_no_counting")
        state = self.service.act(created["sessionId"], "stand")
        self.assertFalse(state["dealerHoleHidden"])
        self.assertGreaterEqual(len(state["dealerHand"]), 2)

    def test_blackjack_ai_action_always_matches_basic_strategy(self) -> None:
        created = self.service.create_session("blackjack", {"seed": 1})
        state = self.service.act(created["sessionId"], "ai_play")
        self.assertTrue(state["history"][0]["matched"])
        self.assertEqual(state["history"][0]["actor"], "ai")
        self.assertEqual(state["strategyAccuracy"], 1.0)

    def test_blackjack_manual_deviation_is_audited(self) -> None:
        created = self.service.create_session("blackjack", {"seed": 6})
        state = created["state"]
        self.assertEqual(state["recommendation"], "stand")
        state = self.service.act(created["sessionId"], "hit")
        self.assertFalse(state["history"][0]["matched"])
        self.assertEqual(state["strategyAccuracy"], 0.0)

    def test_restricted_rps_dominance_cycle_is_zero_sum(self) -> None:
        self.assertEqual(RestrictedRPSSession._payoff("rock", "scissors"), 1)
        self.assertEqual(RestrictedRPSSession._payoff("paper", "rock"), 1)
        self.assertEqual(RestrictedRPSSession._payoff("scissors", "paper"), 1)
        self.assertEqual(RestrictedRPSSession._payoff("rock", "paper"), -1)
        self.assertEqual(RestrictedRPSSession._payoff("rock", "rock"), 0)

    def test_restricted_rps_consumes_public_inventory(self) -> None:
        created = self.service.create_session("restricted-rps", {"seed": 5})
        state = self.service.act(
            created["sessionId"], "play_move", {"move": "rock"}
        )
        self.assertEqual(state["playerInventory"]["rock"], 2)
        self.assertEqual(sum(state["aiInventory"].values()), 8)
        self.assertEqual(state["roundNumber"], 1)

    def test_restricted_rps_strategy_probabilities_normalize(self) -> None:
        created = self.service.create_session("restricted-rps", {"seed": 11})
        state = self.service.act(
            created["sessionId"], "play_move", {"move": "paper"}
        )
        analysis = state["lastAnalysis"]
        self.assertAlmostEqual(sum(analysis["equilibriumDistribution"].values()), 1)
        self.assertAlmostEqual(sum(analysis["finalDistribution"].values()), 1)
        self.assertGreaterEqual(analysis["exploitWeight"], 0)
        self.assertLessEqual(analysis["exploitWeight"], 0.32)

    def test_restricted_rps_exact_minimax_has_zero_symmetric_value(self) -> None:
        session = RestrictedRPSSession({"seed": 13})
        value, ai_mix, player_mix = session._solve_minimax(
            (3, 3, 3), (3, 3, 3)
        )
        self.assertAlmostEqual(value, 0.0)
        self.assertAlmostEqual(sum(ai_mix), 1.0)
        self.assertAlmostEqual(sum(player_mix), 1.0)

    def test_restricted_rps_match_uses_every_card_once(self) -> None:
        created = self.service.create_session(
            "restricted-rps", {"seed": 19, "copies": 1}
        )
        session_id = created["sessionId"]
        state = created["state"]
        for move in ("rock", "paper", "scissors"):
            state = self.service.act(session_id, "play_move", {"move": move})
        self.assertEqual(state["phase"], "finished")
        self.assertEqual(state["roundNumber"], 3)
        self.assertEqual(sum(state["playerInventory"].values()), 0)
        self.assertEqual(state["playerScore"] + state["aiScore"] + state["draws"], 3)

    def test_e_card_uses_the_asymmetric_dominance_cycle(self) -> None:
        self.assertEqual(ECardSession._outcome("emperor", "citizen"), "player")
        self.assertEqual(ECardSession._outcome("citizen", "slave"), "player")
        self.assertEqual(ECardSession._outcome("slave", "emperor"), "player")
        self.assertEqual(ECardSession._outcome("citizen", "citizen"), "draw")

    def test_e_card_hides_ai_choice_until_player_commits(self) -> None:
        created = self.service.create_session("e-card", {"seed": 7})
        state = created["state"]
        self.assertNotIn("aiHand", state)
        self.assertIsNone(state["lastReveal"])
        self.assertEqual(state["informationSet"]["opponentCardsLeft"], 5)
        state = self.service.act(
            created["sessionId"], "play_card", {"card": "citizen"}
        )
        self.assertIn(state["lastReveal"]["aiCard"], {"citizen", "slave"})

    def test_e_card_scores_by_winning_role_and_swaps_sides(self) -> None:
        created = self.service.create_session("e-card", {"seed": 17})
        session_id = created["sessionId"]
        state = created["state"]
        while state["phase"] == "playing":
            card = state["playerHand"][0]["card"]
            state = self.service.act(session_id, "play_card", {"card": card})
        expected_points = 5 if state["result"]["winnerRole"] == "slave" else 1
        self.assertEqual(state["result"]["points"], expected_points)
        state = self.service.act(session_id, "next_round")
        self.assertEqual(state["roundNumber"], 2)
        self.assertEqual(state["playerRole"], "slave")
        self.assertEqual(state["aiRole"], "emperor")

    def test_e_card_rejects_a_card_not_in_the_current_hand(self) -> None:
        created = self.service.create_session("e-card", {"seed": 29})
        with self.assertRaises(ValueError):
            self.service.act(
                created["sessionId"], "play_card", {"card": "not-a-card"}
            )

    def test_kuhn_poker_keeps_ai_card_private_until_hand_finishes(self) -> None:
        created = self.service.create_session("kuhn-poker", {"seed": 23})
        state = created["state"]
        self.assertIsNone(state["aiCard"])
        self.assertEqual(len(state["informationSet"]["possibleOpponentCards"]), 2)
        self.assertNotIn(
            state["playerCard"], state["informationSet"]["possibleOpponentCards"]
        )

        while state["phase"] == "playing":
            action = state["legalActions"][0]
            state = self.service.act(created["sessionId"], action)
        self.assertIn(state["aiCard"], {"J", "Q", "K"})
        self.assertEqual(state["playerScore"] + state["aiScore"], 0)

    def test_kuhn_poker_continues_as_a_scored_multi_hand_match(self) -> None:
        created = self.service.create_session("kuhn-poker", {"seed": 31})
        session_id = created["sessionId"]
        state = created["state"]
        while state["phase"] == "playing":
            state = self.service.act(session_id, state["legalActions"][-1])
        score = state["playerScore"]
        state = self.service.act(session_id, "next_hand")
        self.assertEqual(state["handNumber"], 2)
        self.assertEqual(state["playerScore"], score)
        self.assertFalse(state["playerIsFirst"])
        self.assertIsNone(state["aiCard"])

    def test_kuhn_poker_rejects_actions_outside_the_information_set(self) -> None:
        created = self.service.create_session("kuhn-poker", {"seed": 41})
        with self.assertRaises(ValueError):
            self.service.act(created["sessionId"], "call")

    def test_case_value_stays_hidden_until_opened_or_finished(self) -> None:
        created = self.service.create_session("cases", {"seed": 7})
        session_id = created["sessionId"]
        state = self.service.act(session_id, "choose_case", {"caseId": 4})
        chosen = next(case for case in state["cases"] if case["id"] == 4)
        self.assertNotIn("value", chosen)
        self.assertNotIn("seed", state)

    def test_six_reveals_trigger_first_banker_offer(self) -> None:
        created = self.service.create_session(
            "cases", {"seed": 11, "riskTolerance": 100_000}
        )
        session_id = created["sessionId"]
        self.service.act(session_id, "choose_case", {"caseId": 1})
        for case_id in range(2, 8):
            state = self.service.act(session_id, "open_case", {"caseId": case_id})
        self.assertEqual(state["phase"], "offer")
        self.assertIsNotNone(state["offer"])
        self.assertIsNotNone(state["metrics"])
        self.assertEqual(
            len([case for case in state["cases"] if case["status"] == "opened"]), 6
        )

    def test_accepting_offer_finishes_game(self) -> None:
        created = self.service.create_session("cases", {"seed": 13})
        session_id = created["sessionId"]
        self.service.act(session_id, "choose_case", {"caseId": 1})
        for case_id in range(2, 8):
            state = self.service.act(session_id, "open_case", {"caseId": case_id})
        offer = state["offer"]
        finished = self.service.act(session_id, "deal")
        self.assertEqual(finished["phase"], "finished")
        self.assertEqual(finished["payout"], offer)

    def test_rejecting_every_offer_reaches_chosen_case_payout(self) -> None:
        created = self.service.create_session("cases", {"seed": 17})
        session_id = created["sessionId"]
        state = self.service.act(session_id, "choose_case", {"caseId": 26})
        while state["phase"] != "finished":
            if state["phase"] == "opening":
                case_id = next(
                    case["id"] for case in state["cases"] if case["status"] == "closed"
                )
                state = self.service.act(session_id, "open_case", {"caseId": case_id})
            else:
                state = self.service.act(session_id, "no_deal")
        chosen = next(case for case in state["cases"] if case["id"] == 26)
        self.assertEqual(state["payout"], chosen["value"])
        self.assertEqual(state["result"]["kind"], "kept_case")
        self.assertIsNotNone(state["payout"])
        self.assertEqual(
            len([case for case in state["cases"] if case["status"] == "opened"]), 25
        )

    def test_illegal_action_is_rejected(self) -> None:
        created = self.service.create_session("cases", {"seed": 19})
        with self.assertRaises(ValueError):
            self.service.act(created["sessionId"], "deal")

    def test_pirate_allocations_reject_fractional_coins(self) -> None:
        created = self.service.create_session("pirates", {"pirates": 5, "gold": 100})
        with self.assertRaisesRegex(ValueError, "whole coins"):
            self.service.act(
                created["sessionId"],
                "submit_proposal",
                {"allocation": [97.5, 1.5, 1, 0, 0]},
            )

    def test_discrete_game_inputs_reject_fractional_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "whole number"):
            self.service.create_session("worm", {"holes": 5.5})
        worm = self.service.create_session("worm", {"holes": 5})
        with self.assertRaisesRegex(ValueError, "whole number"):
            self.service.act(worm["sessionId"], "check_hole", {"holeId": 2.5})
        liar = self.service.create_session("liars-dice", {"dice": 5})
        with self.assertRaisesRegex(ValueError, "whole number"):
            self.service.act(
                liar["sessionId"], "raise_bid", {"quantity": 1.5, "face": 2}
            )

    def test_liars_dice_ai_uses_its_own_private_hand(self) -> None:
        session = LiarDiceSession({"seed": 7, "dice": 5})
        session.player_dice = [1, 2, 3, 6, 6]
        session.ai_dice = [2, 3, 4, 5, 5]
        session.current_bid = (3, 6)
        session.history = []
        session.phase = "bidding"
        session.turn = "ai"
        session._ai_response()
        self.assertEqual(session.history[0]["action"], "challenge")

    def test_health_endpoint_identifies_running_aip_server(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), AIPRequestHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = HTTPConnection("127.0.0.1", server.server_port, timeout=2)
            connection.request("GET", "/api/health")
            response = connection.getresponse()
            payload = json.loads(response.read())
            connection.close()
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["application"], "aip-game-lobby")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_lobby_assets_include_language_and_github_navigation(self) -> None:
        html = files("aip.ui").joinpath("static/index.html").read_text()
        script = files("aip.ui").joinpath("static/app.js").read_text()
        self.assertIn("https://github.com/Y36366363/Asymmetric_Information_Puzzles", html)
        self.assertIn('id="languageEn"', html)
        self.assertIn('en: {', script)
        self.assertIn('localStorage.setItem("aip-language"', script)

    def test_worm_position_is_hidden_while_playing(self) -> None:
        created = self.service.create_session("worm", {"seed": 5})
        state = created["state"]
        self.assertEqual(state["phase"], "playing")
        self.assertEqual(state["mode"], "adversarial")
        self.assertFalse(any(hole["worm"] for hole in state["holes"]))
        self.assertNotIn("seed", state)

    def test_guaranteed_sequence_beats_adversarial_worm_on_last_check(self) -> None:
        created = self.service.create_session("worm", {"mode": "adversarial"})
        session_id = created["sessionId"]
        state = created["state"]
        strategy = state["strategy"]
        for index, hole_id in enumerate(strategy):
            state = self.service.act(session_id, "check_hole", {"holeId": hole_id})
            if index < len(strategy) - 1:
                self.assertEqual(state["phase"], "playing")
        self.assertEqual(state["phase"], "finished")
        self.assertEqual(state["turn"], len(strategy))
        self.assertTrue(any(hole["worm"] for hole in state["holes"]))
        self.assertTrue(state["history"][-1]["guaranteed"])
        self.assertIsNone(state["suggestedHole"])

    def test_repeated_wrong_check_never_catches_smart_worm(self) -> None:
        created = self.service.create_session("worm")
        state = created["state"]
        for _ in range(20):
            state = self.service.act(
                created["sessionId"], "check_hole", {"holeId": 1}
            )
        self.assertEqual(state["phase"], "playing")
        self.assertEqual(state["turn"], 20)
        self.assertFalse(state["followedStrategy"])

    def test_optimal_pirate_proposal_passes_and_is_recognized(self) -> None:
        created = self.service.create_session("pirates")
        session_id = created["sessionId"]
        self.assertIsNone(created["state"]["optimalAllocation"])
        result = self.service.act(
            session_id, "submit_proposal", {"allocation": [98, 0, 1, 0, 1]}
        )
        self.assertTrue(result["passed"])
        self.assertEqual(result["yesVotes"], 3)
        self.assertTrue(result["matchesOptimal"])

    def test_greedy_pirate_proposal_is_rejected_and_proposer_dies(self) -> None:
        created = self.service.create_session("pirates")
        result = self.service.act(
            created["sessionId"],
            "submit_proposal",
            {"allocation": [100, 0, 0, 0, 0]},
        )
        self.assertFalse(result["passed"])
        self.assertFalse(result["realizedAlive"][0])
        self.assertEqual(sum(result["realizedAllocation"]), 100)

    def test_pirate_proposal_must_allocate_every_coin(self) -> None:
        created = self.service.create_session("pirates")
        with self.assertRaises(ValueError):
            self.service.act(
                created["sessionId"],
                "submit_proposal",
                {"allocation": [90, 0, 1, 0, 1]},
            )

    def test_worm_miss_updates_public_information_set(self) -> None:
        created = self.service.create_session("worm", {"seed": 0})
        state = self.service.act(created["sessionId"], "check_hole", {"holeId": 2})
        if state["phase"] == "playing":
            self.assertNotIn(1, state["possiblePositions"])
            self.assertEqual(state["turn"], 1)


if __name__ == "__main__":
    unittest.main()
