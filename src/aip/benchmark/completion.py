"""Completion-backed strategic agents with retry and usage telemetry."""

from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Mapping, Protocol

from aip.benchmark.types import (
    AgentDecision,
    AgentInput,
    BeliefOutput,
    validate_decision,
)


GENERIC_STRATEGIC_PROMPT = """You are a general strategic-reasoning agent.
Use only the supplied observation, information state, public history, rules, and
legal actions. Never infer a hidden state from episode identifiers. Choose one
legal action. Report an honest confidence from 0 to 1 and, when meaningful, a
normalized belief over the adapter's state labels. Encode the selected action's
payload as JSON text in payload_json, using "{}" when the action has no payload.
Return only the required JSON object, with no explanation or private reasoning
text.
"""

GUESS_WHO_STRATEGY_PROMPT = """For this Guess Who environment, treat the
remaining candidates as a uniform posterior after truthful public answers.
Prefer the legal yes/no question with the most even split of remaining public
candidate profiles. When one candidate remains, choose its final-guess action.
"""

DECISION_JSON_SCHEMA: Mapping[str, object] = {
    "type": "object",
    "properties": {
        "action_id": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "payload_json": {
            "type": "string",
            "description": "JSON object for the chosen action payload; use {} when empty.",
        },
        "belief": {
            "anyOf": [
                {"type": "null"},
                {
                    "type": "object",
                    "properties": {
                        "target": {"type": "string"},
                        "probabilities": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "state": {"type": "string"},
                                    "probability": {
                                        "type": "number",
                                        "minimum": 0,
                                        "maximum": 1,
                                    },
                                },
                                "required": ["state", "probability"],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "required": ["target", "probabilities"],
                    "additionalProperties": False,
                },
            ]
        },
    },
    "required": ["action_id", "confidence", "payload_json", "belief"],
    "additionalProperties": False,
}

BELIEF_NORMALIZATION_TOLERANCE = 0.02


class PromptCondition(str, Enum):
    GENERIC = "generic"
    SINGLE_GAME = "single_game_prompted"
    CROSS_GAME_EXPERIENCE = "cross_game_experience"


@dataclass(frozen=True, slots=True)
class CompletionRequest:
    model: str
    condition: PromptCondition
    instructions: str
    input_text: str
    response_schema: Mapping[str, object] = field(
        default_factory=lambda: DECISION_JSON_SCHEMA
    )


@dataclass(frozen=True, slots=True)
class CompletionResponse:
    output_text: str
    resolved_model: str
    response_id: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    def __post_init__(self) -> None:
        if min(self.input_tokens, self.output_tokens, self.total_tokens) < 0:
            raise ValueError("token counts cannot be negative")


class CompletionBackend(Protocol):
    provider_name: str
    is_real_model: bool

    def complete(self, request: CompletionRequest) -> CompletionResponse: ...


@dataclass(frozen=True, slots=True)
class CompletionAttempt:
    attempt: int
    outcome: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    resolved_model: str | None
    response_id: str | None
    output_sha256: str | None
    output_characters: int
    raw_belief_probability_sum: float | None = None
    belief_normalized: bool = False
    error_type: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class CompletionTelemetry:
    condition: PromptCondition
    provider: str
    requested_model: str
    attempts: tuple[CompletionAttempt, ...]
    final_confidence: float | None

    @property
    def retry_count(self) -> int:
        return max(0, len(self.attempts) - 1)

    @property
    def parse_failure_count(self) -> int:
        return sum(attempt.outcome == "parse_error" for attempt in self.attempts)

    @property
    def validation_failure_count(self) -> int:
        return sum(attempt.outcome == "validation_error" for attempt in self.attempts)

    @property
    def transport_failure_count(self) -> int:
        return sum(attempt.outcome == "transport_error" for attempt in self.attempts)

    @property
    def total_latency_ms(self) -> float:
        return sum(attempt.latency_ms for attempt in self.attempts)

    @property
    def input_tokens(self) -> int:
        return sum(attempt.input_tokens for attempt in self.attempts)

    @property
    def output_tokens(self) -> int:
        return sum(attempt.output_tokens for attempt in self.attempts)

    @property
    def total_tokens(self) -> int:
        return sum(attempt.total_tokens for attempt in self.attempts)

    def as_dict(self) -> dict[str, object]:
        return {
            "condition": self.condition.value,
            "provider": self.provider,
            "requestedModel": self.requested_model,
            "attempts": [asdict(attempt) for attempt in self.attempts],
            "retryCount": self.retry_count,
            "parseFailureCount": self.parse_failure_count,
            "validationFailureCount": self.validation_failure_count,
            "transportFailureCount": self.transport_failure_count,
            "totalLatencyMs": self.total_latency_ms,
            "inputTokens": self.input_tokens,
            "outputTokens": self.output_tokens,
            "totalTokens": self.total_tokens,
            "finalConfidence": self.final_confidence,
        }


class CompletionAgentError(RuntimeError):
    """Raised after all attempts fail, retaining audit telemetry."""

    def __init__(self, message: str, telemetry: CompletionTelemetry) -> None:
        super().__init__(message)
        self.telemetry = telemetry


def _safe_error(error: Exception) -> str:
    text = " ".join(str(error).split())
    return text[:240] or error.__class__.__name__


def _response_fingerprint(output_text: str) -> str:
    return hashlib.sha256(output_text.encode("utf-8")).hexdigest()


def load_dotenv_value(path: str | Path, key: str) -> str | None:
    """Read one literal dotenv value without executing shell syntax or expansion."""

    if not key or "=" in key:
        raise ValueError("dotenv key must be a nonempty variable name")
    source = Path(path)
    if not source.is_file():
        return None
    found: str | None = None
    for raw_line in source.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.removeprefix("export ").split("=", 1)
        if name.strip() != key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        found = value
    return found or None


def _public_agent_input(decision: AgentInput) -> dict[str, object]:
    return {
        "environment_id": decision.environment_id,
        "step": decision.step,
        "observation": dict(decision.observation),
        "information_state": dict(decision.information_state),
        "legal_actions": [asdict(action) for action in decision.legal_actions],
        "action_history": [asdict(event) for event in decision.action_history],
        "natural_language_rules": decision.natural_language_rules,
    }


def _validate_adapter_belief(decision_input: AgentInput, chosen: AgentDecision) -> None:
    if chosen.belief is None:
        return
    target = decision_input.information_state.get("beliefTarget")
    if isinstance(target, str) and chosen.belief.target != target:
        raise ValueError(f"belief target must be {target}")
    labels = decision_input.information_state.get("beliefStateLabels")
    if isinstance(labels, (list, tuple)):
        allowed = {str(label) for label in labels}
        unknown = set(chosen.belief.probabilities).difference(allowed)
        if unknown:
            raise ValueError(f"belief contains unknown state labels: {sorted(unknown)}")


def parse_completion_decision(output_text: str) -> AgentDecision:
    """Parse the narrow structured-output shape without accepting extra fields."""

    return _parse_completion_decision(output_text).decision


@dataclass(frozen=True, slots=True)
class _ParsedDecision:
    decision: AgentDecision
    raw_belief_probability_sum: float | None
    belief_normalized: bool


def _parse_completion_decision(output_text: str) -> _ParsedDecision:

    payload = json.loads(output_text)
    if not isinstance(payload, dict):
        raise ValueError("completion output must be a JSON object")
    expected = {"action_id", "confidence", "payload_json", "belief"}
    if set(payload) != expected:
        raise ValueError(
            "completion output must contain exactly action_id, confidence, "
            "payload_json, belief"
        )
    action_id = payload["action_id"]
    confidence = payload["confidence"]
    if not isinstance(action_id, str):
        raise ValueError("action_id must be a string")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise ValueError("confidence must be numeric")
    payload_json = payload["payload_json"]
    if not isinstance(payload_json, str):
        raise ValueError("payload_json must be a string")
    action_payload = json.loads(payload_json)
    if not isinstance(action_payload, dict):
        raise ValueError("payload_json must encode a JSON object")
    belief_payload = payload["belief"]
    belief = None
    raw_sum = None
    normalized = False
    if belief_payload is not None:
        if not isinstance(belief_payload, dict) or set(belief_payload) != {
            "target",
            "probabilities",
        }:
            raise ValueError("belief must contain exactly target and probabilities")
        entries = belief_payload["probabilities"]
        target = belief_payload["target"]
        if not isinstance(target, str):
            raise ValueError("belief target must be a string")
        if not isinstance(entries, list) or not entries:
            raise ValueError("belief probabilities must be a nonempty array")
        probabilities: dict[str, float] = {}
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {"state", "probability"}:
                raise ValueError("each belief entry needs state and probability")
            state = entry["state"]
            probability = entry["probability"]
            if not isinstance(state, str):
                raise ValueError("belief state must be a string")
            if state in probabilities:
                raise ValueError(f"duplicate belief state: {state}")
            if isinstance(probability, bool) or not isinstance(probability, (int, float)):
                raise ValueError("belief probability must be numeric")
            probability = float(probability)
            if not math.isfinite(probability) or not 0 <= probability <= 1:
                raise ValueError("belief probability must be between 0 and 1")
            probabilities[state] = probability
        raw_sum = sum(probabilities.values())
        deviation = abs(raw_sum - 1.0)
        if deviation > BELIEF_NORMALIZATION_TOLERANCE:
            raise ValueError(
                f"belief probabilities sum to {raw_sum:.12g}; maximum accepted "
                f"rounding deviation is {BELIEF_NORMALIZATION_TOLERANCE}"
            )
        if deviation > 1e-9:
            probabilities = {
                state: probability / raw_sum
                for state, probability in probabilities.items()
            }
            normalized = True
        belief = BeliefOutput(target, probabilities)
    return _ParsedDecision(
        AgentDecision(
            action_id,
            float(confidence),
            payload=action_payload,
            belief=belief,
        ),
        raw_sum,
        normalized,
    )


class CompletionBackedAgent:
    """Turn one completion backend into an auditable strategic agent."""

    def __init__(
        self,
        backend: CompletionBackend,
        model: str,
        condition: PromptCondition,
        *,
        condition_prompt: str = "",
        max_attempts: int = 3,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        if not model:
            raise ValueError("model cannot be empty")
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        self.backend = backend
        self.model = model
        self.condition = condition
        self.condition_prompt = condition_prompt.strip()
        self.max_attempts = max_attempts
        self._clock = clock
        self._last_telemetry: CompletionTelemetry | None = None
        self._telemetry_history: list[CompletionTelemetry] = []

    @property
    def instructions(self) -> str:
        if not self.condition_prompt:
            return GENERIC_STRATEGIC_PROMPT
        return f"{GENERIC_STRATEGIC_PROMPT}\n{self.condition_prompt}\n"

    def agent_metadata(self) -> dict[str, object]:
        metadata = {
            "condition": self.condition.value,
            "completionBacked": True,
            "provider": self.backend.provider_name,
            "requestedModel": self.model,
            "isLlm": self.backend.is_real_model,
            "isRealModel": self.backend.is_real_model,
            "claimLevel": (
                "exploratory_llm_behavior"
                if self.backend.is_real_model
                else "test_double"
            ),
            "usesGameSpecificKnowledge": self.condition is PromptCondition.SINGLE_GAME,
            "usesCrossGameExperience": (
                self.condition is PromptCondition.CROSS_GAME_EXPERIENCE
            ),
            "promptSha256": hashlib.sha256(
                self.instructions.encode("utf-8")
            ).hexdigest(),
        }
        backend_metadata = getattr(self.backend, "metadata", None)
        if callable(backend_metadata):
            metadata["backendConfiguration"] = dict(backend_metadata())
        return metadata

    def decision_telemetry(self) -> Mapping[str, object]:
        return self._last_telemetry.as_dict() if self._last_telemetry else {}

    @property
    def telemetry_history(self) -> tuple[CompletionTelemetry, ...]:
        return tuple(self._telemetry_history)

    def choose_action(self, decision: AgentInput) -> AgentDecision:
        attempts: list[CompletionAttempt] = []
        correction = ""
        for attempt_number in range(1, self.max_attempts + 1):
            input_text = json.dumps(
                _public_agent_input(decision), sort_keys=True, separators=(",", ":")
            )
            if correction:
                input_text += "\nCorrection required: " + correction
            request = CompletionRequest(
                self.model,
                self.condition,
                self.instructions,
                input_text,
            )
            started = self._clock()
            try:
                response = self.backend.complete(request)
            except Exception as error:
                latency_ms = (self._clock() - started) * 1000
                attempts.append(
                    CompletionAttempt(
                        attempt=attempt_number,
                        outcome="transport_error",
                        latency_ms=latency_ms,
                        input_tokens=0,
                        output_tokens=0,
                        total_tokens=0,
                        resolved_model=None,
                        response_id=None,
                        output_sha256=None,
                        output_characters=0,
                        error_type=error.__class__.__name__,
                        error_message=_safe_error(error),
                    )
                )
                correction = "The previous request failed. Produce the required JSON."
                continue

            latency_ms = (self._clock() - started) * 1000
            common = {
                "attempt": attempt_number,
                "latency_ms": latency_ms,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "total_tokens": response.total_tokens,
                "resolved_model": response.resolved_model,
                "response_id": response.response_id,
                "output_sha256": _response_fingerprint(response.output_text),
                "output_characters": len(response.output_text),
            }
            try:
                parsed = _parse_completion_decision(response.output_text)
                chosen = parsed.decision
            except json.JSONDecodeError as error:
                attempts.append(
                    CompletionAttempt(
                        outcome="parse_error",
                        error_type=error.__class__.__name__,
                        error_message=_safe_error(error),
                        **common,
                    )
                )
                correction = "The previous output was not valid JSON."
                continue
            except (TypeError, ValueError) as error:
                attempts.append(
                    CompletionAttempt(
                        outcome="validation_error",
                        error_type=error.__class__.__name__,
                        error_message=_safe_error(error),
                        **common,
                    )
                )
                correction = (
                    "The previous JSON did not match the required schema: "
                    + _safe_error(error)
                )
                continue

            try:
                validate_decision(decision, chosen)
                _validate_adapter_belief(decision, chosen)
            except ValueError as error:
                attempts.append(
                    CompletionAttempt(
                        outcome="validation_error",
                        error_type=error.__class__.__name__,
                        error_message=_safe_error(error),
                        raw_belief_probability_sum=parsed.raw_belief_probability_sum,
                        belief_normalized=parsed.belief_normalized,
                        **common,
                    )
                )
                correction = (
                    "The previous action was illegal for the supplied state: "
                    + _safe_error(error)
                )
                continue

            attempts.append(
                CompletionAttempt(
                    outcome="success",
                    raw_belief_probability_sum=parsed.raw_belief_probability_sum,
                    belief_normalized=parsed.belief_normalized,
                    **common,
                )
            )
            self._last_telemetry = CompletionTelemetry(
                self.condition,
                self.backend.provider_name,
                self.model,
                tuple(attempts),
                chosen.confidence,
            )
            self._telemetry_history.append(self._last_telemetry)
            return chosen

        self._last_telemetry = CompletionTelemetry(
            self.condition,
            self.backend.provider_name,
            self.model,
            tuple(attempts),
            None,
        )
        self._telemetry_history.append(self._last_telemetry)
        raise CompletionAgentError(
            f"completion agent failed after {self.max_attempts} attempts",
            self._last_telemetry,
        )


@dataclass(frozen=True, slots=True)
class CompletionAgentPair:
    generic: CompletionBackedAgent
    single_game: CompletionBackedAgent

    def __post_init__(self) -> None:
        if self.generic.backend is not self.single_game.backend:
            raise ValueError("paired conditions must share the same backend instance")
        if self.generic.model != self.single_game.model:
            raise ValueError("paired conditions must request the same model")


def make_guess_who_completion_pair(
    backend: CompletionBackend,
    model: str,
    *,
    max_attempts: int = 3,
) -> CompletionAgentPair:
    return CompletionAgentPair(
        CompletionBackedAgent(
            backend,
            model,
            PromptCondition.GENERIC,
            max_attempts=max_attempts,
        ),
        CompletionBackedAgent(
            backend,
            model,
            PromptCondition.SINGLE_GAME,
            condition_prompt=GUESS_WHO_STRATEGY_PROMPT,
            max_attempts=max_attempts,
        ),
    )


def _field(value: object, name: str, default: object = None) -> object:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


class OpenAIResponsesBackend:
    """Optional real-model backend using the official OpenAI Python SDK."""

    provider_name = "openai-responses"
    is_real_model = True

    def __init__(
        self,
        client: object | None = None,
        *,
        reasoning_effort: str = "low",
        max_output_tokens: int = 4096,
        **client_options: object,
    ) -> None:
        if not reasoning_effort:
            raise ValueError("reasoning_effort cannot be empty")
        if max_output_tokens < 1:
            raise ValueError("max_output_tokens must be positive")
        if client is None:
            try:
                from openai import OpenAI
            except ImportError as error:
                raise RuntimeError(
                    "Install AIP with the 'llm' extra to use OpenAIResponsesBackend"
                ) from error
            client = OpenAI(**client_options)
        self.client = client
        self.reasoning_effort = reasoning_effort
        self.max_output_tokens = max_output_tokens

    def metadata(self) -> Mapping[str, object]:
        return {
            "reasoningEffort": self.reasoning_effort,
            "maxOutputTokens": self.max_output_tokens,
            "store": False,
            "structuredOutputs": True,
        }

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        responses = getattr(self.client, "responses")
        response = responses.create(
            model=request.model,
            instructions=request.instructions,
            input=request.input_text,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "aip_agent_decision",
                    "strict": True,
                    "schema": request.response_schema,
                }
            },
            reasoning={"effort": self.reasoning_effort},
            max_output_tokens=self.max_output_tokens,
            store=False,
        )
        usage = _field(response, "usage", {})
        return CompletionResponse(
            output_text=str(_field(response, "output_text", "")),
            resolved_model=str(_field(response, "model", request.model)),
            response_id=(
                str(response_id)
                if (response_id := _field(response, "id")) is not None
                else None
            ),
            input_tokens=int(_field(usage, "input_tokens", 0) or 0),
            output_tokens=int(_field(usage, "output_tokens", 0) or 0),
            total_tokens=int(_field(usage, "total_tokens", 0) or 0),
        )
