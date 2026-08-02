import unittest

from aip.ui.registry import LocalGameService, build_default_registry


class LocalGameUITests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = LocalGameService(build_default_registry())

    def test_lobby_lists_one_playable_game_and_future_games(self) -> None:
        games = self.service.games()
        playable = [game["id"] for game in games if game["available"]]
        self.assertEqual(playable, ["cases"])
        self.assertIn("liars-dice", [game["id"] for game in games])

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
        self.assertEqual(
            len([case for case in state["cases"] if case["status"] == "opened"]), 25
        )

    def test_illegal_action_is_rejected(self) -> None:
        created = self.service.create_session("cases", {"seed": 19})
        with self.assertRaises(ValueError):
            self.service.act(created["sessionId"], "deal")


if __name__ == "__main__":
    unittest.main()
