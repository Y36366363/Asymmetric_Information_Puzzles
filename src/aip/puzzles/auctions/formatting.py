from __future__ import annotations

from aip.puzzles.auctions.models import AuctionAnalysis


def format_analysis(analysis: AuctionAnalysis) -> str:
    rules = analysis.rules
    benchmark = analysis.benchmark
    lines = [
        f"Repeated all-pay auction: {rules.player_count} players, {rules.rounds} rounds, "
        f"prize={rules.prize_value}, initial budget={rules.initial_budget}",
        "All bids are lost; highest positive bid wins the prize; tied highs are random.",
        "",
        "Fully rational one-shot continuous symmetric benchmark (budgets nonbinding):",
        f"  bid distribution: {benchmark.bid_cdf}",
        f"  expected bid/player={benchmark.expected_bid_per_player:.2f}",
        f"  expected total bids={benchmark.expected_total_bids:.2f}",
        f"  expected winning bid={benchmark.expected_winning_bid:.2f}",
        f"  expected net payoff/player={benchmark.expected_payoff_per_player:.2f}",
        f"  price-only rotating convention needs discount/continuation >= "
        f"{analysis.tacit_patience_threshold:.4f} in the worst rotation position",
        f"  majority exclusion convention needs discount/continuation >= "
        f"{analysis.social_patience_threshold:.4f}",
        f"  101-style leadership signal net cost={analysis.leadership_signal_net_cost:.2f}; "
        f"cooperative expected flow/player/round={analysis.cooperative_payoff_per_round:.2f}",
        "",
        "Finite-budget simulation averages:",
        "  mode         auctioneer revenue  final group wealth  richest share  bankrupt  expelled",
    ]
    for summary in analysis.scenarios:
        survival = (
            f"; tacit norm survives={summary.coordination_survival_rate:.2%}"
            if summary.coordination_survival_rate is not None
            else ""
        )
        lines.append(
            f"  {summary.mode.value:11s} {summary.mean_auctioneer_revenue:18.2f} "
            f"{summary.mean_final_group_wealth:19.2f} "
            f"{summary.mean_richest_share:13.2%} {summary.mean_bankrupt_players:9.2f} "
            f"{summary.mean_expelled_players:9.2f}"
            + survival
        )
    lines.extend(
        [
            "",
            "Interpretation:",
            "  naive: noisy bids, including possible bids above the 100-value prize",
            "  cautious: frequent abstention and bids capped near value/player-count",
            "  equilibrium: one-shot mixed-equilibrium draws, then truncated by budgets",
            "  cooperative: rotating winner bids 1; efficient but not self-enforcing",
            "  tacit: price 1 means cooperate; price >1 publicly triggers equilibrium punishment",
            "  social: a >V costly signal proposes the norm; an observable majority expels defectors",
            "  Finite budgets/rounds make the exact dynamic equilibrium state-dependent.",
        ]
    )
    return "\n".join(lines)
