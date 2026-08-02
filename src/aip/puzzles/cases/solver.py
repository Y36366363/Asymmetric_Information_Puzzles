from __future__ import annotations

import itertools
import math
import random
from statistics import fmean, pstdev

from aip.core.information import InformationSet, Observation
from aip.puzzles.cases.models import (
    BankerHypothesis,
    BankerProfile,
    CaseGameResult,
    CaseGameRules,
    CaseRound,
    CaseSimulationSummary,
    NextOfferProjection,
    OfferAnalysis,
    RiskPreferences,
)


class CaseGameAnalyzer:
    """Probability, utility, simulation, and hidden-banker inference tools."""

    @staticmethod
    def certainty_equivalent(
        outcomes: tuple[float, ...], preferences: RiskPreferences
    ) -> float:
        if not outcomes:
            raise ValueError("outcomes cannot be empty")
        if preferences.risk_tolerance is None:
            return fmean(outcomes)
        tolerance = preferences.risk_tolerance
        scaled = tuple(-value / tolerance for value in outcomes)
        anchor = max(scaled)
        log_mean_exp = anchor + math.log(
            sum(math.exp(value - anchor) for value in scaled) / len(scaled)
        )
        return -tolerance * log_mean_exp

    def analyze_offer(
        self,
        remaining_prizes: tuple[float, ...],
        offer: float,
        preferences: RiskPreferences = RiskPreferences(),
    ) -> OfferAnalysis:
        if not remaining_prizes or offer < 0:
            raise ValueError("remaining prizes must be nonempty and offer nonnegative")
        expected_value = fmean(remaining_prizes)
        certainty_equivalent = self.certainty_equivalent(remaining_prizes, preferences)
        return OfferAnalysis(
            remaining_prizes=remaining_prizes,
            offer=offer,
            expected_value=expected_value,
            standard_deviation=pstdev(remaining_prizes),
            certainty_equivalent=certainty_equivalent,
            risk_premium=expected_value - certainty_equivalent,
            offer_to_expected_value=(offer / expected_value if expected_value else math.inf),
            probability_case_beats_offer=sum(value > offer for value in remaining_prizes)
            / len(remaining_prizes),
            reservation_recommendation=(
                "deal" if offer >= certainty_equivalent else "no-deal"
            ),
        )

    @staticmethod
    def make_offer(
        remaining_prizes: tuple[float, ...],
        round_index: int,
        banker: BankerProfile,
        rng: random.Random | None = None,
    ) -> float:
        mean = fmean(remaining_prizes)
        base = banker.multiplier(round_index) * mean
        if banker.noise_fraction and rng is not None:
            base += rng.gauss(0.0, banker.noise_fraction * mean)
        return max(0.0, round(base, 2))

    def project_next_offer(
        self,
        remaining_prizes: tuple[float, ...],
        cases_to_open: int,
        next_multiplier: float,
        current_offer: float,
        *,
        max_outcomes: int = 200_000,
    ) -> NextOfferProjection:
        """Enumerate all equally likely sets of values that could be removed next."""

        count = len(remaining_prizes)
        if not 0 < cases_to_open < count:
            raise ValueError("cases_to_open must leave at least the player's case")
        outcomes = math.comb(count, cases_to_open)
        if outcomes > max_outcomes:
            raise ValueError("projection is too large; reduce cases or increase max_outcomes")
        offers = []
        indices = range(count)
        for removed in itertools.combinations(indices, cases_to_open):
            removed_set = set(removed)
            survivors = tuple(
                value for index, value in enumerate(remaining_prizes) if index not in removed_set
            )
            offers.append(next_multiplier * fmean(survivors))
        return NextOfferProjection(
            outcomes=outcomes,
            expected_offer=fmean(offers),
            minimum_offer=min(offers),
            maximum_offer=max(offers),
            probability_next_offer_beats_current=sum(offer > current_offer for offer in offers)
            / outcomes,
        )

    @staticmethod
    def banker_information_set(
        bankers: tuple[BankerProfile, ...], prior: tuple[float, ...] | None = None
    ) -> InformationSet[BankerHypothesis]:
        if not bankers:
            raise ValueError("at least one banker profile is required")
        probabilities = prior or tuple(1.0 / len(bankers) for _ in bankers)
        if len(probabilities) != len(bankers):
            raise ValueError("prior length must match banker profiles")
        hypotheses = tuple(BankerHypothesis(profile) for profile in bankers)
        return InformationSet(
            key="banker-type",
            player_id="contestant",
            possible_states=hypotheses,
            beliefs=dict(zip(hypotheses, probabilities)),
        )

    @staticmethod
    def update_banker_beliefs(
        information_set: InformationSet[BankerHypothesis],
        observed_offer: float,
        remaining_prizes: tuple[float, ...],
        round_index: int,
        assumed_noise_fraction: float = 0.05,
    ) -> InformationSet[BankerHypothesis]:
        if assumed_noise_fraction <= 0:
            raise ValueError("assumed_noise_fraction must be positive")
        mean = fmean(remaining_prizes)
        scale = max(0.01, assumed_noise_fraction * mean)
        observation = Observation(
            "banker_offer", observed_offer, is_public=True, timestamp=round_index
        )

        def likelihood(state: BankerHypothesis, fact: Observation) -> float:
            expected = state.profile.multiplier(round_index) * mean
            z_score = (float(fact.value) - expected) / scale
            return math.exp(-0.5 * z_score * z_score)

        return information_set.bayesian_update(observation, likelihood)

    def play(
        self,
        rules: CaseGameRules,
        banker: BankerProfile,
        preferences: RiskPreferences = RiskPreferences(),
        *,
        seed: int = 42,
    ) -> CaseGameResult:
        rng = random.Random(seed)
        shuffled = list(rules.prizes)
        rng.shuffle(shuffled)
        player_value = shuffled[0]
        unopened = shuffled[1:]
        remaining = list(rules.prizes)
        rounds: list[CaseRound] = []
        payout = player_value
        accepted_round = None
        for round_index, open_count in enumerate(rules.cases_opened_per_round):
            revealed = tuple(unopened[:open_count])
            del unopened[:open_count]
            for value in revealed:
                remaining.remove(value)
            offer = self.make_offer(tuple(remaining), round_index, banker, rng)
            analysis = self.analyze_offer(tuple(remaining), offer, preferences)
            accepted = analysis.reservation_recommendation == "deal"
            rounds.append(
                CaseRound(
                    round_number=round_index + 1,
                    revealed=revealed,
                    remaining=tuple(sorted(remaining)),
                    offer=offer,
                    analysis=analysis,
                    accepted=accepted,
                )
            )
            if accepted:
                payout = offer
                accepted_round = round_index + 1
                break
        return CaseGameResult(player_value, payout, accepted_round, tuple(rounds))

    def simulate(
        self,
        rules: CaseGameRules,
        banker: BankerProfile,
        preferences: RiskPreferences = RiskPreferences(),
        *,
        trials: int = 1_000,
        seed: int = 42,
    ) -> CaseSimulationSummary:
        if trials < 1:
            raise ValueError("trials must be positive")
        results = [
            self.play(rules, banker, preferences, seed=seed + trial)
            for trial in range(trials)
        ]
        accepted = [result for result in results if result.accepted_round is not None]
        return CaseSimulationSummary(
            trials=trials,
            mean_payout=fmean(result.payout for result in results),
            mean_case_value=fmean(result.player_case_value for result in results),
            deal_rate=len(accepted) / trials,
            mean_accepted_round=(
                fmean(result.accepted_round for result in accepted) if accepted else None
            ),
        )
