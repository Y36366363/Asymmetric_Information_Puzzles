# AIP — Asymmetric Information Puzzles

## Updates 07/31/2026

- **Guaranteed moving-worm capture** — Added shortest-path search over evolving
  hole information sets, a six-check guarantee for five holes, and a stepwise
  explanation of the forced parity change after every miss.
- **Robust bean-taking analysis** — Added five-player minimax solving over an
  uncertain pile-size interval, exact-count safe-action ranges, zero-risk action
  intersection, and a conservative recommendation when no action is universally safe.
- **Public-knowledge hat solver** — Added finite-world information sets,
  simultaneous public announcements, repeated world elimination, and explicit
  discovery-delay traces for arbitrary two-colour hat configurations.

AIP is a modular Python environment for exploring dynamic games, backward
induction, common knowledge, information sets, and robust strategies.

The project currently solves pirate gold allocation, public coloured-hat
reasoning, robust sequential bean taking, and adversarial moving-worm search.
Its shared core remains ready for future puzzles.

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
│       ├── beans/                 # interval minimax and robust strategies
│       └── worm/                  # shortest adversarial search strategy
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

## Run the bean-taking solver

```bash
PYTHONPATH=src python -m aip beans --min-beans 4 --max-beans 7 \
  --players 5 --min-take 1 --max-take 3
```

The default model has five cyclic players taking one to three beans, with the
last taker losing. Player 1 initially knows only an inclusive pile-size range;
all other players are conservatively treated as a coalition trying to make
player 1 lose. The solver reports safe actions for every exact pile size, their
intersection across the information set, and the action with least worst-case
exposure when an absolute guarantee is impossible.

## Run the moving-worm solver

```bash
PYTHONPATH=src python -m aip worm --holes 5
```

The worm starts in any of five adjacent holes. After every unsuccessful check,
it must move exactly one hole left or right. A breadth-first search over belief
states proves that `2 → 3 → 4 → 2 → 3 → 4` is a shortest guaranteed sequence:
if all first five checks miss, only hole 4 remains possible at the sixth check.
The repeated sweep handles both possible starting parities.

## Architecture notes

`InformationSet[StateT]` is the extension seam for imperfect-information
puzzles. It records all states a player regards as possible, private
observations, public history, and optional Bayesian beliefs. Domain modules
provide the compatibility rule used to eliminate states after an observation.

The modules use the shared information interface without coupling their reasoning styles:

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
