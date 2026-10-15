# Five-die observation-stratification update — 2026-10-15

## Decision

Separately stratifying average-policy observations improves evidence coverage
without changing regret sampling. A frozen one-epoch dose pilot selected four
observation replicas, and a new-seed four-epoch paired confirmation passed every
mechanism gate. This validates the mechanism for a full-budget study; it does
not certify five-die GTO and runtime ε-GTO remains disabled.

## Mechanism

The original joint-marginal external-sampling traversal remains the only code
path that updates regrets and training visits. After each regret iteration, an
observation-only traversal uses:

- an independent RNG;
- separately shuffled exact five-die multinomial schedules;
- branching over the non-observed player's actions;
- policy sampling and average-strategy accumulation only for the observed
  opponent player.

Observation passes do not update regret or visit counts. Each replica contains
all 7,776 ordered five-die microstates per epoch for both private-hand roles, so
histogram frequencies retain their exact multinomial weights.

## Frozen dose pilot

| Observation replicas | Raw evidence coverage | Gain vs 21.30% baseline | Fallback | Exploitability | Training time |
|---:|---:|---:|---:|---:|---:|
| 1 | 24.14% | +2.83 pp | 75.86% | 0.27609 | 5.15 s |
| 2 | 25.81% | +4.51 pp | 74.19% | 0.27736 | 6.24 s |
| 4 | 27.85% | +6.55 pp | 72.15% | 0.28035 | 9.53 s |

All three doses preserved regret and visit traces and passed the schedule,
fallback, normalization and evaluator-identity checks. Returns diminished per
replica. None reached the pilot's 40% target, so the frozen selection rule chose
the highest-coverage dose, four replicas. The pilot remained explicitly
noncertifying.

## Bounded paired confirmation

The four-epoch confirmation used an unseen seed and trained candidate and
baseline from scratch.

| Metric | Paired baseline | 4-replica candidate |
|---|---:|---:|
| Positive-weight information sets | 23,198 | 28,486 |
| Raw observation coverage | 26.61% | 32.67% |
| Fallback fraction | 73.39% | 67.33% |
| Independent exploitability | 0.10059 | 0.10363 |

Coverage improved by 6.06 percentage points, exceeding the frozen 5-point
minimum. Exploitability increased by 0.00304 but remained inside the 0.02 paired
noninferiority allowance and below the bounded absolute ceiling of 0.15. The
candidate reproduced exactly and retained identical regret and visit traces.

## Interpretation

The experiment supports the causal claim that independent observation strata
increase average-strategy evidence without changing regret sampling. It does
not yet show that four replicas are cost-effective at the full horizon or that
fallback can reach the earlier certification ceiling of 40%.

A separate full-budget mechanism study is now frozen with 16 complete epochs
and a new seed. Its intermediate fallback ceiling is 65%, not a replacement for
the stricter certification gate. Even if that study passes, it cannot promote
runtime AI without a later certification experiment and completion of the
resumable full-tree audit.
