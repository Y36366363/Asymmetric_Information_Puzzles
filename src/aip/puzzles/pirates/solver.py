"""Backward-induction solver for the pirate gold-allocation puzzle."""

from __future__ import annotations

from aip.puzzles.pirates.models import (
    PirateOutcome,
    PirateRules,
    ProposalRound,
    Solution,
    Vote,
)


class PirateSolver:
    """Compute a deterministic subgame-perfect outcome.

    Preferences are lexicographic: (1) stay alive, (2) receive more gold.
    If both are equal, ``rules.accept_equal_gold`` controls the vote. When
    several equally cheap coalitions exist, more senior pirates are bribed
    first; this only selects one equilibrium and does not change its cost.
    """

    def __init__(self, rules: PirateRules | None = None) -> None:
        self.rules = rules or PirateRules()

    def solve(self, pirate_count: int, total_gold: int) -> Solution:
        if pirate_count < 1:
            raise ValueError("pirate_count must be at least 1")
        if total_gold < 0:
            raise ValueError("total_gold cannot be negative")

        names = self._pirate_names(pirate_count)
        rounds: list[ProposalRound] = []

        # Solve suffix games from the lone youngest pirate back to the full game.
        for active_count in range(1, pirate_count + 1):
            active_names = names[pirate_count - active_count :]
            rejection = rounds[-1] if rounds else None
            rounds.append(self._solve_round(active_names, total_gold, rejection))

        return Solution(names, total_gold, tuple(rounds))

    def _solve_round(
        self,
        names: tuple[str, ...],
        total_gold: int,
        rejection: ProposalRound | None,
    ) -> ProposalRound:
        count = len(names)
        required = self.rules.votes_required(count)
        proposer = names[0]

        rejection_outcomes: list[PirateOutcome] = [PirateOutcome(False, 0)]
        if rejection is not None:
            rejection_outcomes.extend(
                PirateOutcome(alive, gold)
                for alive, gold in zip(rejection.alive, rejection.allocation)
            )

        candidates: list[tuple[int, int]] = []
        # (bribe cost, voter index); proposer is handled separately.
        for index in range(1, count):
            outcome = rejection_outcomes[index]
            if not outcome.alive:
                cost = 0  # survival is strictly better than any death outcome
            elif self.rules.accept_equal_gold:
                cost = outcome.gold
            else:
                cost = outcome.gold + 1
            candidates.append((cost, index))
        candidates.sort(key=lambda item: (item[0], item[1]))

        automatic_yes = 1 if self.rules.proposer_votes else 0
        supporters_needed = max(0, required - automatic_yes)
        chosen = candidates[:supporters_needed]
        affordable = len(chosen) == supporters_needed and sum(cost for cost, _ in chosen) <= total_gold

        if affordable:
            allocation = [0] * count
            for cost, index in chosen:
                allocation[index] = cost
            allocation[0] = total_gold - sum(allocation)
            alive = [True] * count
        else:
            # No passing proposal exists: proposer dies and the suffix-game
            # equilibrium is played. This round records that realised outcome.
            allocation = [0] + ([] if rejection is None else list(rejection.allocation))
            alive = [False] + ([] if rejection is None else list(rejection.alive))

        votes = self._build_votes(
            names, tuple(allocation), tuple(rejection_outcomes), affordable
        )
        yes = sum(vote.supports for vote in votes)
        passed = affordable and yes >= required
        if passed:
            coalition = ", ".join(vote.pirate for vote in votes if vote.supports)
            explanation = (
                f"{proposer} needs {required} yes vote(s), buys the cheapest "
                f"winning coalition [{coalition}], and keeps {allocation[0]} gold."
            )
        else:
            explanation = (
                f"{proposer} cannot fund {required} yes vote(s); the proposal "
                "fails, the proposer dies, and the continuation outcome applies."
            )

        return ProposalRound(
            pirate_count=count,
            proposer=proposer,
            allocation=tuple(allocation),
            alive=tuple(alive),
            votes=votes,
            votes_required=required,
            passed=passed,
            explanation=explanation,
        )

    def _build_votes(
        self,
        names: tuple[str, ...],
        allocation: tuple[int, ...],
        rejection: tuple[PirateOutcome, ...],
        proposal_is_feasible: bool,
    ) -> tuple[Vote, ...]:
        votes: list[Vote] = []
        for index, name in enumerate(names):
            offered = allocation[index] if proposal_is_feasible else 0
            outside = rejection[index]
            if index == 0:
                supports = self.rules.proposer_votes and proposal_is_feasible
                reason = "proposer supports their own feasible proposal" if supports else "no feasible passing proposal"
            elif not proposal_is_feasible:
                supports = False
                reason = "the displayed allocation is the rejection outcome, not a proposal"
            elif not outside.alive:
                supports = True
                reason = f"accepting guarantees survival; rejection means death with {outside.gold} gold"
            elif offered > outside.gold:
                supports = True
                reason = f"{offered} gold is better than {outside.gold} after rejection"
            elif offered == outside.gold and self.rules.accept_equal_gold:
                supports = True
                reason = f"equal {offered} gold is enough under the configured tie preference"
            else:
                supports = False
                comparison = "equal to" if offered == outside.gold else "less than"
                reason = f"{offered} gold is {comparison} the {outside.gold} available after rejection"
            votes.append(Vote(name, offered, outside, supports, reason))
        return tuple(votes)

    @staticmethod
    def _pirate_names(count: int) -> tuple[str, ...]:
        """A is most senior; names remain readable beyond 26 pirates."""

        def excel_name(number: int) -> str:
            result = ""
            while number:
                number, remainder = divmod(number - 1, 26)
                result = chr(65 + remainder) + result
            return result

        return tuple(excel_name(index) for index in range(1, count + 1))

