from __future__ import annotations

from aip.puzzles.liars_dice.models import BidAnalysis, BidderType, ProbabilityCheck, RaiseOption
from aip.core.information import InformationSet
from aip.puzzles.liars_dice.models import BidderHypothesis


def format_liars_dice(
    analysis: BidAnalysis,
    raises: tuple[RaiseOption, ...],
    check: ProbabilityCheck,
    bidder_beliefs: InformationSet[BidderHypothesis],
) -> str:
    bluffer_probability = next(
        probability
        for hypothesis, probability in bidder_beliefs.beliefs.items()
        if hypothesis.bidder_type is BidderType.BLUFFER
    )
    lines = [
        f"Liar's Dice bid: at least {analysis.bid.quantity} dice showing "
        f"{analysis.bid.face} (including wild ones when enabled)",
        f"  own matches={analysis.own_matches}; hidden dice={analysis.hidden_dice}; "
        f"per-hidden-die match chance={analysis.hidden_match_probability:.2%}",
        f"  still needed={analysis.matches_still_needed}; "
        f"P(bid true)={analysis.probability_bid_true:.4%}; "
        f"P(exact total)={analysis.probability_exactly_true:.4%}",
        f"  challenge EV={analysis.challenge_expected_value:+.4f}; "
        f"symmetric threshold={analysis.challenge_threshold:.2%}; "
        f"recommendation={analysis.recommendation}",
        f"  behavioral posterior P(bluffer | this bid)={bluffer_probability:.2%}",
        "",
        "Safest legal raises under raw probability (not equilibrium advice):",
    ]
    lines.extend(
        f"  {option.bid.quantity} × face {option.bid.face}: "
        f"P(true)={option.probability_true:.2%}"
        for option in raises
    )
    lines.extend(
        [
            "",
            f"Monte Carlo check ({check.trials} trials): exact={check.exact_probability:.4%}, "
            f"simulated={check.simulated_probability:.4%}, "
            f"absolute error={check.absolute_error:.4%}",
        ]
    )
    return "\n".join(lines)
