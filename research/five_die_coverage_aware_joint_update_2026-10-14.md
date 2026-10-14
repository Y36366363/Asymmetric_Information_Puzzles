# Five-die coverage-aware joint-stratified update — 2026-10-14

## Decision

The frozen five-die candidate completed all 124,416 iterations and passed its
independent exploitability endpoint, but failed both preregistered coverage
endpoints. The candidate therefore fails overall and runtime ε-GTO remains
disabled. No iterations were added after inspecting the result.

## What was tested

The candidate combines two independently audited mechanisms:

1. joint-marginal chance stratification, with each 7,776-iteration epoch
   reproducing the exact five-die multinomial marginal for both hands; and
2. the standard external-sampling average at observed information sets, with
   current regret matching used only when cumulative observation weight is zero.

Its algorithm ID is
`coverage_aware_joint_marginal_stratified_external_sampling_mccfr_v1`.
Fallback use is exported per information set and does not create observation
evidence. Short paired tests confirm that the new trainer preserves the old
joint trainer's regret, visit and observation traces.

## Frozen results

| Iterations | Visit coverage | Raw observation-weight coverage | Fallback fraction | Exploitability |
|---:|---:|---:|---:|---:|
| 62,208 | 55.04% | 28.22% | 71.78% | 0.063146 |
| 93,312 | 57.63% | 28.94% | 71.06% | 0.049610 |
| 124,416 | 59.63% | 29.49% | 70.51% | 0.040003 |

The final exploitability is below the frozen `0.05` ceiling and improves on
the retained `0.063834` joint-stratified result. The profile is complete and
normalized, the chance schedule is reproducible, and the fallback set exactly
equals the zero-observation-weight set.

However, only 51,996 of 87,192 information sets received a positive traversal
visit, below the required 65%. More importantly, 61,475 information sets still
needed fallback, far above the maximum 40%. Resolved policy coverage is not
treated as training evidence.

## Why visits and observation weight differ

Standard external-sampling MCCFR accumulates an average strategy when a node is
encountered on the sampled side of the alternating update. A node may therefore
receive regret-update visits when its player is being updated without ever
receiving positive average-strategy observation weight in the complementary
sampled traversal. Complete zero-regret initialization adds neither kind of
evidence. This explains why positive visit coverage reached 59.63% while raw
average-strategy observation coverage was only 29.49%.

The fallback makes those unresolved entries deterministic and auditable; it
does not solve the sampling-coverage problem.

## Next valid experiment

Do not extend this run. A future experiment should be separately preregistered
around the average-policy observation schedule, not another regret update rule.
The strongest candidate is paired stratification of the opponent-side private
histogram used for average-policy observations, while leaving regret sampling
unchanged and unbiased. Before another full five-die budget, it should prove on
one-die and a small five-die slice that:

- regret and best-response semantics remain unchanged;
- observation coverage increases without counting initialization as evidence;
- each observation stratum has the correct multinomial weight;
- exploitability remains independently certified;
- the prior failed artifact remains immutable.

The resumable complete-tree audit also remains unfinished at 200,000 explored
histories. Even a future candidate pass cannot enable ε-GTO until that separate
structural gate is complete.
