# Kuhn Poker modes and rules audit — 2026-08-26

## Scope

This update changes difficulty without changing the standard three-card Kuhn
game: both players ante one, bets cost one, cards rank `J < Q < K`, and the
player always occupies the second seat.  Keeping the seat fixed isolates AI
policy strength from Kuhn Poker's inherent positional value.

## Exact mode definitions

| Mode | AI policy | Evidence level | Second-seat best-response value | AI exploitability |
|---|---|---|---:|---:|
| Basic | Equilibrium opening bets, but Q calls only `1/3` after check-bet | Strong heuristic | `+1/6` chip/hand | `1/9` chip/hand |
| Advanced | Alpha-`1/3` Kuhn equilibrium | Equilibrium-backed | `+1/18` chip/hand | `0` |

All values include antes.  The solver exhausts all 64 pure behavioral best
responses for each seat.  It also evaluates complete behavior policies exactly
with rational arithmetic.  Advanced therefore has proved zero exploitability
inside this finite game model; Basic is intentionally, quantitatively
exploitable.

A GTO player earns the normal second-seat value `+1/18` against either mode.
To obtain Basic's larger `+1/6` value, the player must adapt to its Q under-call
rather than merely replaying the equilibrium mixture.  These are expectations
over repeated hands, not promises about any single deal or short match.

## UI and runtime contract

- Mode is passed when a session is created and returned in every snapshot.
- `strategyEvidence` distinguishes `strong_heuristic` from
  `equilibrium_backed`; `strategyScope`, `aiExploitability`, seat, and expected
  seat value remain machine-readable.
- Switching difficulty starts a fresh match and resets the score.
- Python, Worker, and zero-backend GitHub Pages runtimes implement the same
  policies and fixed second seat.
- AI cards remain private until a hand finishes.

## Cross-game wording check

The audit compared playable rules and UI claims with their current mechanisms:

- Guess Who and Kuhn Poker retain exact/verified claims scoped to their finite
  models.
- Restricted RPS and Goofspiel retain equilibrium-backed labels scoped to their
  implemented inventories and horizons.
- Mastermind, Battleship, Hidden Pursuit, Love Letter, E-Card, Liar's Dice, and
  investment advice remain described as bounded or strong heuristics where no
  global proof is present.
- Blackjack continues to scope basic-strategy optimality to its displayed deck
  and dealer rules and explicitly lists unsupported actions.

The only direct contradiction found was Kuhn Poker's old statement that seats
alternate.  It was corrected in the quick rules, full rules, first-turn guide,
position labels, and session engine.

## Reliability finding

Browser testing exposed a stale-process hazard: a long-running local Python
server could serve newly edited static files while retaining yesterday's game
classes in memory.  Health responses now carry API version `2`; a new launcher
will not mistake an older AIP process for the current compatible service.
