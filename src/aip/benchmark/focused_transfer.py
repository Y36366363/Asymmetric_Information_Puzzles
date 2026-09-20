"""Frozen, paired cross-game decision probes with exact target-game scoring."""

from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import asdict
from pathlib import Path
from statistics import mean
from typing import Mapping

from aip.benchmark.guess_who import ASK_PREFIX, GuessWhoBenchmarkAdapter, OptimalGuessWhoAgent


ARMS = ("no_memory", "same_game", "surface_experience", "abstract_memory")
SECRETS = ("Ada", "Hugo", "Nico", "Talia")
DEPTHS = (1, 2)
SEED = 20260920
MEMORY_CHARACTERS = 690

_MEMORIES = {
    "no_memory": (
        "No earlier game records, advice, or examples are available. Use only the "
        "current public state and legal actions."
    ),
    "same_game": (
        "Earlier Guess Who practice: after truthful yes/no answers, retain only "
        "consistent names and keep their probabilities equal. For each legal question, "
        "count yes and no among remaining profiles. Choose a near-even split; "
        "then repeat with the updated candidates. This target-game advice is a "
        "supervised positive control, not cross-game transfer."
    ),
    "surface_experience": (
        "Earlier play records: a four-card Love Letter contest involved private "
        "hands, a draw, a card play and a final comparison. A one-die Liar's Dice "
        "contest involved private die faces, bids and a challenge. Both used "
        "turn-taking and a hidden random deal. These are surface descriptions of "
        "source games, with no recommendation for this new game."
    ),
    "abstract_memory": (
        "Lessons from hidden-card and hidden-die games: maintain a probability "
        "distribution over hidden states consistent with public observations; "
        "update it after new evidence. Evaluate an information-gathering action "
        "by its possible observations and the quality of later decisions, not by "
        "its label. Opponent modeling and bluff thresholds matter only when an "
        "opponent can act strategically; do not invent one in a truthful environment."
    ),
}


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: object) -> str:
    payload = value if isinstance(value, str) else canonical_json(value)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def memory_prompt(arm: str) -> str:
    if arm not in ARMS:
        raise ValueError(f"unknown memory arm: {arm}")
    head = f"Prior-memory condition: {arm}.\n{_MEMORIES[arm]}\n"
    tail = "\nEnd of prior-memory block."
    gap = MEMORY_CHARACTERS - len(head) - len(tail)
    if gap < 0:
        raise ValueError("memory block exceeds fixed character budget")
    return head + ("." * gap) + tail


def probe_adapter(secret: str, depth: int) -> GuessWhoBenchmarkAdapter:
    if secret not in SECRETS or depth not in DEPTHS:
        raise ValueError("probe is outside the frozen target panel")
    adapter = GuessWhoBenchmarkAdapter(
        secret, episode_id="guess-who:held-out-transfer", include_rules=True
    )
    oracle = OptimalGuessWhoAgent(adapter.solver)
    for _ in range(depth):
        if adapter.terminal:
            raise ValueError("probe reached a terminal state")
        adapter.apply_decision(oracle.choose_action(adapter.decision_input()))
    if adapter.terminal or not any(
        action.action_id.startswith(ASK_PREFIX)
        for action in adapter.decision_input().legal_actions
    ):
        raise ValueError("probe must offer an information question")
    return adapter


def public_probe_fingerprint(adapter: GuessWhoBenchmarkAdapter) -> str:
    decision = adapter.decision_input()
    return digest({
        "observation": decision.observation,
        "informationState": decision.information_state,
        "legalActions": [asdict(action) for action in decision.legal_actions],
        "actionHistory": [asdict(event) for event in decision.action_history],
        "rules": decision.natural_language_rules,
    })


def failure_penalty(adapter: GuessWhoBenchmarkAdapter) -> float:
    candidate_mask, remaining_mask = adapter._masks()
    optimum = adapter.solver.exact_expected_questions(candidate_mask, remaining_mask)
    regrets = [
        adapter._question_cost(action.action_id.removeprefix(ASK_PREFIX)) - optimum
        for action in adapter.decision_input().legal_actions
        if action.action_id.startswith(ASK_PREFIX)
    ]
    return max(1.0, max(regrets))


def make_preregistration(source_paths: tuple[Path, Path]) -> dict[str, object]:
    sources = []
    for path in source_paths:
        if not path.is_file():
            raise FileNotFoundError(path)
        contents = path.read_text(encoding="utf-8")
        if json.loads(contents).get("passed") is not True:
            raise ValueError(f"source audit did not pass: {path}")
        sources.append({"path": str(path), "sha256": digest(contents)})
    probes = []
    for secret in SECRETS:
        for depth in DEPTHS:
            adapter = probe_adapter(secret, depth)
            probes.append({
                "id": f"{secret.lower()}-after-{depth}",
                "secret": secret,
                "depth": depth,
                "publicStateSha256": public_probe_fingerprint(adapter),
                "failurePenaltyTurns": failure_penalty(adapter),
            })
    cells = [(probe["id"], arm) for probe in probes for arm in ARMS]
    random.Random(SEED).shuffle(cells)
    return {
        "schemaVersion": "aip-focused-transfer-prereg-v1",
        "date": "2026-09-20",
        "sourceGames": ["love-letter-four-card-subgame", "one-die-liars-dice"],
        "targetGame": "guess-who",
        "sourceArtifacts": sources,
        "sourceScope": "Only certified small games; full Love Letter is uncertified.",
        "model": "gpt-5.6-luna",
        "reasoningEffort": "low",
        "maxOutputTokens": 4096,
        "maxAttemptsPerCell": 1,
        "maxProviderCalls": len(cells),
        "memoryBlockCharacters": MEMORY_CHARACTERS,
        "memoryPrompts": {arm: memory_prompt(arm) for arm in ARMS},
        "probes": probes,
        "cellOrder": [{"probeId": probe_id, "arm": arm} for probe_id, arm in cells],
        "primaryEndpoint": (
            "Mean exact expected-turn action regret across all eight frozen target "
            "probes, with failed or invalid completions assigned that probe's "
            "preregistered failure penalty; abstract_memory minus no_memory. "
            "Negative is beneficial."
        ),
        "secondaryEndpoints": [
            "same_game positive control", "surface_experience contrast",
            "valid response rate", "valid-only exact regret", "belief Brier score",
        ],
        "interpretationRule": (
            "Use paired probe differences and a fixed-seed 10000-resample paired "
            "bootstrap interval. Label benefit only when the entire 95% interval "
            "is below zero, harm only when entirely above zero; otherwise "
            "inconclusive. This small panel cannot establish general transfer."
        ),
        "noMemoryLeakageRule": (
            "Only same_game may mention Guess Who or target-specific solutions. "
            "Neither source-game memory arm may contain target-game names or examples."
        ),
    }


def validate_preregistration(plan: Mapping[str, object]) -> None:
    if plan.get("schemaVersion") != "aip-focused-transfer-prereg-v1":
        raise ValueError("unknown preregistration version")
    prompts = plan["memoryPrompts"]
    if set(prompts) != set(ARMS):
        raise ValueError("memory arms differ from frozen design")
    if any(prompts[arm] != memory_prompt(arm) for arm in ARMS):
        raise ValueError("memory prompt differs from frozen design")
    if any(len(prompts[arm]) != MEMORY_CHARACTERS for arm in ARMS):
        raise ValueError("memory lengths differ")
    for arm in ("surface_experience", "abstract_memory"):
        lower = prompts[arm].lower()
        if "guess who" in lower or any(name.lower() in lower for name in SECRETS):
            raise ValueError("target example leaked into source memory")
    if len(plan["probes"]) != len(SECRETS) * len(DEPTHS):
        raise ValueError("probe panel changed")
    by_id = {probe["id"]: probe for probe in plan["probes"]}
    if len(by_id) != len(plan["probes"]):
        raise ValueError("duplicate probe ID")
    for probe in plan["probes"]:
        adapter = probe_adapter(probe["secret"], probe["depth"])
        if probe["publicStateSha256"] != public_probe_fingerprint(adapter):
            raise ValueError("target state changed after preregistration")
        if not math.isclose(probe["failurePenaltyTurns"], failure_penalty(adapter)):
            raise ValueError("failure penalty changed after preregistration")
    expected_cells = {(probe_id, arm) for probe_id in by_id for arm in ARMS}
    actual_cells = [(cell["probeId"], cell["arm"]) for cell in plan["cellOrder"]]
    if len(actual_cells) != len(expected_cells) or set(actual_cells) != expected_cells:
        raise ValueError("cell schedule is not complete and unique")
    if plan["maxProviderCalls"] != len(actual_cells):
        raise ValueError("provider budget differs from cell count")


def _bootstrap_interval(differences: list[float]) -> tuple[float, float]:
    rng = random.Random(SEED)
    estimates = sorted(
        mean(rng.choices(differences, k=len(differences)))
        for _ in range(10_000)
    )
    return estimates[249], estimates[9749]


def analyze_results(plan: Mapping[str, object], rows: list[Mapping[str, object]]) -> dict[str, object]:
    validate_preregistration(plan)
    expected = {(cell["probeId"], cell["arm"]) for cell in plan["cellOrder"]}
    by_cell = {(row["probeId"], row["arm"]): row for row in rows}
    if len(by_cell) != len(rows) or set(by_cell) != expected:
        raise ValueError("incomplete or duplicate results")
    summaries = {}
    for arm in ARMS:
        arm_rows = [by_cell[(probe["id"], arm)] for probe in plan["probes"]]
        valid = [row for row in arm_rows if row["status"] == "valid"]
        summaries[arm] = {
            "meanPenalizedRegretTurns": mean(float(row["penalizedRegretTurns"]) for row in arm_rows),
            "validDecisions": len(valid),
            "meanValidRegretTurns": (
                mean(float(row["penalizedRegretTurns"]) for row in valid) if valid else None
            ),
            "meanBeliefBrier": (
                mean(float(row["beliefBrier"]) for row in valid if row.get("beliefBrier") is not None)
                if any(row.get("beliefBrier") is not None for row in valid) else None
            ),
            "totalTokens": sum(int(row["totalTokens"]) for row in arm_rows),
        }
    contrasts = {}
    for arm in ARMS[1:]:
        differences = [
            float(by_cell[(probe["id"], arm)]["penalizedRegretTurns"])
            - float(by_cell[(probe["id"], "no_memory")]["penalizedRegretTurns"])
            for probe in plan["probes"]
        ]
        lower, upper = _bootstrap_interval(differences)
        label = "benefit" if upper < 0 else "harm" if lower > 0 else "inconclusive"
        contrasts[arm] = {
            "meanDifferenceTurns": mean(differences),
            "pairedBootstrap95": [lower, upper],
            "interpretation": label,
            "probeDifferencesTurns": differences,
        }
    return {"summaries": summaries, "contrastsVersusNoMemory": contrasts}
