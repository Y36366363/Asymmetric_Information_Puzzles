# Stopping-time compression and unified GTO pipeline — 2026-09-11

## Result

The proposed rule is valid after making its assumptions explicit:

> For a finite hidden-timing, inspection, or ambush game, first test whether every
> pure strategy is completely represented by a stopping time. If so, solve the
> resulting complete payoff matrix exactly and use CFR only as a cross-check.

The genre label is not enough. Compression is admitted only when:

1. private information is fixed at the start;
2. no new private observation arrives during play;
3. continuation before stopping is forced rather than strategically chosen;
4. terminal payoff depends only on both stopping times; and
5. the horizon is finite and the entire stopping-time matrix is enumerated.

`audit_stopping_time_compression` now checks these conditions and returns
machine-readable failure reasons. This is an auditable structural declaration,
not an automatic theorem prover: each adapter still needs game-specific tests
showing that its declaration matches its rules and transitions.

## Positive and negative controls

Single-round E-Card passes. Each seat chooses the duel in which to play its one
special card, earlier rounds contain no other choice or observation, and payoff is
fully determined by the two selected times. Its complete strategic form is the
existing 5×5 zero-sum matrix. Exact minimax is therefore stronger and cheaper than
CFR; vanilla CFR remains useful only as an independent numerical cross-check.

Two-player Love Letter fails all four information/payoff compression conditions:

- a player's private hand is not fixed for the whole round;
- a fresh private card is drawn at the beginning of later turns;
- each turn contains a card/action/target/guess choice rather than forced waiting;
- elimination, protection, forced Countess play, deck exhaustion, and hand-value
  comparison cannot be reconstructed from two stopping times.

An executable regression also drives the current Love Letter engine through a
later turn and verifies that the AI's hand changes from one private card to two.
Consequently, a stopping-time matrix would merge strategically different histories
and is not a valid representation of Love Letter.

## External-sampling MCCFR validation

The reusable engine now implements two-player external-sampling MCCFR. For each
updating player it traverses all of that player's actions, samples chance outcomes
wherever they occur, and samples one opponent action per reached information set.
It accumulates the standard simple average strategy at opponent information sets.

Two tests distinguish algorithm support from a game-specific claim:

- A purpose-built game places a private chance signal after player zero's action.
  Two seeded 50,000-iteration runs are identical and the resulting profile has
  analytic exploitability below `0.03`.
- On canonical Kuhn Poker, 50,000 iterations with seed 7 cover all 12 information
  sets, visit each at least 1,970 times, and reach maximum exploitability
  `0.003770074` under the project's separate exhaustive best-response evaluator.

This is evidence that the generic sampler works on small perfect-recall games with
later chance nodes. It is **not** evidence that the current Love Letter heuristic is
GTO. Love Letter still needs a complete extensive-form adapter and a separately
implemented best-response/NashConv oracle before any ε-GTO policy may be activated.

The implementation follows the external-sampling structure introduced by
[Lanctot et al.](https://proceedings.neurips.cc/paper/2009/file/00411460f7c92d2124a67ea0f4cb5f85-Paper.pdf)
and was compared with
[OpenSpiel's external-sampling MCCFR implementation](https://github.com/google-deepmind/open_spiel/blob/master/open_spiel/algorithms/external_sampling_mccfr.cc).
The fail-closed perfect-recall requirement is retained because the usual CFR
guarantee depends on it; see
[Lanctot et al., No-Regret Learning in Extensive-Form Games with Imperfect Recall](https://icml.cc/2012/papers/58.pdf).

## Unified mechanism

The project can use GTO testing and inference as a central mechanism, but not as a
single universal solver. The reusable pipeline is:

1. **Declare eligibility.** Require a finite, two-player, zero/constant-sum,
   perfect-recall model. Route other games to a method appropriate to their actual
   objective rather than forcing a GTO label.
2. **Audit representation.** Try stopping-time compression first when plausible.
   Otherwise retain the complete extensive form and test information-set identity,
   legal-action consistency, chance probabilities, and terminal utility.
3. **Choose the strongest practical solver.** Prefer an exact matrix for complete
   stopping-time reductions, sequence-form LP for small perfect-recall trees,
   vanilla CFR for manageable trees, and external-sampling MCCFR when later chance
   or tree size makes full traversal unattractive.
4. **Use an independent oracle.** Measure both players' best-response gains/NashConv
   with code separate from the trainer. Training regret alone is diagnostic, not a
   certificate.
5. **Apply one promotion gate.** Check game assumptions, complete information-set
   coverage, visit counts, finite normalized probabilities, regret diagnostics,
   and independently measured exploitability against a declared ε.
6. **Freeze and activate exactly that policy.** The live AI may be called ε-GTO only
   if it samples the certified artifact without an unreported heuristic overlay and
   without exposing private strategy information during play.
7. **Regress scope and parity.** Test seeds, runtime/browser parity, artifact hashes,
   and rule scope. A certificate for a reduced game never transfers to a larger one.

The new `recommend_equilibrium_solver` function implements the first routing layer.
It sends E-Card to an exact matrix with vanilla CFR cross-check, Love Letter to
external-sampling MCCFR with sequence-form as the intended exact comparator, and
rejects multiplayer general-sum games from this two-player pipeline.

## Next Love Letter milestone

Before training, enumerate the full two-player round state: remaining multiset,
burned card, both hands, public discards, protection, whose turn it is, legal card
effects and targets, public observations, and terminal utility. Prove information
sets do not contain unavailable opponent/deck information, cover every rule branch,
and add an independent pure-best-response traversal. Only after that evaluator and
the existing promotion gate pass should the runtime expose an ε-GTO Love Letter AI.
