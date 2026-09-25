"""Held-out one-die Liar's Dice transfer probes with an exact action oracle."""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass
from statistics import mean
from typing import Hashable, Mapping

from aip.benchmark.types import ActionEvent, ActionSpec, AgentDecision, AgentInput
from aip.benchmark.value_decomposition import ValueDecomposition
from aip.puzzles.liars_dice import (
    OneDieLiarDiceCFRGame,
    OneDieLiarIndependentEvaluator,
    OneDieLiarState,
    solve_one_die_liar_exact,
)


ARMS = ("no_memory", "same_game", "surface_experience", "abstract_memory")
SEED = 20260921
REPEATS = 2
PROBE_COUNT = 12
PAD_TOKEN = " PAD"

RULES = (
    "Each player has one private six-sided die. Ones are wild for bids on faces 2-6. "
    "Player 0 opens with a quantity-one bid. Thereafter choose challenge or the one "
    "legal next bid on the fixed quantity/face ladder. A challenge wins when the last "
    "bid is false and loses when it is true. Choose from the supplied legal actions."
)


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: object) -> str:
    payload = value if isinstance(value, str) else canonical_json(value)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def action_id(action: Hashable) -> str:
    if action == "challenge":
        return "challenge"
    quantity, face = action
    return f"raise:{quantity}:{face}"


def decode_action(value: str) -> Hashable:
    if value == "challenge":
        return value
    prefix, quantity, face = value.split(":")
    if prefix != "raise":
        raise ValueError(f"unknown Liar's Dice action: {value}")
    return int(quantity), int(face)


def _opponent_reach_weights(profile, hero: int, bids: tuple[tuple[int, int], ...]):
    weights = {opponent_die: 1 / 6 for opponent_die in range(1, 7)}
    prefix: tuple[tuple[int, int], ...] = ()
    for bid in bids:
        actor = len(prefix) % 2
        if actor != hero:
            for opponent_die in weights:
                distribution = profile[(actor, (opponent_die, prefix))]
                weights[opponent_die] *= float(distribution[bid])
        prefix += (bid,)
    return weights


def opponent_reach_mass(
    profile, hero: int, bids: tuple[tuple[int, int], ...]
) -> float:
    """Return chance/opponent reach for one player's public bid history."""

    return sum(_opponent_reach_weights(profile, hero, bids).values())


def _posterior(profile, hero: int, own_die: int, bids: tuple[tuple[int, int], ...]):
    del own_die
    weights = _opponent_reach_weights(profile, hero, bids)
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("probe information set has zero opponent reach")
    return {str(die): weight / total for die, weight in weights.items()}


@dataclass(frozen=True, slots=True)
class LiarProbe:
    probe_id: str
    player: int
    own_die: int
    bids: tuple[tuple[int, int], ...]
    exact_action_values: Mapping[str, float]
    exact_posterior: Mapping[str, float]

    def decision_input(self) -> AgentInput:
        game = OneDieLiarDiceCFRGame()
        representative_dice = (
            (self.own_die, 1) if self.player == 0 else (1, self.own_die)
        )
        from aip.puzzles.liars_dice import OneDieLiarState

        state = OneDieLiarState(representative_dice, self.bids)
        if game.current_player(state) != self.player:
            raise ValueError("probe player does not match bid history")
        actions = tuple(
            ActionSpec(
                action_id(action),
                "Challenge the previous bid." if action == "challenge" else (
                    f"Raise to quantity {action[0]} on face {action[1]}."
                ),
            )
            for action in game.legal_actions(state)
        )
        history = tuple(
            ActionEvent(
                actor_id=f"player_{index % 2}",
                action_id=action_id(bid),
                public_observation={"bid": list(bid)},
            )
            for index, bid in enumerate(self.bids)
        )
        return AgentInput(
            environment_id="one-die-liars-dice-held-out",
            episode_id="one-die-liars-dice:held-out-probe",
            step=len(self.bids),
            observation={
                "kind": "decision",
                "lastBid": list(self.bids[-1]) if self.bids else None,
            },
            information_state={
                "player": self.player,
                "ownDie": self.own_die,
                "publicBids": [list(bid) for bid in self.bids],
                "beliefTarget": "opponent_die",
                "beliefStateLabels": [str(face) for face in range(1, 7)],
            },
            legal_actions=actions,
            action_history=history,
            natural_language_rules=RULES,
        )

    def evaluate(self, decision: AgentDecision) -> dict[str, object]:
        chosen = decision.action_id
        if chosen not in self.exact_action_values:
            raise ValueError("chosen action is outside exact action-value table")
        optimum = max(self.exact_action_values.values())
        regret = optimum - float(self.exact_action_values[chosen])
        belief_brier = None
        if decision.belief is not None:
            if decision.belief.target != "opponent_die":
                raise ValueError("belief target must be opponent_die")
            belief_brier = sum(
                (decision.belief.probabilities.get(face, 0.0) - probability) ** 2
                for face, probability in self.exact_posterior.items()
            )
        return {
            "actionRegret": regret,
            "optimalActionIds": sorted(
                action for action, value in self.exact_action_values.items()
                if abs(value - optimum) <= 1e-12
            ),
            "optimalPolicyAgreement": regret <= 1e-12,
            "beliefBrierToExactPosterior": belief_brier,
        }

    def to_artifact(self) -> dict[str, object]:
        return {
            "id": self.probe_id,
            "player": self.player,
            "ownDie": self.own_die,
            "bids": [list(bid) for bid in self.bids],
            "exactActionValues": dict(self.exact_action_values),
            "exactPosterior": dict(self.exact_posterior),
            "publicStateSha256": digest(asdict(self.decision_input())),
            "failurePenalty": max(2.0, max(self.exact_action_values.values()) - min(self.exact_action_values.values())),
        }


def candidate_oracle_probes() -> tuple[LiarProbe, ...]:
    """Return every reachable, discriminating probe under the exact profile."""

    _, solution = solve_one_die_liar_exact()
    values = OneDieLiarIndependentEvaluator().action_values(solution.policy)
    candidates = []
    for (player, information_set), action_values in values.items():
        own_die, bids = information_set
        if not bids or len(action_values) != 2:
            continue
        encoded = {action_id(action): float(value) for action, value in action_values.items()}
        gap = max(encoded.values()) - min(encoded.values())
        if gap < 0.25:
            continue
        candidates.append(LiarProbe(
            probe_id=(
                "liar-candidate-"
                + digest({"player": player, "ownDie": own_die, "bids": bids})[:12]
            ),
            player=player,
            own_die=own_die,
            bids=bids,
            exact_action_values=encoded,
            exact_posterior=_posterior(solution.policy, player, own_die, bids),
        ))
    return tuple(candidates)


def build_oracle_probes() -> tuple[LiarProbe, ...]:
    groups: dict[str, list[LiarProbe]] = {"challenge": [], "raise": []}
    for probe in candidate_oracle_probes():
        best = max(probe.exact_action_values, key=probe.exact_action_values.get)
        groups["challenge" if best == "challenge" else "raise"].append(probe)
    rank = lambda probe: digest({
        "seed": SEED,
        "player": probe.player,
        "ownDie": probe.own_die,
        "bids": probe.bids,
    })
    selected = sorted(groups["challenge"], key=rank)[: PROBE_COUNT // 2]
    raise_per_player = PROBE_COUNT // 4
    for player in (0, 1):
        selected.extend(sorted(
            (probe for probe in groups["raise"] if probe.player == player),
            key=rank,
        )[:raise_per_player])
    probes = []
    for index, probe in enumerate(selected, start=1):
        probes.append(LiarProbe(
            probe_id=f"liar-probe-{index:02d}",
            player=probe.player,
            own_die=probe.own_die,
            bids=probe.bids,
            exact_action_values=probe.exact_action_values,
            exact_posterior=probe.exact_posterior,
        ))
    if len(probes) != PROBE_COUNT:
        raise ValueError("insufficient balanced Liar's Dice probes")
    return tuple(probes)


def select_profile_invariant_probes(
    profiles: Mapping[str, Mapping[tuple[int, Hashable], Mapping[Hashable, float]]],
    *,
    count: int = 30,
    minimum_action_value_gap: float = 0.25,
) -> tuple[tuple[LiarProbe, ...], dict[str, object]]:
    """Select a balanced panel only where all reference profiles agree."""

    if count < 2 or count % 2:
        raise ValueError("profile-invariant panel size must be an even number >= 2")
    candidates = candidate_oracle_probes()
    audit = compare_probe_oracles(candidates, profiles)
    rows = {row["probeId"]: row for row in audit["probes"]}
    eligible = [
        probe for probe in candidates
        if rows[probe.probe_id]["profileInvariant"]
        and min(rows[probe.probe_id]["actionValueGaps"].values())
        >= minimum_action_value_gap
    ]
    groups = {"challenge": [], "raise": []}
    for probe in eligible:
        labels = next(iter(rows[probe.probe_id]["bestActionIds"].values()))
        if len(labels) != 1:
            continue
        groups["challenge" if labels[0] == "challenge" else "raise"].append(probe)
    rank = lambda probe: digest({
        "seed": SEED,
        "panel": "profile_invariant_v1",
        "probe": probe.probe_id,
    })
    per_action = count // 2
    challenge = sorted(groups["challenge"], key=rank)[:per_action]
    raise_player_one = sorted(
        (probe for probe in groups["raise"] if probe.player == 1), key=rank
    )[: min(5, per_action)]
    raise_player_zero = sorted(
        (probe for probe in groups["raise"] if probe.player == 0), key=rank
    )[: per_action - len(raise_player_one)]
    selected = challenge + raise_player_zero + raise_player_one
    if len(challenge) != per_action or len(selected) != count:
        raise ValueError("insufficient profile-invariant probes for balanced panel")
    return tuple(selected), {
        "candidateAudit": audit,
        "minimumActionValueGap": minimum_action_value_gap,
        "selectedProbeIds": [probe.probe_id for probe in selected],
        "selectedProbes": len(selected),
        "challengeOptimal": len(challenge),
        "raiseOptimal": len(raise_player_zero) + len(raise_player_one),
        "playerOneRaiseProbes": len(raise_player_one),
        "allSelectedProfileInvariant": all(
            rows[probe.probe_id]["profileInvariant"] for probe in selected
        ),
    }


def build_consensus_reference_profiles():
    """Return the three independently audited profiles used by probe gates."""

    from pathlib import Path

    from aip.core import create_regret_minimization_trainer
    from aip.puzzles.liars_dice import load_one_die_liar_policy

    _, exact = solve_one_die_liar_exact()
    frozen = load_one_die_liar_policy(
        Path(__file__).resolve().parents[1]
        / "puzzles/liars_dice/one_die_cfr_policy.json"
    )
    dcfr = create_regret_minimization_trainer(
        OneDieLiarDiceCFRGame(), "dcfr"
    ).train(300)
    return {
        "exact_sequence_form": exact.policy,
        "frozen_runtime_cfr": frozen.policy,
        "dcfr_300": dcfr.policy,
    }


def positive_control_material(
    test_panel: tuple[LiarProbe, ...],
    profiles: Mapping[str, Mapping[tuple[int, Hashable], Mapping[Hashable, float]]],
    *,
    examples_per_action: int = 8,
) -> dict[str, object]:
    """Create stratified, mechanically selected, test-disjoint examples."""

    if examples_per_action < 1:
        raise ValueError("positive control needs examples from both action classes")
    excluded = {probe.probe_id for probe in test_panel}
    candidates = tuple(
        probe for probe in candidate_oracle_probes() if probe.probe_id not in excluded
    )
    audit = compare_probe_oracles(candidates, profiles)
    rows = {row["probeId"]: row for row in audit["probes"]}
    groups = {"challenge": [], "raise": []}
    for probe in candidates:
        row = rows[probe.probe_id]
        if not row["profileInvariant"]:
            continue
        labels = next(iter(row["bestActionIds"].values()))
        if len(labels) != 1:
            continue
        groups["challenge" if labels[0] == "challenge" else "raise"].append(probe)
    rank = lambda probe: digest({
        "seed": 20260923,
        "purpose": "same_game_positive_control",
        "probe": probe.probe_id,
    })
    selected = []
    for label in ("challenge", "raise"):
        selected.extend(sorted(groups[label], key=rank)[:examples_per_action])
    if len(selected) != examples_per_action * 2:
        raise ValueError("insufficient disjoint positive-control examples")
    examples = []
    for probe in selected:
        values = probe.exact_action_values
        examples.append({
            "player": probe.player,
            "ownDie": probe.own_die,
            "publicBids": [list(bid) for bid in probe.bids],
            "legalActionValuesAgainstExactOpponent": dict(values),
            "bestAction": max(values, key=values.get),
        })
    return {
        "schemaVersion": "aip-liar-positive-control-material-v1",
        "selectionSeed": 20260923,
        "testProbeIds": sorted(excluded),
        "examples": examples,
        "exampleCount": len(examples),
        "challengeBestExamples": examples_per_action,
        "raiseBestExamples": examples_per_action,
        "testDisjoint": not excluded.intersection(probe.probe_id for probe in selected),
    }


def positive_control_prompt(material: Mapping[str, object]) -> str:
    """Build a strong target-game control from audited, disjoint records."""

    return (
        "Prior-memory condition: same_game_stratified_positive_control. The records "
        "below are exact one-die Liar's Dice decisions selected mechanically from "
        "information sets disjoint from every test state. Each value is conditional "
        "expected utility against the exact equilibrium opponent; choose the legal "
        "action with the larger value. Do not default to challenge: a bid can be "
        "plausible because of either player's die, and ones are wild only for faces "
        "2-6. Match the current player, own die, and full public bid history to the "
        "strategic pattern in these worked records.\n"
        + canonical_json(material["examples"])
    )


class ExactLiarDecisionProgram:
    """Reusable, information-set-only decision aid for manipulation controls.

    This is deliberately an oracle-assisted positive control, not a learned
    memory condition. It may establish that an agent follows a valid strategic
    signal, but it cannot by itself support a transfer or GTO claim.
    """

    program_id = "one_die_liar_exact_decision_program_v1"

    def __init__(self) -> None:
        _, solution = solve_one_die_liar_exact()
        self._policy = solution.policy
        self._values = OneDieLiarIndependentEvaluator().action_values(solution.policy)

    def advise(
        self,
        player: int,
        own_die: int,
        bids: tuple[tuple[int, int], ...],
    ) -> dict[str, object]:
        key = (player, (own_die, bids))
        if key not in self._values:
            raise ValueError("decision program received an unknown information set")
        values = {
            action_id(action): float(value)
            for action, value in self._values[key].items()
        }
        optimum = max(values.values())
        best = sorted(
            action for action, value in values.items()
            if abs(value - optimum) <= 1e-12
        )
        return {
            "programId": self.program_id,
            "player": player,
            "ownDie": own_die,
            "publicBids": [list(bid) for bid in bids],
            "actionValuesAgainstExactEquilibriumOpponent": values,
            "recommendedActionIds": best,
            "recommendationRule": "maximize conditional expected utility",
            "certificationScope": "manipulation_control_only",
        }

    def prompt_for(self, probe: LiarProbe) -> str:
        advice = self.advise(probe.player, probe.own_die, probe.bids)
        return (
            "Condition: oracle_assisted_same_game_positive_control. An audited, "
            "deterministic one-die Liar's Dice decision program has evaluated only "
            "the legal information visible in the current state. Follow its "
            "recommendedActionIds exactly. This is an instruction-following "
            "manipulation control, not a memory-transfer condition. Program output:\n"
            + canonical_json(advice)
        )


class LiarValueDecompositionOracle:
    """Exact posterior → challenge/raise values → action decomposition."""

    oracle_id = "one_die_liar_value_decomposition_v1"

    def decompose(self, probe: LiarProbe) -> ValueDecomposition:
        game = OneDieLiarDiceCFRGame()
        immediate = {action: 0.0 for action in probe.exact_action_values}
        continuation = {action: 0.0 for action in probe.exact_action_values}
        if "challenge" in probe.exact_action_values:
            challenge_value = 0.0
            for opponent_die, probability in probe.exact_posterior.items():
                dice = (
                    (probe.own_die, int(opponent_die))
                    if probe.player == 0
                    else (int(opponent_die), probe.own_die)
                )
                terminal = OneDieLiarState(
                    dice=dice,
                    bids=probe.bids,
                    challenger=probe.player,
                )
                utility = game.utility_player_zero(terminal)
                challenge_value += probability * (
                    utility if probe.player == 0 else -utility
                )
            immediate["challenge"] = challenge_value
        for action, value in probe.exact_action_values.items():
            if action != "challenge":
                continuation[action] = float(value)
        total = {
            action: immediate[action] + continuation[action]
            for action in probe.exact_action_values
        }
        optimum = max(total.values())
        chosen = sorted(
            action for action, value in total.items()
            if abs(value - optimum) <= 1e-12
        )[0]
        return ValueDecomposition(
            posterior_target="opponent_die",
            posterior=dict(probe.exact_posterior),
            immediate_action_values=immediate,
            continuation_action_values=continuation,
            total_action_values=total,
            chosen_action_id=chosen,
        )


def source_experience_records() -> dict[str, object]:
    """Generate auditable records rather than hand-written fictional episodes."""

    from aip.benchmark.guess_who import GuessWhoBenchmarkAdapter, OptimalGuessWhoAgent
    from aip.core import CFRGameProperties, compile_sequence_form, solve_sequence_form
    from aip.puzzles.love_letter import LoveLetterCFRGame

    guess_records = []
    for secret in ("Ada", "Hugo"):
        adapter = GuessWhoBenchmarkAdapter(secret, include_rules=True)
        agent = OptimalGuessWhoAgent(adapter.solver)
        before = adapter.decision_input()
        decision = agent.choose_action(before)
        result = adapter.apply_decision(decision)
        guess_records.append({
            "candidateCount": before.information_state["candidateCount"],
            "action": decision.action_id,
            "publicObservation": dict(result.outcome),
            "actionRegret": result.evaluation["actionRegret"],
        })

    game = LoveLetterCFRGame.late_round_subgame()
    form = compile_sequence_form(
        game,
        game_properties=CFRGameProperties(2, True, True, True),
        sparse=True,
    )
    solution = solve_sequence_form(form, backend="scipy_highs")
    love_records = []
    for key, distribution in sorted(solution.policy.items(), key=lambda item: repr(item[0])):
        positive = [(repr(action), probability) for action, probability in distribution.items() if probability > 1e-9]
        if not positive:
            continue
        love_records.append({
            "informationSet": repr(key),
            "positiveProbabilityActions": [
                {"action": action, "probability": probability}
                for action, probability in positive
            ],
        })
        if len(love_records) == 2:
            break
    return {
        "schemaVersion": "aip-source-experience-v1",
        "guessWhoExactEpisodes": guess_records,
        "loveLetterFourCardExactDecisions": love_records,
        "provenance": {
            "guessWho": "exact dynamic-programming oracle",
            "loveLetter": "audited sequence-form LP policy",
            "fullLoveLetterUsed": False,
        },
    }


def target_oracle_metadata() -> dict[str, object]:
    """Describe the independent target oracle used to score every probe."""

    from aip.core import run_independent_evaluation

    form, solution = solve_one_die_liar_exact()
    report = run_independent_evaluation(
        OneDieLiarIndependentEvaluator(),
        solution.policy,
        maximum_exploitability=1e-10,
    )
    return {
        "evaluatorId": report.evaluator_id,
        "evaluatorMethod": report.evaluator_method,
        "profileFingerprint": report.profile_fingerprint,
        "expectedValueToPlayer0": report.expected_value_to_player_0,
        "nashConv": report.nash_conv,
        "exploitability": report.exploitability,
        "solverBackend": solution.backend,
        "primalDualGap": solution.primal_dual_gap,
        "maximumFlowResidual": solution.maximum_flow_residual,
        "treeAudit": form.audit.to_artifact(),
    }


def compare_probe_oracles(
    probes: tuple[LiarProbe, ...],
    profiles: Mapping[str, Mapping[tuple[int, Hashable], Mapping[Hashable, float]]],
) -> dict[str, object]:
    """Check whether conditional best-action labels survive profile choice.

    A zero-sum game can have multiple equilibria with different off-path or
    conditional behavior. Probe labels intended for agent evaluation should be
    treated as profile-sensitive unless all supplied independently evaluated
    profiles select the same action.
    """

    if len(profiles) < 2:
        raise ValueError("oracle comparison requires at least two profiles")
    evaluator = OneDieLiarIndependentEvaluator()
    value_tables = {
        name: evaluator.action_values(profile) for name, profile in profiles.items()
    }
    rows = []
    for probe in probes:
        key = (probe.player, (probe.own_die, probe.bids))
        labels = {}
        gaps = {}
        for name, table in value_tables.items():
            values = table[key]
            maximum = max(values.values())
            best = sorted(
                action_id(action)
                for action, value in values.items()
                if abs(value - maximum) <= 1e-12
            )
            labels[name] = best
            gaps[name] = maximum - min(values.values())
        first = next(iter(labels.values()))
        stable = all(label == first for label in labels.values())
        rows.append({
            "probeId": probe.probe_id,
            "bestActionIds": labels,
            "actionValueGaps": gaps,
            "profileInvariant": stable,
        })
    unstable = [row["probeId"] for row in rows if not row["profileInvariant"]]
    return {
        "profiles": list(profiles),
        "probes": rows,
        "profileInvariantProbes": len(rows) - len(unstable),
        "totalProbes": len(rows),
        "unstableProbeIds": unstable,
        "allProbeLabelsInvariant": not unstable,
    }


def base_memory_prompts(probes: tuple[LiarProbe, ...]) -> dict[str, str]:
    records = source_experience_records()
    _, solution = solve_one_die_liar_exact()
    values = OneDieLiarIndependentEvaluator().action_values(solution.policy)
    excluded = {
        (probe.player, (probe.own_die, probe.bids)) for probe in probes
    }
    target_examples = []
    for key in sorted(values, key=repr):
        if key in excluded or len(values[key]) != 2:
            continue
        encoded = {action_id(action): float(value) for action, value in values[key].items()}
        if max(encoded.values()) - min(encoded.values()) < 0.25:
            continue
        player, (own_die, bids) = key
        target_examples.append({
            "player": player,
            "ownDie": own_die,
            "bids": [list(bid) for bid in bids],
            "bestAction": max(encoded, key=encoded.get),
        })
        if len(target_examples) == 4:
            break
    compact_source = canonical_json({
        "guessWhoExactEpisodes": records["guessWhoExactEpisodes"],
        "loveLetterFourCardExactDecisions": records["loveLetterFourCardExactDecisions"],
    })
    return {
        "no_memory": (
            "Prior-memory condition: no_memory. No prior records or strategic advice "
            "are supplied. Solve the current decision only from its public rules and state."
        ),
        "same_game": (
            "Prior-memory condition: same_game positive control. These exact one-die "
            "Liar's Dice training records are disjoint from the test probes:\n"
            + canonical_json(target_examples)
        ),
        "surface_experience": (
            "Prior-memory condition: surface_experience. Here are mechanically exported "
            "records from two other audited games. Treat them as records without an "
            "added cross-game lesson:\n" + compact_source
        ),
        "abstract_memory": (
            "Prior-memory condition: abstract_memory. An audit of exact records from a "
            "hidden-card game and a truthful information-acquisition game supports this "
            "domain-neutral memo: keep beliefs conditional on public observations; compare "
            "actions by expected downstream utility; distinguish evidence generated by "
            "nature from evidence generated by a strategic opponent; and challenge a claim "
            "only when its posterior failure probability and continuation value justify it. "
            f"Source-record SHA-256: {digest(records)}."
        ),
    }


def analyze_results(plan: Mapping[str, object], rows: list[Mapping[str, object]]) -> dict[str, object]:
    expected = {
        (cell["probeId"], cell["arm"], cell["repeat"])
        for cell in plan["cellOrder"]
    }
    by_cell = {(row["probeId"], row["arm"], row["repeat"]): row for row in rows}
    if len(by_cell) != len(rows) or set(by_cell) != expected:
        raise ValueError("results do not exactly cover the preregistered cells")
    probes = {probe["id"]: probe for probe in plan["probes"]}
    summaries = {}
    for arm in ARMS:
        arm_rows = [row for row in rows if row["arm"] == arm]
        valid = [row for row in arm_rows if row["status"] == "valid"]
        subgroups = {}
        for label in ("challenge_optimal", "raise_optimal"):
            subgroup = [
                row for row in arm_rows
                if (
                    max(
                        probes[row["probeId"]]["exactActionValues"],
                        key=probes[row["probeId"]]["exactActionValues"].get,
                    ) == "challenge"
                ) == (label == "challenge_optimal")
            ]
            subgroups[label] = {
                "decisions": len(subgroup),
                "meanPenalizedActionRegret": mean(
                    float(row["penalizedActionRegret"]) for row in subgroup
                ),
                "optimalActionRate": mean(
                    bool(row.get("optimalPolicyAgreement")) for row in subgroup
                ),
                "challengeSelectionRate": mean(
                    row.get("actionId") == "challenge" for row in subgroup
                ),
            }
        repeat_agreements = []
        for probe in plan["probes"]:
            actions = [
                by_cell[(probe["id"], arm, repeat)].get("actionId")
                for repeat in range(1, plan["repeats"] + 1)
            ]
            repeat_agreements.append(
                all(action is not None for action in actions)
                and len(set(actions)) == 1
            )
        summaries[arm] = {
            "meanPenalizedActionRegret": mean(float(row["penalizedActionRegret"]) for row in arm_rows),
            "optimalActionRate": mean(bool(row.get("optimalPolicyAgreement")) for row in arm_rows),
            "validDecisions": len(valid),
            "totalDecisions": len(arm_rows),
            "meanBeliefBrierToExactPosterior": (
                mean(float(row["beliefBrierToExactPosterior"]) for row in valid if row.get("beliefBrierToExactPosterior") is not None)
                if any(row.get("beliefBrierToExactPosterior") is not None for row in valid) else None
            ),
            "repeatActionAgreementRate": mean(repeat_agreements),
            "exploratorySubgroups": subgroups,
        }
    contrasts = {}
    for arm in ARMS[1:]:
        differences = []
        for probe in plan["probes"]:
            for repeat in range(1, plan["repeats"] + 1):
                differences.append(
                    float(by_cell[(probe["id"], arm, repeat)]["penalizedActionRegret"])
                    - float(by_cell[(probe["id"], "no_memory", repeat)]["penalizedActionRegret"])
                )
        rng = random.Random(SEED)
        estimates = sorted(mean(rng.choices(differences, k=len(differences))) for _ in range(10_000))
        lower, upper = estimates[249], estimates[9749]
        contrasts[arm] = {
            "meanDifference": mean(differences),
            "pairedBootstrap95": [lower, upper],
            "interpretation": "benefit" if upper < 0 else "harm" if lower > 0 else "inconclusive",
        }
    return {"summaries": summaries, "contrastsVersusNoMemory": contrasts}
