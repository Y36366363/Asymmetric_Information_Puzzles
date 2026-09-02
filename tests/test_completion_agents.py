import json
import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace

from aip.benchmark import (
    CompletionAgentError,
    CompletionBackedAgent,
    CompletionRequest,
    CompletionResponse,
    GuessWhoBenchmarkAdapter,
    OpenAIResponsesBackend,
    PromptCondition,
    make_guess_who_completion_pair,
    load_dotenv_value,
    run_episode,
    parse_completion_decision,
)


def valid_output(action_id: str, confidence: float = 0.7) -> str:
    return json.dumps(
        {
            "action_id": action_id,
            "confidence": confidence,
            "payload_json": "{}",
            "belief": None,
        }
    )


class FakeBackend:
    provider_name = "fake-completion"
    is_real_model = False

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests: list[CompletionRequest] = []

    def complete(self, request):
        self.requests.append(request)
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class IncrementingClock:
    def __init__(self, step=0.01):
        self.value = 0.0
        self.step = step

    def __call__(self):
        self.value += self.step
        return self.value


class AdaptiveBackend:
    provider_name = "adaptive-fake"
    is_real_model = False

    def complete(self, request):
        public_input = json.loads(request.input_text.splitlines()[0])
        action_id = public_input["legal_actions"][0]["action_id"]
        return CompletionResponse(
            valid_output(action_id, 0.42),
            request.model,
            "resp-adaptive",
            10,
            4,
            14,
        )


class CompletionAgentTests(unittest.TestCase):
    def setUp(self):
        self.decision_input = GuessWhoBenchmarkAdapter(
            "Ada", include_rules=True
        ).decision_input()
        self.legal_action = self.decision_input.legal_actions[0].action_id

    def response(self, text, *, input_tokens=10, output_tokens=3):
        return CompletionResponse(
            text,
            "same-model-snapshot",
            "resp-test",
            input_tokens,
            output_tokens,
            input_tokens + output_tokens,
        )

    def test_pair_shares_backend_and_model_but_changes_only_prompt_condition(self):
        backend = FakeBackend(
            [self.response(valid_output(self.legal_action)) for _ in range(2)]
        )
        pair = make_guess_who_completion_pair(backend, "same-model-snapshot")
        pair.generic.choose_action(self.decision_input)
        pair.single_game.choose_action(self.decision_input)
        self.assertIs(pair.generic.backend, pair.single_game.backend)
        self.assertEqual(
            {request.model for request in backend.requests}, {"same-model-snapshot"}
        )
        self.assertEqual(
            [request.condition for request in backend.requests],
            [PromptCondition.GENERIC, PromptCondition.SINGLE_GAME],
        )
        self.assertNotEqual(
            backend.requests[0].instructions, backend.requests[1].instructions
        )

    def test_parse_failure_retries_and_accumulates_tokens_latency_and_confidence(self):
        backend = FakeBackend(
            [
                self.response("not-json", input_tokens=11, output_tokens=2),
                self.response(
                    valid_output(self.legal_action, 0.63),
                    input_tokens=13,
                    output_tokens=4,
                ),
            ]
        )
        agent = CompletionBackedAgent(
            backend,
            "same-model-snapshot",
            PromptCondition.GENERIC,
            clock=IncrementingClock(),
        )
        decision = agent.choose_action(self.decision_input)
        telemetry = agent.decision_telemetry()
        self.assertEqual(decision.confidence, 0.63)
        self.assertEqual(telemetry["retryCount"], 1)
        self.assertEqual(telemetry["parseFailureCount"], 1)
        self.assertEqual(telemetry["validationFailureCount"], 0)
        self.assertEqual(telemetry["inputTokens"], 24)
        self.assertEqual(telemetry["outputTokens"], 6)
        self.assertEqual(telemetry["totalTokens"], 30)
        self.assertAlmostEqual(telemetry["totalLatencyMs"], 20.0)
        self.assertEqual(telemetry["finalConfidence"], 0.63)
        self.assertNotIn("not-json", json.dumps(telemetry))

    def test_illegal_action_and_transport_error_are_separate_retry_classes(self):
        backend = FakeBackend(
            [
                RuntimeError("temporary transport failure"),
                self.response(valid_output("illegal-action")),
                self.response(valid_output(self.legal_action)),
            ]
        )
        agent = CompletionBackedAgent(
            backend,
            "same-model-snapshot",
            PromptCondition.GENERIC,
            max_attempts=3,
        )
        agent.choose_action(self.decision_input)
        telemetry = agent.decision_telemetry()
        self.assertEqual(telemetry["retryCount"], 2)
        self.assertEqual(telemetry["transportFailureCount"], 1)
        self.assertEqual(telemetry["validationFailureCount"], 1)
        self.assertEqual(
            [attempt["outcome"] for attempt in telemetry["attempts"]],
            ["transport_error", "validation_error", "success"],
        )

    def test_wrong_adapter_belief_target_retries_before_environment_transition(self):
        wrong_target = json.dumps(
            {
                "action_id": self.legal_action,
                "confidence": 0.8,
                "payload_json": "{}",
                "belief": {
                    "target": "hidden_character",
                    "probabilities": [
                        {"state": "Ada", "probability": 1.0}
                    ],
                },
            }
        )
        backend = FakeBackend(
            [self.response(wrong_target), self.response(valid_output(self.legal_action))]
        )
        agent = CompletionBackedAgent(
            backend,
            "same-model-snapshot",
            PromptCondition.GENERIC,
            max_attempts=2,
        )
        agent.choose_action(self.decision_input)
        telemetry = agent.decision_telemetry()
        self.assertEqual(telemetry["validationFailureCount"], 1)
        self.assertEqual(telemetry["retryCount"], 1)
        self.assertIn("belief target must be secret_character", backend.requests[1].input_text)

    def test_exhausted_retries_raise_with_complete_telemetry(self):
        backend = FakeBackend([self.response("{"), self.response("also bad")])
        agent = CompletionBackedAgent(
            backend,
            "same-model-snapshot",
            PromptCondition.GENERIC,
            max_attempts=2,
        )
        with self.assertRaises(CompletionAgentError) as raised:
            agent.choose_action(self.decision_input)
        self.assertEqual(raised.exception.telemetry.retry_count, 1)
        self.assertEqual(raised.exception.telemetry.parse_failure_count, 2)
        self.assertIsNone(raised.exception.telemetry.final_confidence)
        self.assertEqual(agent.telemetry_history, (raised.exception.telemetry,))

    def test_episode_trace_records_operational_telemetry_per_decision(self):
        backend = AdaptiveBackend()
        agent = CompletionBackedAgent(
            backend, "same-model-snapshot", PromptCondition.GENERIC
        )
        trace = run_episode(
            GuessWhoBenchmarkAdapter("Ada", include_rules=True),
            agent,
            agent_id="completion:generic",
            agent_metadata=agent.agent_metadata(),
        )
        self.assertTrue(trace.result["solved"])
        self.assertTrue(all(step.agent_telemetry for step in trace.steps))
        self.assertTrue(
            all(step.agent_telemetry["finalConfidence"] == 0.42 for step in trace.steps)
        )
        payload = json.loads(trace.to_json())
        self.assertEqual(
            payload["steps"][0]["agentTelemetry"]["totalTokens"], 14
        )
        self.assertFalse(payload["agentMetadata"]["isRealModel"])

    def test_openai_backend_uses_strict_schema_and_reads_usage(self):
        calls = []

        class Responses:
            def create(self, **kwargs):
                calls.append(kwargs)
                return SimpleNamespace(
                    output_text=valid_output(self_outer.legal_action),
                    model="resolved-model",
                    id="resp-real-shape",
                    usage=SimpleNamespace(
                        input_tokens=21, output_tokens=5, total_tokens=26
                    ),
                )

        self_outer = self
        backend = OpenAIResponsesBackend(
            client=SimpleNamespace(responses=Responses())
        )
        response = backend.complete(
            CompletionRequest(
                "requested-model",
                PromptCondition.GENERIC,
                "instructions",
                "input",
            )
        )
        self.assertEqual(response.total_tokens, 26)
        self.assertEqual(response.resolved_model, "resolved-model")
        self.assertFalse(calls[0]["store"])
        self.assertEqual(calls[0]["reasoning"], {"effort": "low"})
        self.assertEqual(calls[0]["max_output_tokens"], 4096)
        output_format = calls[0]["text"]["format"]
        self.assertEqual(output_format["type"], "json_schema")
        self.assertTrue(output_format["strict"])

    def test_dotenv_loader_reads_only_literal_requested_value(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(
                "OTHER=$(echo should-not-run)\n"
                "OPENAI_API_KEY='first'\n"
                "export OPENAI_API_KEY=second\n",
                encoding="utf-8",
            )
            self.assertEqual(load_dotenv_value(path, "OPENAI_API_KEY"), "second")
            self.assertEqual(
                load_dotenv_value(path, "OTHER"), "$(echo should-not-run)"
            )
            self.assertIsNone(load_dotenv_value(path, "MISSING"))

    def test_small_belief_rounding_error_is_normalized_but_large_error_rejected(self):
        rounded = json.dumps(
            {
                "action_id": self.legal_action,
                "confidence": 0.7,
                "payload_json": "{}",
                "belief": {
                    "target": "secret_character",
                    "probabilities": [
                        {"state": "Ada", "probability": 0.33},
                        {"state": "Bruno", "probability": 0.33},
                        {"state": "Cleo", "probability": 0.33},
                    ],
                },
            }
        )
        parsed = parse_completion_decision(rounded)
        self.assertAlmostEqual(sum(parsed.belief.probabilities.values()), 1.0)
        badly_scaled = rounded.replace("0.33", "0.2")
        with self.assertRaisesRegex(ValueError, "maximum accepted rounding"):
            parse_completion_decision(badly_scaled)

    def test_payload_json_supports_game_specific_actions_without_changing_trace_shape(self):
        output = json.dumps(
            {
                "action_id": "submit_guess",
                "confidence": 0.75,
                "payload_json": '{"guess":"0123"}',
                "belief": None,
            }
        )
        decision = parse_completion_decision(output)
        self.assertEqual(decision.payload, {"guess": "0123"})
        malformed = json.dumps(
            {
                "action_id": "submit_guess",
                "confidence": 0.75,
                "payload_json": "[]",
                "belief": None,
            }
        )
        with self.assertRaisesRegex(ValueError, "must encode a JSON object"):
            parse_completion_decision(malformed)


if __name__ == "__main__":
    unittest.main()
