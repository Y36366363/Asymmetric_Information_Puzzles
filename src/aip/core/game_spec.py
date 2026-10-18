"""Small declarative slices of a game's observation semantics."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Generic, Hashable, Iterable, Mapping, TypeVar

from aip.core.semantic_audit import ObservationInvarianceCase


State = TypeVar("State", bound=Hashable)
FieldValue = Hashable


@dataclass(frozen=True, slots=True)
class GameSpecObservationSlice:
    """Declare which state fields each player may observe.

    This deliberately narrow GameSpec component is independent of a candidate
    adapter's ``information_set`` implementation.  Public fields are visible
    to both players; each player additionally sees only their own private
    fields.
    """

    spec_id: str
    player_count: int
    public_fields: tuple[str, ...]
    private_fields_by_player: tuple[tuple[str, ...], ...]

    def __post_init__(self) -> None:
        if not self.spec_id:
            raise ValueError("GameSpec observation slice id must be nonempty")
        if self.player_count < 2:
            raise ValueError("GameSpec observation slice needs at least two players")
        if len(self.private_fields_by_player) != self.player_count:
            raise ValueError("private field declarations must cover every player")
        declarations = self.public_fields + tuple(
            field
            for fields in self.private_fields_by_player
            for field in fields
        )
        if any(not field for field in declarations):
            raise ValueError("observation field names must be nonempty")
        if len(set(declarations)) != len(declarations):
            raise ValueError("public and private observation fields must be disjoint")

    @property
    def all_fields(self) -> tuple[str, ...]:
        return self.public_fields + tuple(
            field
            for fields in self.private_fields_by_player
            for field in fields
        )

    def visible_fields(self, player: int) -> tuple[str, ...]:
        self._validate_player(player)
        return self.public_fields + self.private_fields_by_player[player]

    def hidden_fields(self, player: int) -> tuple[str, ...]:
        visible = set(self.visible_fields(player))
        return tuple(field for field in self.all_fields if field not in visible)

    def project(
        self, fields: Mapping[str, FieldValue], player: int
    ) -> tuple[tuple[str, FieldValue], ...]:
        self._validate_fields(fields)
        return tuple((field, fields[field]) for field in self.visible_fields(player))

    def _validate_player(self, player: int) -> None:
        if player < 0 or player >= self.player_count:
            raise ValueError(f"player must be between 0 and {self.player_count - 1}")

    def _validate_fields(self, fields: Mapping[str, FieldValue]) -> None:
        actual = set(fields)
        expected = set(self.all_fields)
        if actual != expected:
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            raise ValueError(
                f"observation record fields do not match GameSpec; "
                f"missing={missing}, extra={extra}"
            )
        for name in self.all_fields:
            try:
                hash(fields[name])
            except TypeError as error:
                raise TypeError(
                    f"observation field {name!r} must contain a hashable value"
                ) from error


@dataclass(frozen=True, slots=True)
class ObservationStateRecord(Generic[State]):
    """A decision state encoded using a GameSpec observation slice."""

    state: State
    acting_player: int
    fields: tuple[tuple[str, FieldValue], ...]

    @classmethod
    def from_mapping(
        cls,
        state: State,
        acting_player: int,
        fields: Mapping[str, FieldValue],
    ) -> "ObservationStateRecord[State]":
        return cls(state, acting_player, tuple(fields.items()))

    def field_mapping(self) -> dict[str, FieldValue]:
        result = dict(self.fields)
        if len(result) != len(self.fields):
            raise ValueError("observation record field names must be unique")
        return result


@dataclass(frozen=True, slots=True)
class GeneratedObservationContract(Generic[State]):
    """Pairwise invariance obligations derived from one field declaration."""

    spec_id: str
    records: int
    observation_groups: int
    cases: tuple[ObservationInvarianceCase[State], ...]

    def to_artifact(self) -> dict[str, object]:
        return {
            "spec_id": self.spec_id,
            "records": self.records,
            "observation_groups": self.observation_groups,
            "cases": len(self.cases),
        }


def generate_observation_invariance_contract(
    spec: GameSpecObservationSlice,
    records: Iterable[ObservationStateRecord[State]],
    *,
    maximum_records: int = 100_000,
    maximum_cases: int = 100_000,
) -> GeneratedObservationContract[State]:
    """Group states by declared observation and pair hidden alternatives.

    Input order is retained within and between groups.  This makes the output
    deterministic and permits an exact comparison with an independently kept
    manual reference, while the grouping itself uses only declared fields.
    """

    if maximum_records <= 0 or maximum_cases <= 0:
        raise ValueError("GameSpec generation limits must be positive")
    materialized = tuple(records)
    if not materialized:
        raise ValueError("GameSpec observation records must be nonempty")
    if len(materialized) > maximum_records:
        raise OverflowError(
            f"GameSpec observation records exceed {maximum_records}"
        )

    groups: dict[
        tuple[int, tuple[tuple[str, FieldValue], ...]],
        list[tuple[ObservationStateRecord[State], dict[str, FieldValue]]],
    ] = {}
    seen_states: set[State] = set()
    for record in materialized:
        spec._validate_player(record.acting_player)
        fields = record.field_mapping()
        spec._validate_fields(fields)
        try:
            if record.state in seen_states:
                raise ValueError("GameSpec observation states must be unique")
            seen_states.add(record.state)
        except TypeError as error:
            raise TypeError("GameSpec observation states must be hashable") from error
        key = (record.acting_player, spec.project(fields, record.acting_player))
        groups.setdefault(key, []).append((record, fields))

    cases: list[ObservationInvarianceCase[State]] = []
    for (player, _), members in groups.items():
        hidden_fields = spec.hidden_fields(player)
        for (left, left_fields), (right, right_fields) in combinations(members, 2):
            if not any(
                left_fields[field] != right_fields[field]
                for field in hidden_fields
            ):
                raise ValueError(
                    "distinct records in one observation group must differ in "
                    "at least one hidden field"
                )
            if len(cases) >= maximum_cases:
                raise OverflowError(
                    f"generated observation contract exceeds {maximum_cases} cases"
                )
            cases.append(
                ObservationInvarianceCase(
                    case_id=f"{spec.spec_id}:p{player}:pair{len(cases):06d}",
                    left_state=left.state,
                    right_state=right.state,
                )
            )

    if not cases:
        raise ValueError("GameSpec observation declaration generated no obligations")
    return GeneratedObservationContract(
        spec_id=spec.spec_id,
        records=len(materialized),
        observation_groups=len(groups),
        cases=tuple(cases),
    )
