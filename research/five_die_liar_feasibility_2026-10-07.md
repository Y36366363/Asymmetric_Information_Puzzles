# Five-die Liar's Dice feasibility decision — 2026-10-07

## Why the live game should not enter tabular CFR directly

The current two-player browser mode gives each player five d6, treats ones as
wild for non-one claims, and permits any lexicographically higher bid. There are
60 bids: quantities 1–10 crossed with faces 1–6.

An arbitrary strictly increasing bid history is any nonempty subset of this
ordered ladder. The live rule therefore admits `2^60 - 1`, or about `1.15e18`,
public bid histories. Each player has 252 lossless five-die face histograms.
The resulting information-set lower bound is about `2.91e20` before adding
terminal histories. The existing exact/tabular pipeline must reject this route.

This is a structural resource result, not a statement that CFR theory fails.
External-sampling MCCFR could sample such a game, but a strict independent best
response over the unchanged tree would remain outside the current auditable
budget.

## Frozen stepwise candidate

A separately scoped rules contract now freezes:

- two players, five d6 each and wild ones;
- lossless private hand histograms;
- six legal quantity-one openings;
- thereafter only the next bid in the 60-position ladder or challenge;
- zero-sum ±1 terminal utility.

This produces 345 public bid chains rather than `2^60 - 1`, while retaining all
252 private hand types and 63,504 joint histogram chance outcomes. A direct
histogram-expanded tree is estimated at 43,881,265 histories and 87,192
information sets including pre-opening states. This is still substantial, but
it is finite, measurable and suitable for a resumable structural audit.

The chosen route is:

1. implement the separate stepwise adapter;
2. run a bounded resumable full-tree/information-set audit before training;
3. use fixed-seed external-sampling MCCFR as the initial candidate method;
4. build complete best response over histogram chance states;
5. attempt sparse sequence form only after measuring sequence/payoff size;
6. expose no ε-GTO label until the independent exploitability gate passes.

The live arbitrary-raise five-die mode remains a transparent heuristic. The new
contract does not inherit the one-die certificate and will not silently replace
the live rules.

The machine-readable contract is
`configs/five_die_liar_stepwise_rules_v1.json`; the feasibility artifact is
`research/results/five_die_liar_feasibility_2026-10-07.json`.
