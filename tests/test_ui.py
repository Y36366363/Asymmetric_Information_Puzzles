import unittest
import json
import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

from aip.ui.registry import LocalGameService, build_default_registry
from aip.ui.server import AIPRequestHandler


class LocalGameUITests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = LocalGameService(build_default_registry())

    def test_lobby_lists_one_playable_game_and_future_games(self) -> None:
        games = self.service.games()
        playable = [game["id"] for game in games if game["available"]]
        self.assertEqual(playable, ["cases", "worm"])
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

    def test_worm_position_is_hidden_while_playing(self) -> None:
        created = self.service.create_session("worm", {"seed": 5})
        state = created["state"]
        self.assertEqual(state["phase"], "playing")
        self.assertFalse(any(hole["worm"] for hole in state["holes"]))
        self.assertNotIn("seed", state)

    def test_guaranteed_worm_sequence_catches_random_movement(self) -> None:
        for seed in range(30):
            created = self.service.create_session("worm", {"seed": seed})
            session_id = created["sessionId"]
            state = created["state"]
            for hole_id in state["strategy"]:
                state = self.service.act(
                    session_id, "check_hole", {"holeId": hole_id}
                )
                if state["phase"] == "finished":
                    break
            self.assertEqual(state["phase"], "finished", f"seed={seed}")
            self.assertTrue(any(hole["worm"] for hole in state["holes"]))
            self.assertIsNone(state["suggestedHole"])

    def test_worm_miss_updates_public_information_set(self) -> None:
        created = self.service.create_session("worm", {"seed": 0})
        state = self.service.act(created["sessionId"], "check_hole", {"holeId": 2})
        if state["phase"] == "playing":
            self.assertNotIn(1, state["possiblePositions"])
            self.assertEqual(state["turn"], 1)


if __name__ == "__main__":
    unittest.main()
