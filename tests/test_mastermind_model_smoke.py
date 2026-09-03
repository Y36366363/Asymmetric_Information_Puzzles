import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from aip.benchmark import (
    FROZEN_MASTERMIND_SMOKE_PROTOCOL_SHA256,
    FROZEN_MASTERMIND_SMOKE_PROTOCOL_V1,
    BudgetedCompletionBackend,
    CompletionRequest,
    CompletionResponse,
    ExperimentBudgetExceeded,
    PromptCondition,
    make_mastermind_completion_pair,
    verify_frozen_smoke_protocol,
)
from scripts.run_mastermind_model_smoke import analyze_report, prepare_plan


class FakeBackend:
    provider_name = "fake"
    is_real_model = False

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        return CompletionResponse("{}", request.model, total_tokens=7)


class MastermindModelSmokeTests(unittest.TestCase):
    def test_frozen_protocol_hash_and_pre_api_plan_are_reproducible(self) -> None:
        verify_frozen_smoke_protocol()
        self.assertEqual(
            FROZEN_MASTERMIND_SMOKE_PROTOCOL_V1.sha256(),
            FROZEN_MASTERMIND_SMOKE_PROTOCOL_SHA256,
        )
        with tempfile.TemporaryDirectory() as directory:
            first = prepare_plan(Path(directory) / "plan.json")
            second = prepare_plan(Path(directory) / "plan-2.json")
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "prepared_before_api_calls")

    def test_protocol_drift_is_rejected(self) -> None:
        drifted = replace(FROZEN_MASTERMIND_SMOKE_PROTOCOL_V1, max_provider_calls=95)
        with self.assertRaisesRegex(ValueError, "protocol drifted"):
            verify_frozen_smoke_protocol(drifted)

    def test_budget_stops_before_an_extra_provider_call(self) -> None:
        backend = BudgetedCompletionBackend(
            FakeBackend(), max_provider_calls=1, reported_token_stop_threshold=100
        )
        request = CompletionRequest(
            "model", PromptCondition.GENERIC, "instructions", "input"
        )
        backend.complete(request)
        with self.assertRaisesRegex(ExperimentBudgetExceeded, "call budget"):
            backend.complete(request)
        self.assertEqual(backend.provider_calls, 1)

    def test_pair_changes_only_cross_game_material_not_target_advice(self) -> None:
        backend = FakeBackend()
        pair = make_mastermind_completion_pair(backend, "model")
        self.assertIs(pair.generic.backend, pair.cross_game.backend)
        self.assertNotEqual(pair.generic.instructions, pair.cross_game.instructions)
        self.assertFalse(pair.generic.agent_metadata()["usesCrossGameExperience"])
        self.assertTrue(pair.cross_game.agent_metadata()["usesCrossGameExperience"])
        self.assertFalse(pair.cross_game.agent_metadata()["usesGameSpecificKnowledge"])

    def test_analysis_does_not_promote_tiny_smoke_to_transfer_claim(self) -> None:
        trials = []
        for model in ("gpt-5.6-luna", "gpt-5.6-terra"):
            for condition in ("generic", "cross_game_experience"):
                for repeat in range(2):
                    trials.append(
                        {
                            "condition": condition,
                            "status": "completed",
                            "result": {"solved": True, "attempts": 6},
                            "meanHeuristicAgreement": 0.5,
                            "beliefOutputRate": 0.5,
                            "meanBeliefBrier": 0.4,
                            "telemetry": {"attempts": []},
                            "repeat": repeat,
                            "requestedModel": model,
                        }
                    )
        analysis = analyze_report({"trials": trials})
        self.assertTrue(analysis["reliabilityGatePassed"])
        self.assertFalse(analysis["transferGainClaimed"])


if __name__ == "__main__":
    unittest.main()
