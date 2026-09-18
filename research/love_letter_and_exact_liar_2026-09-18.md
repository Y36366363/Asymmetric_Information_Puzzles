# Love Letter full-round progress and exact one-die Liar's Dice

Date: 2026-09-18

## Outcome

The full Love Letter round remains **uncertified**. Today's work improves the
bounded, resumable complete-tree audit and advances its real checkpoint from the
previous 18,998-history run to 796,904 histories. The current prefix contains
357,901 terminal, 211,406 chance and 227,597 player-decision histories, covers
114,711 information sets, reaches depth 26, and has no detected consistency,
probability, utility, cycle or perfect-recall failures. Seventy-six frontier
nodes remain, so partial success is not accepted as a complete structural audit
and cannot support an equilibrium claim.

The principal speed fix is semantic-preserving: information-set records are
loaded into memory when a chunk opens, new records receive stable IDs there,
and SQLite inserts are committed in a batch with the frontier. Replays no longer
perform one database lookup at every player node. The transaction rollback path
also restores all in-memory state, so a failed chunk cannot get ahead of its
durable checkpoint.

## Exact cross-check on another game

The common audited adapter and sparse sequence-form path now solve the complete
one-die, one-die-per-player Liar's Dice game. The compiled representation has
4,141 histories, 348 information sets, 343 realization sequences per player and
2,052 nonzero payoff entries. SciPy/HiGHS returns player 0 value `0.5`, zero
reported primal-dual gap and zero maximum flow residual. The independent
full-tree best-response evaluator also reports NashConv and exploitability of
zero. This is strictly stronger than the existing frozen CFR policy's measured
exploitability of `0.0023538635972168154`.

The exact result is stored as a local frozen research artifact, not silently
installed into the live game. The current runtime strategy and browser build are
unchanged, in accordance with the rule that web integration follows completed
testing.

## Certification boundary

Love Letter has only passed a large prefix of its structural audit. Completion
still requires closing the frontier, compiling or otherwise solving the complete
audited game within declared resource limits, and passing an independent best
response evaluation on the exact candidate profile. The already certified
four-card late-round subgame remains valid but is not evidence for the complete
round. No threshold was relaxed and no training regret was used as a substitute
for independent exploitability.

SciPy remains an optional `sparse-lp` dependency (BSD-3-Clause; compiled wheel
and larger installation footprint). No new dependency was introduced today.
