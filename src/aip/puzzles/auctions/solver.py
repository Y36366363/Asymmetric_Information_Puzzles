"""Theory benchmarks and bounded-rational simulations for all-pay auctions."""

from __future__ import annotations

import random

from aip.puzzles.auctions.models import (
    AuctionAnalysis,
    AuctionMode,
    AuctionRound,
    AuctionRules,
    AuctionRun,
    EquilibriumBenchmark,
    ScenarioSummary,
)


class AllPayAuctionSimulator:
    """Simulate sealed, simultaneous, integer all-pay bids.

    Every bid is paid. The highest positive bid wins the reusable prize value;
    ties are resolved uniformly. A zero bid means abstention. Modes are
    behavioral models, not claims that budget-truncated play is an exact dynamic
    Nash equilibrium.
    """

    def run(
        self,
        rules: AuctionRules,
        mode: AuctionMode | str,
        *,
        seed: int | None = None,
    ) -> AuctionRun:
        behavior = AuctionMode(mode)
        rng = random.Random(seed)
        budgets = [rules.initial_budget] * rules.player_count
        rounds: list[AuctionRound] = []
        total_revenue = 0

        for round_number in range(1, rules.rounds + 1):
            before = tuple(budgets)
            bids = self._bids(rules, behavior, budgets, round_number, rng)
            max_bid = max(bids)
            if max_bid == 0:
                winner = None
            else:
                leaders = [player for player, bid in enumerate(bids) if bid == max_bid]
                winner = rng.choice(leaders)
            for player, bid in enumerate(bids):
                budgets[player] -= bid
            if winner is not None:
                budgets[winner] += rules.prize_value
            revenue = sum(bids)
            total_revenue += revenue
            rounds.append(
                AuctionRound(
                    round_number,
                    before,
                    tuple(bids),
                    winner,
                    tuple(budgets),
                    revenue,
                )
            )
        return AuctionRun(rules, behavior, tuple(rounds), tuple(budgets), total_revenue)

    def _bids(
        self,
        rules: AuctionRules,
        mode: AuctionMode,
        budgets: list[int],
        round_number: int,
        rng: random.Random,
    ) -> list[int]:
        active = sum(budget > 0 for budget in budgets)
        if mode is AuctionMode.COOPERATIVE:
            bids = [0] * rules.player_count
            for offset in range(rules.player_count):
                designated = (round_number - 1 + offset) % rules.player_count
                if budgets[designated] > 0:
                    bids[designated] = 1
                    break
            return bids

        bids: list[int] = []
        for budget in budgets:
            if budget == 0:
                bids.append(0)
                continue
            if mode is AuctionMode.NAIVE:
                if rng.random() < 0.08:
                    bids.append(0)
                else:
                    ceiling = min(budget, int(rules.prize_value * 1.5))
                    bids.append(rng.randint(1, ceiling))
            elif mode is AuctionMode.CAUTIOUS:
                if rng.random() < 0.35:
                    bids.append(0)
                else:
                    ceiling = min(budget, max(1, rules.prize_value // max(active, 1)))
                    bids.append(rng.randint(1, ceiling))
            else:
                # Inverse of F(b)=(b/V)^(1/(m-1)) for the continuous,
                # symmetric, equal-value one-shot equilibrium.
                raw = rules.prize_value * rng.random() ** max(active - 1, 1)
                bids.append(min(budget, max(1, round(raw))))
        return bids


class AllPayAuctionAnalyzer:
    def __init__(self) -> None:
        self.simulator = AllPayAuctionSimulator()

    @staticmethod
    def symmetric_benchmark(player_count: int, prize_value: float = 100) -> EquilibriumBenchmark:
        if player_count < 2 or prize_value <= 0:
            raise ValueError("benchmark needs at least two players and a positive prize")
        return EquilibriumBenchmark(
            player_count=player_count,
            prize_value=prize_value,
            expected_bid_per_player=prize_value / player_count,
            expected_total_bids=prize_value,
            expected_winning_bid=prize_value * player_count / (2 * player_count - 1),
            expected_payoff_per_player=0.0,
            bid_cdf=f"F(b)=(b/{prize_value:g})^(1/{player_count - 1}), 0<=b<={prize_value:g}",
        )

    def analyze(
        self,
        rules: AuctionRules,
        *,
        trials: int = 1_000,
        seed: int = 42,
        modes: tuple[AuctionMode, ...] = tuple(AuctionMode),
    ) -> AuctionAnalysis:
        if trials < 1:
            raise ValueError("trials must be positive")
        summaries: list[ScenarioSummary] = []
        samples: list[AuctionRun] = []
        for mode_index, mode in enumerate(modes):
            revenue_total = 0.0
            wealth_total = 0.0
            richest_share_total = 0.0
            bankrupt_total = 0.0
            for trial in range(trials):
                run_seed = seed + mode_index * 1_000_003 + trial
                run = self.simulator.run(rules, mode, seed=run_seed)
                if trial == 0:
                    samples.append(run)
                wealth = sum(run.final_budgets)
                revenue_total += run.auctioneer_revenue
                wealth_total += wealth
                richest_share_total += max(run.final_budgets) / wealth if wealth else 0.0
                bankrupt_total += sum(budget == 0 for budget in run.final_budgets)
            summaries.append(
                ScenarioSummary(
                    mode,
                    trials,
                    revenue_total / trials,
                    wealth_total / trials,
                    richest_share_total / trials,
                    bankrupt_total / trials,
                )
            )
        return AuctionAnalysis(
            rules,
            self.symmetric_benchmark(rules.player_count, rules.prize_value),
            tuple(summaries),
            tuple(samples),
        )
