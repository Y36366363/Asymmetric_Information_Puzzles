# Programmed positive control and 30-state Liar experiment — 2026-09-24

## Outcome

The redesigned manipulation check passed, so the preregistered 30-state,
four-condition experiment ran. The main abstract-memory result was inconclusive
and the full experiment missed its repeatability quality gate. It does not
support a positive transfer claim.

No runtime strategy, ε-GTO label, or game certification changed. Full Love
Letter remains uncertified. The existing Goofspiel exact adapter remains the
next horizontal engineering target, but this result does not authorize a new
model-level transfer claim for Goofspiel.

## Why the positive control changed

The 2026-09-23 same-game example prompt improved exact-best-action accuracy from
66.7% to 83.3%, but missed its frozen 85% gate by one decision. Its errors were
concentrated in states where the exact oracle says to raise and the model instead
defaults to challenge.

The replacement is an explicit reusable decision program. Given only a legal
one-die Liar's Dice information set, it:

1. loads the independently solved exact equilibrium;
2. recomputes conditional action values through the independent evaluator;
3. returns every utility-maximizing legal action;
4. marks its output `manipulation_control_only`.

This is deliberately an oracle-assisted instruction-following control. It tests
whether a valid strategic signal can reliably change the model's action. It is
not same-game learning, abstract memory, autonomous reasoning, or GTO evidence.

## Fresh manipulation check

The check used 12 states from the frozen 30-state invariant panel that had not
appeared in the prior model run. It retained six challenge-optimal and six
raise-optimal states, two repeats, exact provider-token balancing, one attempt
per cell, and failure penalties. The preregistration SHA-256 was
`11f07602addf85c1b53ec3df8241adc79b5e85faf0b06d7bff9795620d5f87d6`.

| Metric | No memory | Oracle-assisted control |
|---|---:|---:|
| Valid decisions | 24 / 24 | 24 / 24 |
| Exact-best-action rate | 83.3% | 100.0% |
| Repeat action agreement | 83.3% | 100.0% |
| Mean exact conditional regret | 0.2292 | 0.0000 |

All frozen gates passed: valid outputs, exact token matching, at least 80%
repeatability in both groups, at least 95% assisted accuracy, at least a
15-point accuracy lift, and lower assisted regret.

## Four-condition 30-state experiment

The main preregistration SHA-256 was
`ff669033b41b6253384e909a4c9705b31ee7825d7e4d9c4ec4bc8cf43a6c1003`.
It contained all 30 states, four conditions, two repeats, and 240 total cells.
All 240 outputs were valid and every within-state condition had the same exact
provider-counted input-token total.

| Condition | Exact-best rate | Mean regret | Repeat agreement |
|---|---:|---:|---:|
| No memory | 73.3% | 0.3733 | 80.0% |
| Oracle-assisted same game | 100.0% | 0.0000 | 100.0% |
| Surface experience | 66.7% | 0.5011 | 86.7% |
| Abstract memory | 70.0% | 0.4639 | 73.3% |

The preregistered primary comparison was abstract memory minus no memory on
paired exact conditional regret:

- mean difference: **+0.0906** (positive is worse);
- fixed-seed paired-bootstrap 95% interval: **[-0.0917, +0.2800]**;
- interpretation: **inconclusive**.

Surface experience was also inconclusive: mean difference +0.1278, interval
[-0.0372, +0.3044]. The same-game control showed a clear benefit, but that is
expected because it contains the exact program output and is excluded from all
transfer claims.

The abstract arm's 73.3% repeat agreement failed the preregistered 80% quality
gate. Accordingly, the primary result is a quality-limited null result. It is
neither evidence of benefit nor sufficient evidence of negative transfer.

## Diagnostic interpretation

The important residual failure is action asymmetry:

- no memory chose all challenge-optimal states correctly, but only 46.7% of
  raise-optimal decisions correctly;
- abstract memory reached 96.7% on challenge-optimal decisions, but only 43.3%
  on raise-optimal decisions;
- surface records increased challenge selection further and reached only 33.3%
  on raise-optimal decisions.

The current abstract memo therefore does not overcome the model's conservative
challenge bias. Adding more prose or more superficially similar records is not a
promising immediate fix.

## Recommended next method

Separate policy competence from natural-language memory transfer:

1. retain the exact decision program as a calibration ceiling only;
2. replace free-form strategic advice with a compact, executable intermediate
   representation—posterior estimate, challenge value, raise continuation
   value, then action—whose arithmetic fields can be scored independently;
3. preregister correctness and repeatability for each intermediate field before
   another end-to-end transfer run;
4. use the existing exact Goofspiel adapter to test whether the same
   value-decomposition interface generalizes to simultaneous secret bidding;
5. keep Kuhn Poker as the second adversarial target and E-Card as a solver-only
   control;
6. do not expand the game set or certify full Love Letter until these mechanism
   checks are stable.

This route tests a shared strategic computation rather than whether a model can
imitate broad verbal advice. It also localizes failures: belief update,
continuation value, comparison, or final action selection.
