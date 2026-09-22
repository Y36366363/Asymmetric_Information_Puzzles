# Cross-game transfer methodology gap audit (2026-09-22)

## Decision

**Optimize the current method before adding another primary efficacy game.**

The infrastructure is now reliable, but only three of seven methodology gates
pass. The completed Liar's Dice experiment has complete outputs and exact token
matching; however, its same-game positive control does not discriminate from
the no-memory condition, two conditions miss the repeat-stability threshold,
one selected action label is reference-profile sensitive, and beneficial
abstract transfer has not replicated across Guess Who and Liar's Dice.

This does not prevent parallel engineering of the next adapter. It does mean a
new model experiment should not begin until the current manipulation and probe
selection gates pass.

One repair was completed during this audit: the new consensus selector examined
61 discriminating candidate information sets against all three reference
profiles and froze a 30-probe successor panel. It contains 15 challenge-optimal
and 15 raise-optimal states, including five player-1 raise decisions; every
selected label agrees across the three profiles and has a minimum action-value
gap of at least `0.25`. Its artifact also records opponent reach separately for
each reference profile. No model calls were made on this successor panel.

## What passes

- The Liar's Dice run completed all 96 preregistered cells.
- All 96 outputs were valid.
- All provider-reported input token counts exactly matched the preregistration.
- Exact sequence form, frozen runtime CFR and deterministic DCFR profiles all
  pass their existing whole-game independent-evaluation expectations:
  exploitability is `0`, `0.00235386` and `0.00000378356`, respectively.

These results show that the runner, token control, failure accounting and
whole-game evaluator are suitable foundations.

## Newly identified oracle weakness

The 12 probe labels were recomputed against three reference profiles: the exact
sequence-form solution, the frozen runtime CFR policy and 300-iteration DCFR.
Eleven probes retained the same best action. `liar-probe-02` did not:

| Reference profile | Best action | Local action-value gap |
|---|---|---:|
| Exact sequence form | challenge | 1.000000 |
| Frozen runtime CFR | raise to 2×face 4 | 0.510816 |
| DCFR 300 | raise to 2×face 4 | 0.999999 |

The important lesson is that very low whole-game exploitability does not imply
stable conditional action labels at every information set. A future benchmark
must require agreement across accepted reference profiles, not merely choose
one equilibrium artifact and treat every local argmax as canonical.

The original preregistered result remains unchanged. A clearly post-hoc
sensitivity analysis removing the unstable probe leaves 11 independent probe
clusters. Abstract memory then changes from `+0.006944` to `−0.037879`, with a
95% cluster-bootstrap interval of `[-0.265152, 0.212121]`. It remains
inconclusive, so the scientific conclusion does not change.

## Remaining experimental weaknesses

1. **The positive-control manipulation failed.** Same-game records changed
   mean regret by only `−0.013889`, with an interval spanning substantial harm
   and benefit. Without a positive control, a null abstract-memory result may
   mean either “no transfer” or “the memory intervention was too weak.”
2. **Too few independent states.** Two repeats do not turn 12 probe states into
   24 independent observations. Using probe-cluster variation, an exploratory
   normal approximation suggests about 26 independent probes for an absolute
   abstract-memory effect of `0.25`, and about 29 for the surface arm. A future
   plan should use at least 30 robust probes and replace this approximation with
   a preregistered simulation-based power calculation.
3. **Repeat stability is uneven.** No-memory and same-game action agreement are
   91.67%, but abstract memory is 75% and surface experience 66.67%, below the
   proposed 80% gate.
4. **Only one model alias has been tested.** There is no cross-model or dated
   snapshot replication, and the API does not supply a sampling seed for these
   runs.
5. **The abstraction procedure remains investigator-authored.** Source records
   are now mechanical and fingerprinted, but the domain-neutral memo is still a
   curated transformation. A confirmatory study should freeze an independently
   specified transformation procedure.
6. **Belief outputs do not discriminate conditions.** All Liar's Dice arms have
   posterior Brier distance near `0.493`; improving action formatting alone is
   not improving opponent beliefs.
7. **Cross-target replication is absent.** Guess Who's abstract contrast was
   numerically beneficial but failure-driven and inconclusive; Liar's Dice was
   numerically neutral/slightly harmful and inconclusive.

## Horizontal game decision

The next engineering target should be **four-card Goofspiel**, but only as an
adapter and oracle-readiness milestone until the current gates pass. It already
has an exact dynamic equilibrium and adds a genuinely different structure:
simultaneous hidden commitment with public inventories, rather than sequential
bidding under private dice. Required work is a completion adapter plus a
profile-invariant per-state action-regret audit.

Kuhn Poker is the second choice. Its exact sequence form and exhaustive best
response make it immediately auditable, and it is useful for bluffing
replication, but its sequential adversarial structure overlaps more with
Liar's Dice and with PokerCapabilityLab.

Single-round E-Card should remain an exact solver/control case: all five timing
actions have equal equilibrium action value, so it has little discrimination
as a one-decision agent benchmark. Mastermind remains secondary because its
decision oracle is heuristic. Full Love Letter remains blocked and must not be
used as a certified target.

## Next milestone

Before another efficacy run:

1. use the newly generated 30-probe consensus panel and preserve its audit;
2. replace four generic same-game examples with stratified, mechanically
   selected examples and run a small positive-control-only manipulation check;
3. require at least 80% repeat action agreement before the main comparison;
4. preregister a cluster-aware power calculation;
5. only then run the four transfer arms and begin the Goofspiel horizontal
   comparison.

The machine-readable evidence is
[`transfer_methodology_audit_2026-09-22.json`](results/transfer_methodology_audit_2026-09-22.json).
No runtime AI, GTO label, certification gate or web game was changed.
