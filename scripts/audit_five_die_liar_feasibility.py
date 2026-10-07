"""Compare live arbitrary raises with a frozen five-die stepwise candidate."""

from __future__ import annotations

import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "configs/five_die_liar_stepwise_rules_v1.json"
OUTPUT = ROOT / "research/results/five_die_liar_feasibility_2026-10-07.json"


def report() -> dict[str, object]:
    rules = json.loads(RULES.read_text(encoding="utf-8"))
    players = int(rules["players"])
    dice = int(rules["dice_per_player"])
    sides = int(rules["sides"])
    total_dice = players * dice
    bids = total_dice * sides
    hand_histograms = math.comb(dice + sides - 1, dice)
    joint_histogram_outcomes = hand_histograms**players

    arbitrary_raise_bid_histories = 2**bids - 1
    arbitrary_raise_information_set_lower_bound = (
        hand_histograms * arbitrary_raise_bid_histories
    )

    opening_positions = tuple(range(sides))
    stepwise_bid_histories = sum(bids - position for position in opening_positions)
    stepwise_information_sets = hand_histograms * (1 + stepwise_bid_histories)
    stepwise_histories_with_histogram_chance = (
        1 + joint_histogram_outcomes * (1 + 2 * stepwise_bid_histories)
    )
    checks = {
        "two_player_zero_sum": players == 2 and rules["payoff"]["zero_sum"],
        "lossless_private_histograms": hand_histograms == 252,
        "complete_bid_ladder": bids == 60,
        "stepwise_reduction_is_material": (
            stepwise_bid_histories < arbitrary_raise_bid_histories
            and stepwise_information_sets < arbitrary_raise_information_set_lower_bound
        ),
        "runtime_boundary_is_fail_closed": (
            rules["scope_boundary"][
                "separate_from_live_five_die_arbitrary_raise_mode"
            ]
            and rules["scope_boundary"][
                "no_runtime_epsilon_gto_until_independent_gate"
            ]
        ),
        "independent_gate_required": rules["solver_route"][
            "promotion_requires_independent_exploitability"
        ],
    }
    return {
        "rules_id": rules["rules_id"],
        "rules_contract": str(RULES.relative_to(ROOT)),
        "live_arbitrary_raise_mode": {
            "bid_ladder_size": bids,
            "nonempty_public_bid_histories": arbitrary_raise_bid_histories,
            "information_set_lower_bound_from_private_histogram_and_public_history": arbitrary_raise_information_set_lower_bound,
            "full_tree_route": "reject_as_intractable_for_current_tabular_exact_pipeline",
        },
        "stepwise_candidate": {
            "private_hand_histograms_per_player": hand_histograms,
            "joint_histogram_chance_outcomes": joint_histogram_outcomes,
            "bid_ladder_size": bids,
            "allowed_opening_positions": list(opening_positions),
            "public_bid_histories": stepwise_bid_histories,
            "information_sets_including_preopening": stepwise_information_sets,
            "estimated_complete_histories_with_histogram_chance": stepwise_histories_with_histogram_chance,
            "solver_route": rules["solver_route"],
            "next_milestone": "implement_adapter_then_run_bounded_resumable_structural_audit_before_training",
        },
        "decision": {
            "live_mode": "retain_heuristic_and_do_not_claim_gto",
            "new_stepwise_variant": "continue_as_separately_scoped_adapter",
            "reason": "the stepwise contract reduces the public history family from exponential subsets to 345 chains while preserving all 252 private five-die histograms",
        },
        "checks": checks,
        "passed": all(checks.values()),
    }


def main() -> int:
    artifact = report()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(artifact, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(OUTPUT)
    return 0 if artifact["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
