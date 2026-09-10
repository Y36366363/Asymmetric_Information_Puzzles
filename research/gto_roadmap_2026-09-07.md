# GTO implementation audit and roadmap — 2026-09-07

## Definition used in this project

`GTO` is reserved for a complete policy in a declared finite game that attains
the zero-sum minimax value (or an appropriate Nash equilibrium in a non-zero-sum
model). A good heuristic, one-step optimum, information-gain rule, or basic
strategy is not renamed GTO. The opponent must actually sample the audited
policy; displaying equilibrium advice beside a different AI is insufficient.

## Current audit

| Environment | Current evidence | GTO status | Appropriate next method |
| --- | --- | --- | --- |
| Kuhn Poker | Exact behavior policy plus pure best-response exploitability | Implemented | Keep exhaustive regression |
| Goofspiel (4 cards) | Backward induction and per-state zero-sum matrix games | Implemented | Keep exact best-response regression |
| Restricted RPS | Backward induction and per-state zero-sum matrix games | Implemented in this change | Enumerate certificates for larger inventory limits before expanding rules |
| Moving Worm | Deterministic guaranteed capture sequence | Optimal control, not GTO | Keep the more accurate label |
| Pirate Council | Backward induction under fixed voter assumptions | Subgame solution, not a mixed-strategy GTO opponent | Keep assumptions explicit |
| Guess Who / Mastermind | Exact or bounded information-search policies | Single-agent search, not GTO | Keep regret/information labels separate |
| Blackjack | Rule-scoped basic strategy | Decision optimum for the declared shoe model, not an opponent equilibrium | Add exact EV tables before expanding actions |
| E-Card | Exact single-round timing matrix plus precommitted cross-round heuristic | Single-round equilibrium solved; repeated adaptive mode not proved | Keep exact matrix primary and CFR as cross-check; separate modes before promotion |
| Liar's Dice | Five-die heuristic plus certified one-die stepwise CFR profile | Reduced ε-GTO implemented; full game not proved | Keep independent best-response regression; expand rules only under a new certificate |
| Love Letter | Public-belief heuristic | Not proved | Build the complete two-player finite tree, then use CFR/MCCFR with exploitability checks |
| Battleship / Hidden Pursuit | Belief and search heuristics | Not proved | Define smaller finite variants; full-size exact GTO is currently impractical |
| Investment tournament | Kelly and survival heuristics | Not proved | Specify utilities and opponent policies before attempting stochastic-game equilibrium |
| Cases of Fate | Risk-aware single-agent decision aid | GTO not applicable | Evaluate expected/risk-adjusted utility instead |

## Ordered delivery plan

1. Preserve the three exact small-game baselines: Kuhn, four-card Goofspiel, and
   Restricted RPS. Every GTO mode must report scope, evidence level, and zero
   exploitability, and its sampled action distribution must equal the audited policy.
2. The one-die, stepwise-bidding Liar's Dice benchmark is now implemented. Its
   frozen CFR profile is independently checked by exhaustive best responses and
   is exposed as ε-GTO only while its artifact passes the declared gate. Arbitrary
   jump raises and five-die play remain outside that certificate.
3. The frozen single-round E-Card timing model is now solved exactly and
   independently reproduced by CFR. Do not mix cross-round learning into that
   equilibrium claim; expose adaptive play as a separate mode if retained.
4. Attempt Love Letter only after its legal action tree, deck-removal rules,
   information sets, and terminal utilities are covered by exhaustive tests.
5. For full Battleship, Hidden Pursuit, and the investment tournament, prefer
   honest strong-policy labels until a tractable reduced game and an exploitability
   evaluator exist.

## Restricted RPS change made today

The Python service already solved continuation-aware minimax policies, but mixed
up to 32% of a history-based best response into actual AI play. The public browser
used remaining-inventory proportions as an equilibrium approximation. Both paths
now make the AI sample the backward-induction minimax distribution itself. Runtime
state exposes `strategyEvidence = equilibrium_backed`, zero exploitability, and a
named `subgame_perfect_minimax` execution policy.
