from __future__ import annotations

import math
import random

from aip.core.information import InformationSet, Observation
from aip.puzzles.liars_dice.models import (
    BidAnalysis,
    BidderHypothesis,
    BidderType,
    DiceBid,
    LiarsDiceRules,
    ProbabilityCheck,
    RaiseOption,
)


class LiarsDiceAnalyzer:
    """Exact binomial odds from one private hand plus simple type inference."""

    @staticmethod
    def is_legal_raise(previous: DiceBid, proposed: DiceBid) -> bool:
        return proposed.quantity > previous.quantity or (
            proposed.quantity == previous.quantity and proposed.face > previous.face
        )

    @staticmethod
    def _own_matches(hand: tuple[int, ...], bid: DiceBid, rules: LiarsDiceRules) -> int:
        if rules.wild_ones and bid.face != 1:
            return sum(die == bid.face or die == 1 for die in hand)
        return hand.count(bid.face)

    @staticmethod
    def _hidden_match_probability(bid: DiceBid, rules: LiarsDiceRules) -> float:
        if rules.wild_ones and bid.face != 1:
            return 2.0 / rules.sides
        return 1.0 / rules.sides

    @staticmethod
    def _binomial_tail(trials: int, needed: int, probability: float) -> float:
        if needed <= 0:
            return 1.0
        if needed > trials:
            return 0.0
        return sum(
            math.comb(trials, successes)
            * probability**successes
            * (1.0 - probability) ** (trials - successes)
            for successes in range(needed, trials + 1)
        )

    @staticmethod
    def _binomial_mass(trials: int, successes: int, probability: float) -> float:
        if successes < 0 or successes > trials:
            return 0.0
        return (
            math.comb(trials, successes)
            * probability**successes
            * (1.0 - probability) ** (trials - successes)
        )

    def analyze_bid(
        self,
        hand: tuple[int, ...],
        bid: DiceBid,
        rules: LiarsDiceRules,
        *,
        correct_challenge_reward: float = 1.0,
        wrong_challenge_cost: float = 1.0,
    ) -> BidAnalysis:
        bid.validate(rules)
        if len(hand) != rules.dice_per_player:
            raise ValueError("hand length must equal dice_per_player")
        if any(die < 1 or die > rules.sides for die in hand):
            raise ValueError("hand contains a face outside the die")
        if correct_challenge_reward <= 0 or wrong_challenge_cost <= 0:
            raise ValueError("challenge reward and cost must be positive")
        own_matches = self._own_matches(hand, bid, rules)
        hidden_dice = rules.total_dice - len(hand)
        probability = self._hidden_match_probability(bid, rules)
        needed = bid.quantity - own_matches
        probability_true = self._binomial_tail(hidden_dice, needed, probability)
        probability_exact = self._binomial_mass(hidden_dice, needed, probability)
        expected_challenge = (
            (1.0 - probability_true) * correct_challenge_reward
            - probability_true * wrong_challenge_cost
        )
        threshold = correct_challenge_reward / (
            correct_challenge_reward + wrong_challenge_cost
        )
        return BidAnalysis(
            bid=bid,
            own_matches=own_matches,
            hidden_dice=hidden_dice,
            hidden_match_probability=probability,
            matches_still_needed=max(0, needed),
            probability_bid_true=probability_true,
            probability_exactly_true=probability_exact,
            challenge_expected_value=expected_challenge,
            challenge_threshold=threshold,
            recommendation="challenge" if probability_true < threshold else "do-not-challenge",
        )

    def safest_raises(
        self,
        hand: tuple[int, ...],
        previous: DiceBid,
        rules: LiarsDiceRules,
        *,
        limit: int = 5,
    ) -> tuple[RaiseOption, ...]:
        previous.validate(rules)
        options = []
        for quantity in range(1, rules.total_dice + 1):
            for face in range(1, rules.sides + 1):
                proposed = DiceBid(quantity, face)
                if self.is_legal_raise(previous, proposed):
                    probability = self.analyze_bid(hand, proposed, rules).probability_bid_true
                    options.append(RaiseOption(proposed, probability))
        options.sort(
            key=lambda option: (
                -option.probability_true,
                option.bid.quantity,
                option.bid.face,
            )
        )
        return tuple(options[:limit])

    def validate_probability(
        self,
        hand: tuple[int, ...],
        bid: DiceBid,
        rules: LiarsDiceRules,
        *,
        trials: int = 100_000,
        seed: int = 42,
    ) -> ProbabilityCheck:
        if trials < 1:
            raise ValueError("trials must be positive")
        exact = self.analyze_bid(hand, bid, rules).probability_bid_true
        rng = random.Random(seed)
        own_matches = self._own_matches(hand, bid, rules)
        hidden = rules.total_dice - len(hand)
        successes = 0
        for _ in range(trials):
            rolled = tuple(rng.randint(1, rules.sides) for _ in range(hidden))
            matches = own_matches + self._own_matches(rolled, bid, rules)
            successes += matches >= bid.quantity
        simulated = successes / trials
        return ProbabilityCheck(trials, exact, simulated, abs(exact - simulated))

    @staticmethod
    def infer_bidder_type(
        probability_claim_true: float,
        *,
        honest_prior: float = 0.7,
        signal_sharpness: float = 0.9,
    ) -> InformationSet[BidderHypothesis]:
        """Update a transparent two-type behavioral model from one public bid.

        Honest types favor credible claims; bluffing types favor incredible ones.
        This is a configurable behavioral signal model, not a solved equilibrium.
        """

        if not 0 <= probability_claim_true <= 1:
            raise ValueError("probability_claim_true must lie between 0 and 1")
        if not 0 < honest_prior < 1 or not 0 <= signal_sharpness <= 1:
            raise ValueError("prior and sharpness are outside their valid ranges")
        honest = BidderHypothesis(BidderType.HONEST)
        bluffer = BidderHypothesis(BidderType.BLUFFER)
        information = InformationSet(
            key="bidder-type",
            player_id="observer",
            possible_states=(honest, bluffer),
            beliefs={honest: honest_prior, bluffer: 1.0 - honest_prior},
        )
        floor = (1.0 - signal_sharpness) / 2.0

        def likelihood(state: BidderHypothesis, _fact: Observation) -> float:
            aligned = (
                probability_claim_true
                if state.bidder_type is BidderType.HONEST
                else 1.0 - probability_claim_true
            )
            return floor + signal_sharpness * aligned

        return information.bayesian_update(
            Observation("public_bid_credibility", probability_claim_true, is_public=True),
            likelihood,
        )
