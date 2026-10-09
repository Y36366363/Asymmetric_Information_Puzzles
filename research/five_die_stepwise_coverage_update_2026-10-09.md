# Five-die stepwise coverage experiment — 2026-10-09

## Outcome

The coverage intervention worked, but the equilibrium gate did not pass. The
five-die stepwise candidate therefore remains research-only and runtime
ε-GTO remains disabled.

Before training, the experiment froze `seed=20261009`, a 25,200-iteration
budget, independent-best-response checkpoints at 5,000, 12,600 and 25,200,
a 50% real-visit coverage threshold and an exploitability ceiling of 0.05.
The failed 2026-10-08 5,000-iteration artifact was retained unchanged as the
negative-control baseline rather than being replaced by the larger run.

## Coverage intervention

The new traversal deterministically cycles through all 252 possible private
five-die histograms for each updating player. The opponent histogram continues
to be sampled from the exact multinomial chance distribution, so the opponent
model is not silently changed to a uniform distribution over histograms.

All 87,192 information sets are initialized with zero regret and a uniform
default policy. Initialization is not counted as coverage: the reported
coverage numerator includes only information sets with a positive traversal
visit count.

## Fixed convergence trace

| Iterations | Real visited information sets | Coverage | Exact exploitability |
|---:|---:|---:|---:|
| 5,000 | 27,339 | 31.355% | 0.441748 |
| 12,600 | 37,747 | 43.292% | 0.245807 |
| 25,200 | 44,140 | 50.624% | 0.146501 |

The old failed candidate visited 25,945 information sets (29.756%) and had
exploitability 0.391510. The new final checkpoint improves exploitability by
approximately 62.6% relative to that baseline and passes the preregistered
coverage threshold. It still fails the unchanged 0.05 independent gate by a
wide margin. Its player deviation gains are 0.134384 and 0.158617, giving
NashConv 0.293001 and exploitability 0.146501.

The 5,000-point result is also useful negative evidence: stratification gave
slightly more coverage than the old sampler at the same nominal budget, while
exploitability was initially worse. Coverage is therefore a necessary
diagnostic, not a substitute for equilibrium quality.

## Mechanism interpretation

The intervention preferentially guarantees exposure of the updating player's
private histogram. Under standard external sampling, average strategy is
accumulated at opponent nodes, whose private hand remains chance-sampled. Thus
regret coverage, average-policy coverage and independent exploitability need
not improve at the same rate. The exact best-response trace correctly detects
that difference; training regret was not used as a certificate.

A later experiment may preregister joint stratification or a coverage-aware
average-policy estimator, but it must be a new experiment with a new fixed
seed, budget and estimator proof. It must not reinterpret this failed candidate
after seeing the result.

## Structural boundary

The separate resumable tree audit advanced from 90,000 to 140,000 histories.
It now contains 35,425 observed information sets, 69,897 terminal histories and
304 frontier nodes, with no detected structural failures. The audit is still
incomplete; the frontier count is not a completion percentage.

Both required runtime gates remain closed:

1. independent exploitability is above 0.05; and
2. the complete structural audit has not closed.

The live arbitrary-raise five-die game is a different ruleset and remains a
transparent heuristic. No browser or local runtime strategy was changed.
