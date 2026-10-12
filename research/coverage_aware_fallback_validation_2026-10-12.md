# Coverage-aware average-strategy fallback validation — 2026-10-12

## Decision

The separately preregistered fallback behaves as designed, and both Kuhn Poker
and one-die Liar's Dice pass the absolute independent exploitability ceiling of
`0.01`. The experiment nevertheless fails overall because both candidates miss
the frozen comparison guard against the legacy external-sampling estimator. No
five-die preregistration was created and no five-die training was run.

This is a negative result, not a reason to change the thresholds after seeing
the data. The previous 2026-10-11 coverage failure also remains unchanged.

## Frozen rule and evidence boundary

The new algorithm ID is
`coverage_aware_reach_weighted_external_sampling_mccfr_v1`. At each information
set it exports:

- the normalized own-reach-weighted average when cumulative weight is positive;
- the current regret-matching strategy only when cumulative weight is zero;
- a uniform current strategy when every current positive regret is zero.

Fallback use is reported per information set. It changes neither traversal nor
regret updates, and its observation-count and observation-weight maps exactly
match the reach-weighted control at the same seed. Resolved policy coverage is
reported separately from raw observation coverage: fallback makes a complete
policy available but does not manufacture training evidence.

## Results

| Game | Iterations | Raw positive-weight coverage | Fallback | Candidate exploitability | Reach-weighted | Legacy | Overall |
|---|---:|---:|---:|---:|---:|---:|---|
| Canonical Kuhn | 50,000 | 12/12 (100%) | 0/12 (0%) | 0.005751 | 0.005751 | 0.003499 | fail |
| One-die stepwise Liar's Dice | 100,000 | 194/348 (55.75%) | 154/348 (44.25%) | 0.003746 | 0.004464 | 0.000835 | fail |

Both profiles are complete and normalized, reproduce exactly at the fixed seed,
and use exact independent best responses for certification. In one-die Liar's
Dice the fallback improves exploitability relative to the reach-weighted
control by about `0.000718`, but remains about `0.002910` worse than legacy,
exceeding the preregistered allowed increase of `0.002`. Kuhn uses no fallback,
so its candidate equals the reach-weighted control; it is about `0.002252` worse
than legacy, also outside that guard.

The one-die candidate changes 83 exported policies, all inside the 154-node
fallback set. Some zero-weight nodes have positive observation counts because
they were traversed after an earlier action gave them zero own reach. That is
valid counting but not positive-weight average-strategy evidence.

## Interpretation and next step

The implementation is suitable as an explicitly labeled policy-completion
mechanism, but this run does not establish it as a uniformly superior estimator.
The most informative next experiment is not an immediate five-die run. It
should separately preregister whether the legacy estimator, reach-weighted
estimator, or a mixed estimator is the primary candidate, with multiple fixed
seeds and an aggregate endpoint. The current artifact and its failed comparison
gates must remain immutable as negative evidence.
