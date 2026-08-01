# AIP — Asymmetric Information Puzzles

## Updates 08/01/2026

- **Prisoners-and-light coordination** — Added safe designated-counter plans
  for known-off and unknown initial light states, reproducible random simulation,
  execution traces, and an explicit distinction between safety and finite-time completion.
- **Village eye-colour induction** — Added a configurable common-knowledge
  solver that identifies the simultaneous action night, exposes the day-by-day
  counterfactual reasoning, and demonstrates why a public announcement is essential.

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

The project currently solves pirate gold allocation, public coloured-hat and
village eye-colour reasoning, prisoners-and-light coordination, robust
sequential bean taking, and adversarial moving-worm search. Its shared core
remains ready for future puzzles.

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
│       ├── eyes/                  # village eye-colour induction
│       ├── prisoners/             # one-bit distributed coordination
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

## Run the village eye-colour solver

```bash
PYTHONPATH=src python -m aip eyes --target-count 3 --other-count 7 \
  --target-color white --other-color black
```

Assumptions: everyone sees everyone else's eyes but not their own; all villagers
are perfect reasoners; an outsider publicly announces that at least one person
has the target eye colour; and every night's actions are publicly observed. If
there are `N` target-colour people, nobody acts on nights 1 through `N-1`, then
all `N` target-colour people infer their colour on day `N` and act simultaneously
that night (in the stated puzzle, they die by suicide). Other-colour people do
not act under this rule.

The announcement is not redundant: it turns a visible fact into common
knowledge and supplies the induction's base case. Use
`--no-public-announcement` to show that no synchronized day is guaranteed.

## Run the prisoners-and-light solver

```bash
PYTHONPATH=src python -m aip prisoners --count 100 --initial off \
  --goal turned-on --seed 42
```

Before separation, prisoner 0 is designated as the counter. If the light is
known to start off, every other prisoner turns it on exactly once—the first
time they find it off—and otherwise does nothing. The counter turns it off and
increments a private count. At `N-1`, the counter can safely declare that all
non-counters have operated the light. For the literal `turned-on` goal in this
puzzle, the counter must additionally turn the light on personally before
declaring. The standard `--goal visited` variant omits this extra self-signal.

If the initial state is unknown, use `--initial unknown`. Every non-counter then
signals twice, and the counter waits for `2(N-1)` off-events. A possibly
initially-on light contributes at most one phantom count, which is insufficient
to cause a premature declaration. Use `--actual-initial-on` to simulate that
branch.

Under independent fair random selection the strategy completes with probability
1, but it has no finite worst-case deadline: a particular prisoner could be
skipped for an arbitrarily long time. Each simulated visit performs at most one
light operation, matching the puzzle's restriction.

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
- **Prisoners:** the light is a shared one-bit memory channel; local signal
  quotas and the counter's private state form a distributed protocol.

Puzzle solvers remain self-contained under `puzzles/<name>`, while shared state,
transition, and information abstractions stay dependency-free in `core`.

## Tests

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```
