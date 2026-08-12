# AIP platform comparison — 2026-08-12

This review focuses on architecture that can improve AIP without turning a
small, dependency-free playable lobby into a research framework clone.

## Projects reviewed

### OpenSpiel

OpenSpiel separates a high-level `Game` description from a trajectory `State`.
Every state exposes legal actions, transitions, terminal status, and either an
observation or player information state. Its examples also treat seeded chance
events as explicit parts of a trajectory. See the official
[OpenSpiel concepts](https://github.com/google-deepmind/open_spiel/blob/master/docs/concepts.md).

**Useful for AIP:** keep descriptors separate from live sessions; make the
public state contract explicit; continue separating private model state from
the information shown to the player.

**Not adopted now:** a full extensive-form tree and explicit chance-player API
would add substantial machinery to casual single-player puzzles.

### PettingZoo

PettingZoo's Agent Environment Cycle makes turn ownership explicit and exposes
legal-action masks with observations or auxiliary information. Its documentation
also recommends a reusable API conformance test for every environment. See the
official [AEC API and action masking guide](https://pettingzoo.farama.org/api/aec/).

**Useful for AIP:** every playable snapshot should declare `legalActions`, and
one registry-wide contract test should cover old and newly registered games.
This prevents a renderer, AI, or future multiplayer adapter from guessing what
the current `phase` permits.

**Not adopted now:** Gym-style action and observation spaces would be excessive
for button-driven browser games until training external agents becomes a goal.

### Gambit

Gambit emphasizes documented game representations and interoperability between
its GUI, Python API, and command-line solvers. See the official
[Gambit project overview](https://www.gambit-project.org/) and
[representation documentation](https://gambitproject.readthedocs.io/en/stable/contents.html#game-representation-formats).

**Useful for AIP:** retain JSON-friendly public states and stable game IDs so
future replay/export tools can be added without coupling them to a renderer.

**Not adopted now:** exporting every puzzle to `.efg` is not generally possible
or useful; several AIP activities are adversarial search or Bayesian decision
experiments rather than small finite equilibrium problems.

## Changes selected for AIP

1. Require every public snapshot to contain a stable `gameId`, non-empty
   `phase`, and unique string `legalActions`.
2. Validate that contract at the Python service boundary and both hosted
   JavaScript boundaries, failing early when a future game plugin is malformed.
3. Cover every playable game dynamically in conformance tests, so adding a game
   to the registry automatically adds it to the audit.
4. Fix the discovered Python/public-engine mismatch for two-hole Moving Worm:
   both runtimes now support the solver's valid 2–12-hole range.

## Next candidates

- Add an optional serializable replay record: game ID, rules/options, seed,
  actions, and public observations.
- Add explicit `currentActor` only when multiplayer or asynchronous turns enter
  the public lobby.
- Consider a Gambit/OpenSpiel exporter only for finite games such as Kuhn Poker,
  E-Card, and restricted RPS, with parity tests against AIP payoffs.
