"""Safe signalling strategies for the prisoners-and-light puzzle."""

from __future__ import annotations

import random
from collections.abc import Iterable

from aip.puzzles.prisoners.models import (
    DeclarationGoal,
    InitialLight,
    PrisonerPlan,
    SimulationResult,
    VisitRecord,
)


class PrisonerLightSolver:
    """Design and simulate the designated-counter strategy.

    Prisoner 0 is the counter. Every other prisoner turns the light on only
    when it is off and they still owe a signal. The counter turns an on light
    off and increments a private count. No visit uses more than one operation.
    """

    def create_plan(
        self,
        prisoner_count: int = 100,
        initial_light: InitialLight | str = InitialLight.OFF,
        goal: DeclarationGoal | str = DeclarationGoal.TURNED_ON,
    ) -> PrisonerPlan:
        if prisoner_count < 1:
            raise ValueError("prisoner_count must be at least 1")
        state = InitialLight(initial_light)
        declaration_goal = DeclarationGoal(goal)
        if state is InitialLight.OFF:
            quota = 1
            threshold = prisoner_count - 1
            proof = (
                "The light starts off, so every counted on-signal came from a distinct "
                "non-counter who had not signalled before. Reaching N-1 proves all of "
                "them have visited; the counter has also visited."
            )
        else:
            quota = 2
            threshold = 2 * (prisoner_count - 1)
            proof = (
                "At most one count can come from an initially-on light. If any "
                "non-counter had never visited, the other N-2 people could contribute "
                "at most 2(N-2) signals; even with one phantom count this is below "
                "2(N-1). Therefore the threshold cannot be reached too early."
            )
        if declaration_goal is DeclarationGoal.TURNED_ON:
            proof += (
                " The counter is also forbidden to declare until personally turning "
                "the light on once, so the stronger literal goal covers every prisoner."
            )
        return PrisonerPlan(
            prisoner_count=prisoner_count,
            counter_id=0,
            initial_light=state,
            goal=declaration_goal,
            signals_per_non_counter=quota,
            declaration_count=threshold,
            almost_sure=True,
            finite_day_guarantee=False,
            safety_argument=proof,
        )

    def simulate(
        self,
        plan: PrisonerPlan,
        *,
        seed: int | None = None,
        max_days: int = 1_000_000,
        actual_initial_on: bool = False,
    ) -> SimulationResult:
        if max_days < 1:
            raise ValueError("max_days must be positive")
        rng = random.Random(seed)
        schedule = (rng.randrange(plan.prisoner_count) for _ in range(max_days))
        return self.run_schedule(
            plan, schedule, actual_initial_on=actual_initial_on
        )

    def run_schedule(
        self,
        plan: PrisonerPlan,
        schedule: Iterable[int],
        *,
        actual_initial_on: bool = False,
    ) -> SimulationResult:
        if plan.initial_light is InitialLight.OFF and actual_initial_on:
            raise ValueError("known-off plan contradicts actual_initial_on=True")

        light = actual_initial_on
        count = 0
        signals = [0] * plan.prisoner_count
        counter_signal_pending = False
        visited: set[int] = set()
        records: list[VisitRecord] = []

        for day, prisoner in enumerate(schedule, start=1):
            if not 0 <= prisoner < plan.prisoner_count:
                raise ValueError(f"invalid prisoner id {prisoner}")
            visited.add(prisoner)
            before = light
            action = "do nothing"

            if prisoner == plan.counter_id:
                if light:
                    light = False
                    if counter_signal_pending:
                        counter_signal_pending = False
                        action = "turn off own signal (not counted)"
                    else:
                        count += 1
                        action = "turn light off and increment count"
                elif (
                    plan.goal is DeclarationGoal.TURNED_ON
                    and signals[prisoner] == 0
                ):
                    light = True
                    signals[prisoner] = 1
                    counter_signal_pending = True
                    action = "turn light on once to satisfy own requirement"
            elif not light and signals[prisoner] < plan.signals_per_non_counter:
                light = True
                signals[prisoner] += 1
                action = f"turn light on (signal {signals[prisoner]})"

            counter_goal_met = (
                plan.goal is DeclarationGoal.VISITED or signals[plan.counter_id] == 1
            )
            declared = (
                prisoner == plan.counter_id
                and count >= plan.declaration_count
                and counter_goal_met
            )
            if declared:
                action += f"; declare goal achieved: everyone has {plan.goal.value}"
            records.append(
                VisitRecord(day, prisoner, before, action, light, count, declared)
            )
            if declared:
                if plan.goal is DeclarationGoal.TURNED_ON:
                    safe = all(signal >= 1 for signal in signals)
                else:
                    safe = len(visited) == plan.prisoner_count
                return SimulationResult(
                    plan,
                    True,
                    day,
                    safe,
                    tuple(sorted(visited)),
                    tuple(signals),
                    tuple(records),
                )

        return SimulationResult(
            plan,
            False,
            None,
            None,
            tuple(sorted(visited)),
            tuple(signals),
            tuple(records),
        )
