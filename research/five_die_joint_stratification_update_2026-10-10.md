# Five-die joint-stratification experiment — 2026-10-10

## Result

Joint marginal stratification substantially improved the five-die stepwise
candidate, but the frozen experiment failed both primary gates. It is not an
ε-GTO strategy and no runtime policy or label changed.

The experiment was preregistered separately from the 2026-10-08 and 2026-10-09
runs. Both earlier failed artifacts remain intact. Before training, this run
froze `seed=20261010`, 62,208 iterations, checkpoints at 7,776, 31,104 and
62,208, a 60% real-visit coverage threshold, and the unchanged independent
exploitability ceiling of 0.05. The existing uniform-iteration average-policy
estimator was not changed.

## Why the strata use 7,776 microstates

The 252 five-die histograms are not equally likely. Enumerating every histogram
once would overweight rare hands. One epoch instead contains every one of the
`6^5 = 7,776` equally likely ordered five-die outcomes, compressed losslessly
to its histogram. Each updating-player traversal receives independently seeded
permutations for its own and opponent hand.

The schedule audit checked 32 hand schedules across eight epochs. Every one had
the exact true multinomial histogram multiplicities. Random pairing is an
unbiased stratification of both marginals; it is deliberately not described as
exhaustive enumeration of all 63,504 histogram pairs.

## Frozen convergence trace

| Iterations | Complete chance epochs | Real visited sets | Coverage | Exploitability |
|---:|---:|---:|---:|---:|
| 7,776 | 1 | 31,305 | 35.904% | 0.278456 |
| 31,104 | 4 | 42,453 | 48.689% | 0.110165 |
| 62,208 | 8 | 47,473 | 54.447% | 0.063834 |

The final exploitability is 56.4% lower than the retained 2026-10-09 result
(`0.146501`) and the trace is monotonically improving. Nevertheless:

- coverage is below the preregistered 60% threshold;
- exploitability is above 0.05;
- player deviation gains remain `0.057729` and `0.069939`;
- NashConv is `0.127668`.

The near miss cannot be converted into a pass by increasing this experiment's
budget after observing the result.

## Other validation

The five-die resumable structural audit advanced from 140,000 to 200,000
histories. It now observes 44,192 information sets and has no recorded failure,
but remains incomplete. Entering another second-hand chance branch increased
the frontier, confirming again that frontier size is not completion progress.

The independent full-round Love Letter audit advanced from 1,561,622 to
1,581,622 histories and 226,815 observed information sets. It has no recorded
structural failure but remains incomplete with 76 frontier nodes. Full Love
Letter therefore remains uncertified and its runtime remains heuristic-only.

## Next valid experiment

The next step should not be a post-hoc extension of 62,208 iterations. First,
instrument average-strategy observations separately from regret-node visits and
audit the estimator against Kuhn, one-die Liar's Dice and exact small-game
policies. If a different reach-weighted or coverage-aware estimator is proposed,
freeze its formula, small-game acceptance tests, seed, budget and five-die gates
in a new preregistration before running it. Joint marginal stratification can be
retained as a separately tested traversal component.
