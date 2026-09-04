"""Frozen real-model smoke protocol and auditable experiment budget."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Callable, Mapping

from aip.benchmark.completion import (
    CompletionBackend,
    CompletionRequest,
    CompletionResponse,
)
from aip.benchmark.mastermind import FROZEN_TRANSFER_MANIFEST_V1


@dataclass(frozen=True, slots=True)
class MastermindSmokeProtocol:
    protocol_id: str = "aip-mastermind-heldout-smoke-v1"
    model_ids: tuple[str, str] = ("gpt-5.6-luna", "gpt-5.6-terra")
    conditions: tuple[str, str] = ("generic", "cross_game_experience")
    repeats: int = 2
    secret: str = "8062"
    reasoning_effort: str = "low"
    max_attempts_per_decision: int = 2
    max_output_tokens_per_request: int = 2048
    max_provider_calls: int = 96
    reported_token_stop_threshold: int = 250_000

    def __post_init__(self) -> None:
        if len(set(self.model_ids)) != 2 or len(set(self.conditions)) != 2:
            raise ValueError("smoke protocol requires two distinct models and conditions")
        if self.repeats != 2:
            raise ValueError("v1 smoke protocol is frozen to exactly two repeats")
        if min(
            self.max_attempts_per_decision,
            self.max_output_tokens_per_request,
            self.max_provider_calls,
            self.reported_token_stop_threshold,
        ) < 1:
            raise ValueError("budget and retry limits must be positive")

    @property
    def planned_episodes(self) -> int:
        return len(self.model_ids) * len(self.conditions) * self.repeats

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["model_ids"] = list(self.model_ids)
        payload["conditions"] = list(self.conditions)
        payload["planned_episodes"] = self.planned_episodes
        payload["frozen_transfer_manifest"] = dict(FROZEN_TRANSFER_MANIFEST_V1)
        payload["token_threshold_semantics"] = (
            "Stop before the next provider call after cumulative API-reported "
            "tokens reach the threshold; one completed response may cross it."
        )
        return payload

    def sha256(self) -> str:
        encoded = json.dumps(
            self.as_dict(), sort_keys=True, separators=(",", ":")
        ).encode()
        return hashlib.sha256(encoded).hexdigest()


FROZEN_MASTERMIND_SMOKE_PROTOCOL_V1 = MastermindSmokeProtocol()
FROZEN_MASTERMIND_SMOKE_PROTOCOL_SHA256 = (
    "0c989df2e45d2f21c156d35d36997de18b225763f47acea5a50ebab9b619fa6f"
)


@dataclass(frozen=True, slots=True)
class MastermindCeilingDiagnosticProtocol:
    protocol_id: str = "aip-mastermind-output-ceiling-diagnostic-v1"
    model_ids: tuple[str, str] = ("gpt-5.6-luna", "gpt-5.6-terra")
    conditions: tuple[str, str] = ("generic", "cross_game_experience")
    repeats: int = 1
    secret: str = "8062"
    reasoning_effort: str = "low"
    max_attempts_per_decision: int = 2
    max_output_tokens_per_request: int = 8192
    max_provider_calls: int = 48
    reported_token_stop_threshold: int = 250_000
    changed_from_smoke_v1: str = "max_output_tokens_per_request_only"

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["model_ids"] = list(self.model_ids)
        payload["conditions"] = list(self.conditions)
        payload["planned_episodes"] = (
            len(self.model_ids) * len(self.conditions) * self.repeats
        )
        payload["frozen_transfer_manifest"] = dict(FROZEN_TRANSFER_MANIFEST_V1)
        return payload

    def sha256(self) -> str:
        encoded = json.dumps(
            self.as_dict(), sort_keys=True, separators=(",", ":")
        ).encode()
        return hashlib.sha256(encoded).hexdigest()


FROZEN_MASTERMIND_CEILING_DIAGNOSTIC_V1 = MastermindCeilingDiagnosticProtocol()
FROZEN_MASTERMIND_CEILING_DIAGNOSTIC_SHA256 = (
    "04b4f4197d3630c0ef400d46276ce43ce8526ddbb1af036fed09e11c8ffbb8ee"
)


class ExperimentBudgetExceeded(RuntimeError):
    pass


class BudgetedCompletionBackend:
    """Share one provider-call and reported-token stop budget across all trials."""

    def __init__(
        self,
        backend: CompletionBackend,
        *,
        max_provider_calls: int,
        reported_token_stop_threshold: int,
        initial_provider_calls: int = 0,
        initial_reported_tokens: int = 0,
        initial_input_tokens: int = 0,
        initial_output_tokens: int = 0,
        on_usage: Callable[[Mapping[str, object]], None] | None = None,
    ) -> None:
        initial_values = (
            initial_provider_calls,
            initial_reported_tokens,
            initial_input_tokens,
            initial_output_tokens,
        )
        if min(initial_values) < 0:
            raise ValueError("initial budget usage cannot be negative")
        if initial_provider_calls > max_provider_calls:
            raise ValueError("initial provider calls exceed the call budget")
        self.backend = backend
        self.provider_name = backend.provider_name
        self.is_real_model = backend.is_real_model
        self.max_provider_calls = max_provider_calls
        self.reported_token_stop_threshold = reported_token_stop_threshold
        self.provider_calls = initial_provider_calls
        self.reported_tokens = initial_reported_tokens
        self.input_tokens = initial_input_tokens
        self.output_tokens = initial_output_tokens
        self.stopped = False
        self.on_usage = on_usage

    def _check(self) -> None:
        if self.provider_calls >= self.max_provider_calls:
            self.stopped = True
            raise ExperimentBudgetExceeded("provider-call budget exhausted")
        if self.reported_tokens >= self.reported_token_stop_threshold:
            self.stopped = True
            raise ExperimentBudgetExceeded("reported-token stop threshold reached")

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        self._check()
        self.provider_calls += 1
        self._publish_usage()
        response = self.backend.complete(request)
        self.reported_tokens += response.total_tokens
        self.input_tokens += response.input_tokens
        self.output_tokens += response.output_tokens
        self._publish_usage()
        return response

    def _publish_usage(self) -> None:
        if self.on_usage is not None:
            self.on_usage(self.usage())

    def metadata(self) -> Mapping[str, object]:
        backend_metadata = getattr(self.backend, "metadata", None)
        metadata = dict(backend_metadata()) if callable(backend_metadata) else {}
        metadata.update(
            {
                "maxProviderCalls": self.max_provider_calls,
                "reportedTokenStopThreshold": self.reported_token_stop_threshold,
            }
        )
        return metadata

    def usage(self) -> dict[str, object]:
        return {
            "providerCalls": self.provider_calls,
            "reportedTokens": self.reported_tokens,
            "inputTokens": self.input_tokens,
            "outputTokens": self.output_tokens,
            "stopped": self.stopped,
            "providerCallsRemaining": max(
                0, self.max_provider_calls - self.provider_calls
            ),
        }


def verify_frozen_smoke_protocol(
    protocol: MastermindSmokeProtocol = FROZEN_MASTERMIND_SMOKE_PROTOCOL_V1,
) -> None:
    actual = protocol.sha256()
    if actual != FROZEN_MASTERMIND_SMOKE_PROTOCOL_SHA256:
        raise ValueError(
            "Mastermind smoke protocol drifted: "
            f"expected {FROZEN_MASTERMIND_SMOKE_PROTOCOL_SHA256}, got {actual}"
        )


def verify_frozen_ceiling_diagnostic(
    protocol: MastermindCeilingDiagnosticProtocol = (
        FROZEN_MASTERMIND_CEILING_DIAGNOSTIC_V1
    ),
) -> None:
    actual = protocol.sha256()
    if actual != FROZEN_MASTERMIND_CEILING_DIAGNOSTIC_SHA256:
        raise ValueError(
            "Mastermind ceiling diagnostic drifted: "
            f"expected {FROZEN_MASTERMIND_CEILING_DIAGNOSTIC_SHA256}, got {actual}"
        )
