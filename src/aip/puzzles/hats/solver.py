"""Finite epistemic solver for the public coloured-hat puzzle."""

from __future__ import annotations

from itertools import product

from aip.core.information import InformationSet, Observation
from aip.puzzles.hats.models import HatRound, HatSolution, HatWorld


class HatSolver:
    """Model repeated simultaneous reasoning after a public announcement.

    Everyone sees every hat except their own. It is publicly announced that at
    least one hat has ``target_color``. Each round all players simultaneously
    say whether they know their own colour. A public round with no knower
    eliminates every world in which somebody would have known at that round.
    """

    def solve(
        self,
        actual_colors: tuple[str, ...] | list[str] | str,
        target_color: str,
        other_color: str,
        max_rounds: int | None = None,
    ) -> HatSolution:
        actual = tuple(actual_colors)
        self._validate(actual, target_color, other_color)
        limit = max_rounds or len(actual) + 1

        public_history = (
            Observation(
                "public_announcement",
                f"at least one hat is {target_color}",
                is_public=True,
                timestamp=0,
            ),
        )
        possible_worlds = tuple(
            world
            for world in product((target_color, other_color), repeat=len(actual))
            if target_color in world
        )
        rounds: list[HatRound] = []

        for number in range(1, limit + 1):
            actual_sets = tuple(
                self._information_set(actual, player, possible_worlds, public_history, number)
                for player in range(len(actual))
            )
            actual_knowers = tuple(
                player
                for player, info in enumerate(actual_sets)
                if len({world[player] for world in info.possible_states}) == 1
            )
            event_text = (
                "players " + ", ".join(str(i + 1) for i in actual_knowers) + " know"
                if actual_knowers
                else "nobody knows"
            )
            rounds.append(
                HatRound(number, len(possible_worlds), actual_knowers, actual_sets, event_text)
            )
            if actual_knowers:
                break

            no_knowledge = Observation(
                "simultaneous_answers", event_text, is_public=True, timestamp=number
            )
            possible_worlds = tuple(
                world
                for world in possible_worlds
                if not self._knowers_in_world(world, possible_worlds)
            )
            public_history = public_history + (no_knowledge,)
            if actual not in possible_worlds:
                raise RuntimeError("actual world was eliminated by a truthful public event")

        return HatSolution(actual, target_color, tuple(rounds))

    @staticmethod
    def _information_set(
        world: HatWorld,
        player: int,
        public_worlds: tuple[HatWorld, ...],
        public_history: tuple[Observation, ...],
        round_number: int,
    ) -> InformationSet[HatWorld]:
        visible = world[:player] + world[player + 1 :]
        alternatives = tuple(
            candidate
            for candidate in public_worlds
            if candidate[:player] + candidate[player + 1 :] == visible
        )
        return InformationSet(
            key=f"hats-r{round_number}-p{player + 1}",
            player_id=player + 1,
            possible_states=alternatives,
            observations=(
                Observation("visible_hats", visible, is_public=False, timestamp=round_number),
            ),
            public_history=public_history,
        )

    def _knowers_in_world(
        self, world: HatWorld, public_worlds: tuple[HatWorld, ...]
    ) -> tuple[int, ...]:
        return tuple(
            player
            for player in range(len(world))
            if len(
                {
                    candidate[player]
                    for candidate in public_worlds
                    if candidate[:player] + candidate[player + 1 :]
                    == world[:player] + world[player + 1 :]
                }
            )
            == 1
        )

    @staticmethod
    def _validate(actual: HatWorld, target: str, other: str) -> None:
        if not actual:
            raise ValueError("at least one player is required")
        if not target or not other or target == other:
            raise ValueError("target_color and other_color must be distinct non-empty values")
        if any(color not in (target, other) for color in actual):
            raise ValueError("actual colors must use only target_color and other_color")
        if target not in actual:
            raise ValueError("actual world contradicts the public announcement")
