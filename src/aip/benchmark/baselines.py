"""Small, honest baseline agents that do not depend on any game implementation."""

from __future__ import annotations

import hashlib

from aip.benchmark.types import AgentDecision, AgentInput


class GenericWeakRandomAgent:
    """Choose uniformly from legal actions using a stable per-state hash.

    This baseline reads no rules, observations, history, or game-specific state.
    It is intentionally weak, stateless, reproducible, and valid for every AIP
    adapter. It does not emit a belief because it cannot know the adapter's
    hidden-state labels.
    """

    def __init__(self, seed: int | str = 0) -> None:
        self.seed = str(seed)

    def choose_action(self, decision: AgentInput) -> AgentDecision:
        fingerprint = "|".join(
            (
                self.seed,
                decision.environment_id,
                str(decision.step),
                *(action.action_id for action in decision.legal_actions),
            )
        )
        digest = hashlib.sha256(fingerprint.encode("utf-8")).digest()
        index = int.from_bytes(digest[:8], "big") % len(decision.legal_actions)
        return AgentDecision(
            action_id=decision.legal_actions[index].action_id,
            confidence=1 / len(decision.legal_actions),
        )


GENERIC_WEAK_METADATA = {
    "condition": "generic_weak",
    "policyClass": "seeded_uniform_legal_action",
    "isLlm": False,
    "claimLevel": "exploratory_baseline",
    "usesGameSpecificKnowledge": False,
}
