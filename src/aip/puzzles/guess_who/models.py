from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Character:
    name: str
    hair: str
    glasses: bool
    hat: bool
    facial_hair: bool
    smiling: bool

    def value(self, attribute: str) -> object:
        if attribute not in {"hair", "glasses", "hat", "facial_hair", "smiling"}:
            raise ValueError(f"unknown character attribute: {attribute}")
        return getattr(self, attribute)


@dataclass(frozen=True, slots=True)
class Question:
    id: str
    attribute: str
    value: object
    label: str

    def matches(self, character: Character) -> bool:
        return character.value(self.attribute) == self.value


DEFAULT_QUESTIONS: tuple[Question, ...] = (
    Question("hair_black", "hair", "black", "Does the person have black hair?"),
    Question("hair_brown", "hair", "brown", "Does the person have brown hair?"),
    Question("hair_blond", "hair", "blond", "Does the person have blond hair?"),
    Question("hair_red", "hair", "red", "Does the person have red hair?"),
    Question("glasses", "glasses", True, "Does the person wear glasses?"),
    Question("hat", "hat", True, "Does the person wear a hat?"),
    Question("facial_hair", "facial_hair", True, "Does the person have facial hair?"),
    Question("smiling", "smiling", True, "Is the person smiling?"),
)


_NAMES = (
    "Ada", "Bruno", "Cleo", "Dante", "Esme", "Farah",
    "Hugo", "Iris", "Jules", "Kira", "Leon", "Mira",
    "Nico", "Opal", "Pavel", "Quinn", "Rosa", "Soren",
    "Talia", "Uma", "Vik", "Wren", "Xavi", "Yara",
)
_PATTERNS = {
    "black": (0, 3, 5, 10, 12, 15),
    "brown": (1, 2, 7, 8, 13, 14),
    "blond": (0, 6, 7, 9, 10, 15),
    "red": (1, 4, 6, 9, 11, 14),
}


def _build_roster() -> tuple[Character, ...]:
    characters: list[Character] = []
    name_index = 0
    for hair, patterns in _PATTERNS.items():
        for pattern in patterns:
            characters.append(
                Character(
                    name=_NAMES[name_index],
                    hair=hair,
                    glasses=bool(pattern & 1),
                    hat=bool(pattern & 2),
                    facial_hair=bool(pattern & 4),
                    smiling=bool(pattern & 8),
                )
            )
            name_index += 1
    return tuple(characters)


DEFAULT_ROSTER = _build_roster()
