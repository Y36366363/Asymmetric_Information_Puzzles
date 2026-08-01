"""Exact timing analysis for the classic known-off, visit-goal protocol."""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProbabilityPoint:
    day: int
    everyone_visited: float
    counter_has_proof: float


@dataclass(frozen=True, slots=True)
class ConfidenceDay:
    confidence: float
    visit_day: int
    proof_day: int


@dataclass(frozen=True, slots=True)
class MonteCarloCheck:
    trials: int
    mean_visit_day: float
    mean_proof_day: float


@dataclass(frozen=True, slots=True)
class TimingAnalysis:
    prisoner_count: int
    expected_visit_day: float
    expected_proof_day: float
    points: tuple[ProbabilityPoint, ...]
    confidence_days: tuple[ConfidenceDay, ...]
    illustrative_deadline: int
    illustrative_deadline_probability: float
    false_declaration_cost: float
    daily_wait_cost: float
    monte_carlo: MonteCarloCheck | None


class PrisonerTimingAnalyzer:
    """Compare physical coverage, safe proof, and risky fixed deadlines."""

    def analyze(
        self,
        prisoner_count: int = 100,
        *,
        max_days: int = 30_000,
        sample_days: tuple[int, ...] = (
            300,
            400,
            500,
            600,
            700,
            800,
            900,
            1000,
            1200,
            1400,
            8000,
            9000,
            10000,
            11000,
            12000,
            13000,
            14000,
        ),
        confidences: tuple[float, ...] = (0.5, 0.9, 0.95, 0.99, 0.999),
        false_declaration_cost: float = 1_000_000.0,
        daily_wait_cost: float = 1.0,
        simulation_trials: int = 0,
        seed: int = 42,
    ) -> TimingAnalysis:
        if prisoner_count < 1:
            raise ValueError("prisoner_count must be at least 1")
        if max_days < 1:
            raise ValueError("max_days must be positive")
        if any(not 0 < confidence < 1 for confidence in confidences):
            raise ValueError("confidences must lie strictly between 0 and 1")
        if false_declaration_cost <= 0 or daily_wait_cost <= 0:
            raise ValueError("costs must be positive")

        visit_cdf = self.everyone_visited_cdf(prisoner_count, max_days)
        proof_cdf = self.single_counter_cdf(prisoner_count, max_days)
        points = tuple(
            ProbabilityPoint(day, visit_cdf[day], proof_cdf[day])
            for day in sample_days
            if 0 <= day <= max_days
        )
        confidence_days = tuple(
            ConfidenceDay(
                confidence,
                self._quantile(visit_cdf, confidence),
                self._quantile(proof_cdf, confidence),
            )
            for confidence in confidences
        )
        deadline = min(
            range(1, max_days + 1),
            key=lambda day: (
                day * daily_wait_cost
                + (1.0 - visit_cdf[day]) * false_declaration_cost
            ),
        )
        simulation = (
            self.monte_carlo(prisoner_count, simulation_trials, seed)
            if simulation_trials
            else None
        )
        return TimingAnalysis(
            prisoner_count=prisoner_count,
            expected_visit_day=prisoner_count
            * sum(1.0 / k for k in range(1, prisoner_count + 1)),
            expected_proof_day=self.expected_single_counter_days(prisoner_count),
            points=points,
            confidence_days=confidence_days,
            illustrative_deadline=deadline,
            illustrative_deadline_probability=visit_cdf[deadline],
            false_declaration_cost=false_declaration_cost,
            daily_wait_cost=daily_wait_cost,
            monte_carlo=simulation,
        )

    @staticmethod
    def everyone_visited_cdf(prisoner_count: int, max_days: int) -> list[float]:
        """Exact coupon-collector CDF via a stable occupancy recurrence."""

        distribution = [0.0] * (prisoner_count + 1)
        distribution[0] = 1.0
        cdf = [1.0 if prisoner_count == 0 else 0.0]
        for _day in range(1, max_days + 1):
            updated = [0.0] * (prisoner_count + 1)
            for seen, probability in enumerate(distribution):
                if probability == 0:
                    continue
                updated[seen] += probability * seen / prisoner_count
                if seen < prisoner_count:
                    updated[seen + 1] += probability * (prisoner_count - seen) / prisoner_count
            distribution = updated
            cdf.append(distribution[prisoner_count])
        return cdf

    @staticmethod
    def single_counter_cdf(prisoner_count: int, max_days: int) -> list[float]:
        """Exact CDF of the known-off designated-counter protocol."""

        if prisoner_count == 1:
            return [0.0] + [1.0] * max_days
        target = prisoner_count - 1
        off = [0.0] * target
        on = [0.0] * target
        off[0] = 1.0
        completed = 0.0
        cdf = [0.0]
        for _day in range(1, max_days + 1):
            next_off = [0.0] * target
            next_on = [0.0] * target
            for counted in range(target):
                unreported = target - counted
                next_on[counted] += off[counted] * unreported / prisoner_count
                next_off[counted] += off[counted] * (prisoner_count - unreported) / prisoner_count
                next_on[counted] += on[counted] * (prisoner_count - 1) / prisoner_count
                counter_visit = on[counted] / prisoner_count
                if counted + 1 == target:
                    completed += counter_visit
                else:
                    next_off[counted + 1] += counter_visit
            off, on = next_off, next_on
            cdf.append(min(1.0, completed))
        return cdf

    @staticmethod
    def expected_single_counter_days(prisoner_count: int) -> float:
        if prisoner_count == 1:
            return 1.0
        harmonic = sum(1.0 / k for k in range(1, prisoner_count))
        return prisoner_count * harmonic + prisoner_count * (prisoner_count - 1)

    def monte_carlo(
        self, prisoner_count: int, trials: int, seed: int = 42
    ) -> MonteCarloCheck:
        if trials < 1:
            raise ValueError("trials must be positive")
        rng = random.Random(seed)
        visit_total = 0
        proof_total = 0
        for _ in range(trials):
            seen: set[int] = set()
            visit_day = 0
            while len(seen) < prisoner_count:
                visit_day += 1
                seen.add(rng.randrange(prisoner_count))
            visit_total += visit_day

            counted = 0
            light_on = False
            signalled = [False] * prisoner_count
            proof_day = 0
            while counted < prisoner_count - 1:
                proof_day += 1
                prisoner = rng.randrange(prisoner_count)
                if prisoner == 0:
                    if light_on:
                        light_on = False
                        counted += 1
                elif not light_on and not signalled[prisoner]:
                    signalled[prisoner] = True
                    light_on = True
            if prisoner_count == 1:
                proof_day = 1
            proof_total += proof_day
        return MonteCarloCheck(
            trials,
            visit_total / trials,
            proof_total / trials,
        )

    @staticmethod
    def _quantile(cdf: list[float], confidence: float) -> int:
        for day, probability in enumerate(cdf):
            if probability >= confidence:
                return day
        raise ValueError("max_days is too small for the requested confidence")
