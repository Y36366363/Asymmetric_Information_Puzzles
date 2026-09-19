"""Focused cross-algorithm audit for Love Letter and one-die Liar's Dice."""

from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter

from aip.core import (
    CFRGameProperties,
    CFRResult,
    ExternalSamplingCFRTrainer,
    create_regret_minimization_trainer,
    run_independent_evaluation,
    strategy_profile_fingerprint,
)
from aip.puzzles.liars_dice import (
    OneDieLiarDiceCFRGame,
    OneDieLiarIndependentEvaluator,
    certify_one_die_liar_cfr,
    load_one_die_liar_policy,
    one_die_liar_evaluation,
    required_one_die_information_sets,
    solve_one_die_liar_exact,
    train_one_die_liar_cfr,
)
from aip.puzzles.love_letter import (
    LoveLetterCFRGame,
    LoveLetterIndependentEvaluator,
    certify_love_letter_subgame,
    complete_information_set_actions,
    love_letter_subgame_evaluation,
)


ROOT = Path(__file__).resolve().parents[1]
FULL_TREE_ALGORITHMS = ("vanilla_cfr", "cfr_plus", "dcfr")
CHECKPOINTS = (10, 100, 300)


class ReorderedGame:
    """Same game with reversed enumeration, used to detect update-order leaks."""

    def __init__(self, game, *, reverse_chance=False, reverse_actions=False):
        self.game = game
        self.reverse_chance = reverse_chance
        self.reverse_actions = reverse_actions

    def __getattr__(self, name):
        return getattr(self.game, name)

    def chance_outcomes(self, state):
        outcomes = self.game.chance_outcomes(state)
        return tuple(reversed(outcomes)) if self.reverse_chance else outcomes

    def legal_actions(self, state):
        actions = self.game.legal_actions(state)
        return tuple(reversed(actions)) if self.reverse_actions else actions


def compact_report(report):
    return {
        "expected_value_to_player_0": report.expected_value_to_player_0,
        "best_response_player_0": report.best_response_player_0,
        "best_response_player_1": report.best_response_player_1,
        "player_0_deviation_gain": report.player_0_deviation_gain,
        "player_1_deviation_gain": report.player_1_deviation_gain,
        "nash_conv": report.nash_conv,
        "exploitability": report.exploitability,
        "maximum_unilateral_deviation_gain": (
            report.maximum_unilateral_deviation_gain
        ),
        "profile_fingerprint": report.profile_fingerprint,
        "passed": report.passed,
        "failures": list(report.failures),
    }


def as_result(policy):
    return CFRResult(
        iterations=0,
        policy=policy,
        information_set_visits={key: 0 for key in policy},
        average_positive_regret=(0.0, 0.0),
    )


def uniform_policy(game):
    if isinstance(game, LoveLetterCFRGame):
        tables = complete_information_set_actions(game)
    else:
        tables = {}

        def visit(state):
            if game.is_terminal(state):
                return
            player = game.current_player(state)
            if player is None:
                for action, _ in game.chance_outcomes(state):
                    visit(game.next_state(state, action))
                return
            actions = game.legal_actions(state)
            tables[(player, game.information_set(state))] = actions
            for action in actions:
                visit(game.next_state(state, action))

        visit(game.initial_state())
    return {
        key: {action: 1 / len(actions) for action in actions}
        for key, actions in tables.items()
    }


def profile_maximum_difference(first, second):
    if set(first) != set(second):
        return float("inf")
    difference = 0.0
    for key, distribution in first.items():
        if set(distribution) != set(second[key]):
            return float("inf")
        difference = max(
            difference,
            *(abs(value - second[key][action])
              for action, value in distribution.items()),
        )
    return difference


def convergence(game_factory, evaluator_factory):
    output = {}
    for algorithm_id in FULL_TREE_ALGORITHMS:
        trainer = create_regret_minimization_trainer(game_factory(), algorithm_id)
        points = []
        previous = 0
        started = perf_counter()
        for checkpoint in CHECKPOINTS:
            result = trainer.train(checkpoint - previous)
            report = run_independent_evaluation(
                evaluator_factory(game_factory()), result.policy,
                maximum_exploitability=1_000_000.0,
            )
            points.append({
                "iteration": checkpoint,
                "elapsed_seconds": perf_counter() - started,
                **compact_report(report),
            })
            previous = checkpoint
        output[algorithm_id] = {
            "algorithm": result.algorithm.to_artifact(),
            "trace": points,
        }
    return output


def enumeration_invariance(game_factory):
    output = {}
    for algorithm_id in FULL_TREE_ALGORITHMS:
        baseline = create_regret_minimization_trainer(
            game_factory(), algorithm_id
        ).train(25).policy
        reversed_chance = create_regret_minimization_trainer(
            ReorderedGame(game_factory(), reverse_chance=True), algorithm_id
        ).train(25).policy
        reversed_actions = create_regret_minimization_trainer(
            ReorderedGame(game_factory(), reverse_actions=True), algorithm_id
        ).train(25).policy
        output[algorithm_id] = {
            "chance_order_maximum_policy_difference": profile_maximum_difference(
                baseline, reversed_chance
            ),
            "action_order_maximum_policy_difference": profile_maximum_difference(
                baseline, reversed_actions
            ),
        }
    return output


def exact_section(game, evaluator, form, solution, legacy_evaluation):
    independent = run_independent_evaluation(
        evaluator, solution.policy, maximum_exploitability=1e-10
    )
    legacy = legacy_evaluation(as_result(solution.policy))
    legacy_metrics = legacy.to_report()
    independent_metrics = {
        key: getattr(independent, key) for key in legacy_metrics
    }
    return {
        "tree_audit": form.audit.to_artifact(),
        "sequence_counts": [len(value) for value in form.player_sequences],
        "payoff_nonzeros": len(form.payoff_matrix.entries),
        "backend": solution.backend,
        "primal_dual_gap": solution.primal_dual_gap,
        "maximum_flow_residual": solution.maximum_flow_residual,
        "independent_evaluation": compact_report(independent),
        "legacy_oracle_metrics": legacy_metrics,
        "maximum_oracle_metric_difference": max(
            abs(legacy_metrics[key] - independent_metrics[key])
            for key in legacy_metrics
        ),
    }


def sampled_section():
    love_game = LoveLetterCFRGame.late_round_subgame()
    started = perf_counter()
    love_external = ExternalSamplingCFRTrainer(
        love_game, seed=20260912
    ).train(20_000)
    love_seconds = perf_counter() - started
    love_gate = certify_love_letter_subgame(love_game, love_external)

    started = perf_counter()
    liar_root = train_one_die_liar_cfr(20_000, seed=20260908)
    liar_root_seconds = perf_counter() - started
    liar_gate = certify_one_die_liar_cfr(liar_root)
    frozen = load_one_die_liar_policy(
        ROOT / "src/aip/puzzles/liars_dice/one_die_cfr_policy.json"
    )

    started = perf_counter()
    liar_external = ExternalSamplingCFRTrainer(
        OneDieLiarDiceCFRGame(), seed=20260919
    ).train(20_000)
    liar_external_seconds = perf_counter() - started
    required = required_one_die_information_sets()
    missing = required - set(liar_external.policy)
    try:
        liar_external_report = run_independent_evaluation(
            OneDieLiarIndependentEvaluator(), liar_external.policy,
            maximum_exploitability=0.01,
        )
    except ValueError as error:
        liar_external_evidence = {
            "coverage_complete": False,
            "information_sets": len(liar_external.policy),
            "required_information_sets": len(required),
            "missing_information_sets": len(missing),
            "independent_evaluator_rejected": True,
            "rejection": str(error),
            "passed": False,
        }
    else:
        liar_external_evidence = {
            "coverage_complete": not missing,
            "information_sets": len(liar_external.policy),
            "required_information_sets": len(required),
            "missing_information_sets": len(missing),
            "independent_evaluator_rejected": False,
            **compact_report(liar_external_report),
        }
    return {
        "love_letter_external_sampling": {
            "algorithm": love_external.algorithm.to_artifact(),
            "elapsed_seconds": love_seconds,
            "gate_passed": love_gate.passed,
            "failures": list(love_gate.failures),
            **love_gate.evaluation.to_report(),
        },
        "liar_root_chance_sampling": {
            "algorithm": liar_root.algorithm.to_artifact(),
            "elapsed_seconds": liar_root_seconds,
            "gate_passed": liar_gate.passed,
            "failures": list(liar_gate.failures),
            "matches_frozen_runtime_fingerprint": (
                strategy_profile_fingerprint(liar_root.policy)
                == strategy_profile_fingerprint(frozen.policy)
            ),
            **liar_gate.evaluation.to_report(),
        },
        "liar_external_sampling": {
            "algorithm": liar_external.algorithm.to_artifact(),
            "elapsed_seconds": liar_external_seconds,
            **liar_external_evidence,
        },
    }


def main():
    properties = CFRGameProperties(2, True, True, True)
    love_game = LoveLetterCFRGame.late_round_subgame()
    from aip.core import compile_sequence_form, solve_sequence_form

    love_form = compile_sequence_form(
        love_game, game_properties=properties, sparse=True
    )
    love_solution = solve_sequence_form(love_form, backend="scipy_highs")
    liar_form, liar_solution = solve_one_die_liar_exact()

    love_uniform = run_independent_evaluation(
        LoveLetterIndependentEvaluator(love_game), uniform_policy(love_game),
        maximum_exploitability=0.0,
    )
    liar_game = OneDieLiarDiceCFRGame()
    liar_uniform = run_independent_evaluation(
        OneDieLiarIndependentEvaluator(), uniform_policy(liar_game),
        maximum_exploitability=0.0,
    )
    progress = json.loads((
        ROOT / "research/results/love_letter_local_progress_2026-09-17.json"
    ).read_text())
    latest_progress = progress["chunks"][-1]

    artifact = {
        "date": "2026-09-19",
        "scope": ["love_letter", "one_die_stepwise_liars_dice"],
        "certification_contract": {
            "exploitability_source": "independent_best_response_only",
            "training_regret_is_not_exploitability": True,
            "web_runtime_modified": False,
        },
        "love_letter": {
            "exact_four_card_subgame": exact_section(
                love_game,
                LoveLetterIndependentEvaluator(love_game),
                love_form,
                love_solution,
                lambda result: love_letter_subgame_evaluation(love_game, result),
            ),
            "uniform_negative_control": compact_report(love_uniform),
            "deterministic_convergence": convergence(
                LoveLetterCFRGame.late_round_subgame,
                lambda game: LoveLetterIndependentEvaluator(game),
            ),
            "enumeration_invariance": enumeration_invariance(
                LoveLetterCFRGame.late_round_subgame
            ),
            "full_round_checkpoint": latest_progress,
            "full_round_certified": False,
        },
        "one_die_liars_dice": {
            "exact_game": exact_section(
                liar_game,
                OneDieLiarIndependentEvaluator(),
                liar_form,
                liar_solution,
                one_die_liar_evaluation,
            ),
            "uniform_negative_control": compact_report(liar_uniform),
            "deterministic_convergence": convergence(
                OneDieLiarDiceCFRGame,
                lambda game: OneDieLiarIndependentEvaluator(),
            ),
            "enumeration_invariance": enumeration_invariance(
                OneDieLiarDiceCFRGame
            ),
        },
        "sampling": sampled_section(),
        "method_conclusions": {
            "love_letter_four_card_subgame": (
                "sequence-form LP is the primary oracle; DCFR and MCCFR are cross-checks"
            ),
            "love_letter_full_round": (
                "remain uncertified until the structural frontier closes and a complete "
                "candidate passes independent best response"
            ),
            "one_die_liars_dice": (
                "exact sequence-form dominates approximate CFR for release; deterministic "
                "DCFR is a strong cross-check and 20k external sampling lacks coverage"
            ),
        },
    }

    exact_sections = (
        artifact["love_letter"]["exact_four_card_subgame"],
        artifact["one_die_liars_dice"]["exact_game"],
    )
    invariance_sections = (
        artifact["love_letter"]["enumeration_invariance"],
        artifact["one_die_liars_dice"]["enumeration_invariance"],
    )
    convergence_sections = (
        artifact["love_letter"]["deterministic_convergence"],
        artifact["one_die_liars_dice"]["deterministic_convergence"],
    )
    artifact["passed"] = (
        all(section["independent_evaluation"]["passed"] for section in exact_sections)
        and all(section["maximum_oracle_metric_difference"] <= 1e-10
                for section in exact_sections)
        and all(
            metric <= 1e-12
            for section in invariance_sections
            for result in section.values()
            for metric in result.values()
        )
        and all(
            result["trace"][-1]["exploitability"]
            < result["trace"][0]["exploitability"]
            for section in convergence_sections
            for result in section.values()
        )
        and all(
            game["uniform_negative_control"]["exploitability"] > 0
            for game in (artifact["love_letter"], artifact["one_die_liars_dice"])
        )
        and artifact["sampling"]["love_letter_external_sampling"]["gate_passed"]
        and artifact["sampling"]["liar_root_chance_sampling"]["gate_passed"]
        and artifact["sampling"]["liar_root_chance_sampling"][
            "matches_frozen_runtime_fingerprint"
        ]
        and (
            artifact["sampling"]["liar_external_sampling"]["passed"]
            or (
                not artifact["sampling"]["liar_external_sampling"][
                    "coverage_complete"
                ]
                and artifact["sampling"]["liar_external_sampling"][
                    "independent_evaluator_rejected"
                ]
            )
        )
        and not artifact["love_letter"]["full_round_certified"]
    )
    destination = (
        ROOT / "research/results/love_letter_liar_algorithm_audit_2026-09-19.json"
    )
    destination.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "artifact": str(destination),
        "passed": artifact["passed"],
        "love_letter_exact": artifact["love_letter"]["exact_four_card_subgame"][
            "independent_evaluation"
        ],
        "liar_exact": artifact["one_die_liars_dice"]["exact_game"][
            "independent_evaluation"
        ],
        "sampling": artifact["sampling"],
    }, indent=2, sort_keys=True))
    if not artifact["passed"]:
        raise SystemExit("focused algorithm audit failed")


if __name__ == "__main__":
    main()
