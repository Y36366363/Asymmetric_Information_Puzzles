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
        tacit_active = behavior is AuctionMode.TACIT
        break_round: int | None = None
        active_players = set(range(rules.player_count))
        expelled_players: set[int] = set()

        if behavior is AuctionMode.SOCIAL and rules.initial_budget < rules.social_leader_bid:
            raise ValueError("social leadership mode requires budget >= social_leader_bid")

        for round_number in range(1, rules.rounds + 1):
            before = tuple(budgets)
            active_before = tacit_active
            bids = self._bids(
                rules,
                behavior,
                budgets,
                round_number,
                rng,
                tacit_active=tacit_active,
                active_players=active_players,
            )
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
            if behavior is AuctionMode.TACIT and tacit_active and max_bid > 1:
                tacit_active = False
                break_round = round_number
            expelled_this_round: set[int] = set()
            if behavior is AuctionMode.SOCIAL and round_number >= 2:
                compliant = {player for player in active_players if bids[player] == 1}
                noncompliant = active_players.difference(compliant)
                if (
                    rules.social_identity_observable
                    and len(compliant) > len(active_players) / 2
                ):
                    expelled_this_round = set(noncompliant)
                    active_players.difference_update(expelled_this_round)
                    expelled_players.update(expelled_this_round)
            rounds.append(
                AuctionRound(
                    round_number,
                    before,
                    tuple(bids),
                    winner,
                    tuple(budgets),
                    revenue,
                    max_bid,
                    active_before,
                    tacit_active,
                    tuple(sorted(active_players.union(expelled_this_round))),
                    tuple(sorted(expelled_this_round)),
                )
            )
        return AuctionRun(
            rules,
            behavior,
            tuple(rounds),
            tuple(budgets),
            total_revenue,
            break_round,
            tuple(sorted(expelled_players)),
        )

    def _bids(
        self,
        rules: AuctionRules,
        mode: AuctionMode,
        budgets: list[int],
        round_number: int,
        rng: random.Random,
        *,
        tacit_active: bool = False,
        active_players: set[int] | None = None,
    ) -> list[int]:
        participants = set(range(rules.player_count)) if active_players is None else active_players
        active = sum(budget > 0 and player in participants for player, budget in enumerate(budgets))
        if mode is AuctionMode.SOCIAL:
            bids = [0] * rules.player_count
            supporters = set(range(rules.effective_social_supporters))
            if round_number == 1:
                bids[0] = rules.social_leader_bid
                return bids
            for player in participants:
                if budgets[player] <= 0:
                    continue
                if player not in supporters:
                    bids[player] = min(2, budgets[player])
                elif rng.random() < rules.social_deviation_probability:
                    bids[player] = min(2, budgets[player])
                else:
                    bids[player] = 1
            return bids
        if mode is AuctionMode.COOPERATIVE or (
            mode is AuctionMode.TACIT and tacit_active
        ):
            bids = [0] * rules.player_count
            for offset in range(rules.player_count):
                designated = (round_number - 1 + offset) % rules.player_count
                if budgets[designated] > 0:
                    bids[designated] = 1
                    break
            if mode is AuctionMode.TACIT:
                for player, budget in enumerate(budgets):
                    if (
                        bids[player] == 0
                        and budget >= 2
                        and rng.random() < rules.tacit_deviation_probability
                    ):
                        bids[player] = 2
            return bids

        effective_mode = AuctionMode.EQUILIBRIUM if mode is AuctionMode.TACIT else mode

        bids: list[int] = []
        for player, budget in enumerate(budgets):
            if budget == 0 or player not in participants:
                bids.append(0)
                continue
            if effective_mode is AuctionMode.NAIVE:
                if rng.random() < 0.08:
                    bids.append(0)
                else:
                    ceiling = min(budget, int(rules.prize_value * 1.5))
                    bids.append(rng.randint(1, ceiling))
            elif effective_mode is AuctionMode.CAUTIOUS:
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

    @staticmethod
    def tacit_patience_threshold(player_count: int, prize_value: float = 100) -> float:
        """Worst-position discount factor for a rotating price-1 convention.

        A non-designated bidder can bid 2 for an immediate V-2 gain. Detection
        triggers the credible one-shot equilibrium forever (zero continuation
        payoff). The most tempted player waits m-1 rounds for their next V-1
        cooperative prize.
        """

        if player_count < 2 or prize_value <= 2:
            raise ValueError("threshold needs at least two players and prize value > 2")
        low, high = 0.0, 1.0
        for _ in range(100):
            discount = (low + high) / 2
            cooperative_value = (
                discount ** (player_count - 1)
                * (prize_value - 1)
                / (1 - discount**player_count)
            )
            if cooperative_value >= prize_value - 2:
                high = discount
            else:
                low = discount
        return high

    @staticmethod
    def social_patience_threshold(player_count: int, prize_value: float = 100) -> float:
        """Discount factor when an identifiable deviator is permanently excluded."""

        if player_count < 2:
            return 1.0
        cooperative_flow = prize_value / player_count - 1
        if cooperative_flow <= 0:
            return 1.0
        deviation_gain = prize_value - 2 - cooperative_flow
        return deviation_gain / (deviation_gain + cooperative_flow)

    def analyze(
        self,
        rules: AuctionRules,
        *,
        trials: int = 1_000,
        seed: int = 42,
        modes: tuple[AuctionMode, ...] = (
            AuctionMode.NAIVE,
            AuctionMode.CAUTIOUS,
            AuctionMode.EQUILIBRIUM,
            AuctionMode.COOPERATIVE,
            AuctionMode.TACIT,
        ),
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
            coordination_survivals = 0
            expelled_total = 0.0
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
                if mode is AuctionMode.TACIT and run.coordination_break_round is None:
                    coordination_survivals += 1
                expelled_total += len(run.expelled_players)
            summaries.append(
                ScenarioSummary(
                    mode,
                    trials,
                    revenue_total / trials,
                    wealth_total / trials,
                    richest_share_total / trials,
                    bankrupt_total / trials,
                    coordination_survivals / trials if mode is AuctionMode.TACIT else None,
                    expelled_total / trials,
                )
            )
        return AuctionAnalysis(
            rules,
            self.symmetric_benchmark(rules.player_count, rules.prize_value),
            tuple(summaries),
            tuple(samples),
            self.tacit_patience_threshold(rules.player_count, rules.prize_value),
            (
                self.social_patience_threshold(
                    rules.effective_social_supporters, rules.prize_value
                )
                if rules.effective_social_supporters > rules.player_count / 2
                else 1.0
            ),
            float(rules.social_leader_bid - rules.prize_value),
            rules.prize_value / rules.effective_social_supporters - 1,
        )
