# AIP — Asymmetric Information Puzzles

## Updates 07/31/2026

- **Public-knowledge hat solver** — Added finite-world information sets,
  simultaneous public announcements, repeated world elimination, and explicit
  discovery-delay traces for arbitrary two-colour hat configurations.

AIP is a modular Python environment for exploring dynamic games, backward
induction, common knowledge, information sets, and robust strategies.

The project currently solves pirate gold allocation and public coloured-hat
reasoning. It also reserves clean module boundaries for sequential bean taking,
the moving worm, and future puzzles.

## Project layout

```text
.
├── pyproject.toml
├── README.md
├── src/aip/
│   ├── cli.py                    # command-line interface
│   ├── core/
│   │   ├── game.py               # reusable game/solver protocols
│   │   └── information.py        # information sets, beliefs, public history
│   └── puzzles/
│       ├── pirates/              # complete backward-induction solver
│       │   ├── models.py
│       │   ├── solver.py
│       │   └── formatting.py
│       ├── hats/                  # common-knowledge evolution solver
│       ├── beans/                 # planned: ranges and robust strategies
│       └── worm/                  # planned: adversarial search strategy
└── tests/
    ├── test_information.py
    └── test_pirates.py
```

## Run the pirate solver

No third-party runtime dependency is required:

```bash
PYTHONPATH=src python -m aip pirates --pirates 5 --gold 100
```

Or install the project in editable mode and use its command:

```bash
python -m pip install -e .
aip pirates --pirates 5 --gold 100
```

The solver prints every suffix game, beginning with the youngest pirate alone,
so the full backward-induction chain is visible. For every round it shows the
allocation, threshold, individual vote, rejection outcome comparison, and
reasoning.

Useful rule variants:

```bash
aip pirates --pirates 5 --gold 100 --strict-majority
aip pirates --pirates 5 --gold 100 --accept-equal
```

## Default pirate assumptions

1. Pirates rank outcomes lexicographically: survival first, then gold.
2. The proposer votes for their own feasible proposal.
3. At least half of all votes passes, so an exact tie passes.
4. A non-proposer rejects when survival and gold are exactly equal.
5. If multiple cheapest winning coalitions exist, the more senior candidate is
   chosen to make the displayed equilibrium deterministic.

Both the vote threshold and equal-outcome preference are configurable through
`PirateRules`. If a coalition is unaffordable, the solver records the
proposer's death and carries forward the already-solved continuation outcome.

## Run the coloured-hat solver

```bash
PYTHONPATH=src python -m aip hats --colors BBBRR --target B --other R
```

Every player sees all hats except their own. The announcement “at least one hat
is B” is public knowledge, and all answers are simultaneous and public. With
three B hats, nobody knows in rounds one and two; all three B-hat players know
in round three. The output exposes each player's information set at every round.

## Architecture notes

`InformationSet[StateT]` is the extension seam for imperfect-information
puzzles. It records all states a player regards as possible, private
observations, public history, and optional Bayesian beliefs. Domain modules
provide the compatibility rule used to eliminate states after an observation.

This supports the next planned modules without coupling their reasoning styles:

- **Hats:** each public answer becomes a timestamped public observation;
  repeated state elimination models common-knowledge evolution and delay.
- **Beans:** hidden quantities or opponent types live in possible states;
  beliefs can support expected utility while intervals support worst-case play.
- **Worm:** a belief state is the set of holes still reachable after each forced
  move; actions update that set adversarially.

Puzzle solvers remain self-contained under `puzzles/<name>`, while shared state,
transition, and information abstractions stay dependency-free in `core`.

## Tests

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```
