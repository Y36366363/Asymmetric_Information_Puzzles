# Five-die stepwise adapter and MCCFR pilot — 2026-10-08

## Implemented scope

The independent `five_die_liar_two_player_stepwise_v1` adapter now implements
the frozen rules without altering the live arbitrary-raise game:

- two players with five d6 each;
- ones wild for claims on faces 2–6;
- all 252 lossless sorted face-count histograms per player;
- six quantity-one openings;
- thereafter challenge or advance exactly one step on the 60-bid ladder;
- zero-sum ±1 challenge utility;
- information sets containing only own histogram and public bid history.

Chance is represented in two 252-outcome layers. This preserves the exact joint
distribution while letting external-sampling MCCFR draw each private hand
without scanning 63,504 joint outcomes every iteration.

The executable tree has an expected 43,818,013 histories and 87,192 information
sets. This corrects the earlier conservative estimate that counted a dealt
decision state twice.

## Resumable structural audit

The new SQLite-backed audit has processed 90,000 histories and observed 22,834
information sets at maximum depth 63. It has no detected failures and 378
frontier nodes. This is useful progress, not a certificate:

- `complete=false`;
- `structural_audit_passed=false`;
- `equilibrium_certified=false`.

The frontier count describes the depth-first work stack and is not a completion
percentage.

## Preregistered external-sampling candidate

Before training, the pilot froze:

- algorithm: external-sampling MCCFR;
- seed: `20261008`;
- iterations: 5,000;
- independent exploitability gate: `0.05`;
- unvisited information sets: explicitly completed with uniform behavior;
- training regret: never accepted as a certificate.

The sampler directly visited 25,945 of 87,192 information sets, or 29.76%.
Uniform completion supplied the remaining 61,247 sets so the independent oracle
could evaluate a complete behavioral profile rather than silently omit states.

## Independent best-response result

The new oracle traverses every own five-die histogram against all 252 opponent
histograms and optimizes a consistent action at every information set. It does
not inspect MCCFR regrets or visits and returned action values for all 87,192
information sets.

| Metric | Result |
|---|---:|
| Expected value to player 0 | 0.454033 |
| Player 0 deviation gain | 0.361928 |
| Player 1 deviation gain | 0.421091 |
| NashConv | 0.783020 |
| Exploitability | 0.391510 |
| Preregistered gate | 0.05 |

The candidate fails decisively. Both seats have large profitable deviations;
this is not merely asymmetric first-player noise. Runtime ε-GTO remains false.

## Next decision

The five requested mechanism layers now exist: adapter, resumable audit,
fixed-seed MCCFR candidate, complete histogram best response and a fail-closed
promotion gate. The strategy itself is not ready.

The next experiment should not simply relabel 5,000 iterations. It should first
improve coverage—for example stratified private-hand sampling or an explicit
full information-set initialization—then preregister a convergence trace and a
larger fixed budget. Structural auditing can proceed independently in bounded
chunks. No runtime integration is justified until both structural completion
and independent exploitability pass.

Separately, the full-round Love Letter audit advanced by another 20,000
histories to 1,561,622 histories, 702,465 terminals and 223,324 observed
information sets. It has no recorded structural failures but remains incomplete
with 70 frontier nodes; its runtime ε-GTO boundary is unchanged.
