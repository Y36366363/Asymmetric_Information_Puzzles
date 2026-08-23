# Mastermind sampling audit — 2026-08-23

## Question

Can the bounded one-step adviser used by the four-digit Mastermind environment be
made measurably stronger without changing the game, inflating the benchmark, or
mislabeling a heuristic as an optimal policy?

The adviser filters the 5,040 legal hidden codes exactly after every feedback
observation. It then selects a guess lexicographically by:

1. minimum worst-case surviving candidate count;
2. minimum expected surviving candidate count;
3. preference for a currently possible secret;
4. deterministic digit order.

For medium belief states (161–800 candidates), the previous implementation
evaluated all surviving candidates plus 360 evenly spaced global probes. This
audit compares that bounded pool against all 5,040 legal probes after every
nonterminal feedback branch of the fixed opening guess `0123`.

## Exact one-step branch audit

There are 13 nonterminal feedback branches after `0123`. The 360-probe policy
matched the exact one-step objective on 10. Three branches exposed gaps:

| Feedback (exact, misplaced) | Candidates | 360 worst | Exact worst | 360 expected | Exact expected |
| --- | ---: | ---: | ---: | ---: | ---: |
| (1, 0) | 480 | 126 | 120 | 79.792 | 80.533 |
| (1, 1) | 720 | 170 | 148 | 121.111 | 107.556 |
| (1, 2) | 216 | 62 | 60 | 44.185 | 41.296 |

The first row illustrates the declared lexicographic objective: the exact
minimax action sacrifices a small amount of expected partition size to reduce
the worst case by six. A one-point sampling-phase change from 360 to 361 includes
an objective-equivalent exact probe in all three branches. The resulting policy
matches the complete one-step search on all 13 opening branches.

This is not a monotonic sample-size theorem. Even spacing at different sizes
changes the selected points, so a larger pool does not necessarily contain a
smaller pool. The value 361 is an evidence-backed correction for these audited
branches, not a general proof that 361 is universally sufficient.

## Deterministic policy simulation

Both policies were run on the same 200 evenly spaced secrets from the 5,040-code
world:

| Global probes | Solved | Mean attempts | Maximum | Seven-attempt cases |
| ---: | ---: | ---: | ---: | ---: |
| 360 | 200/200 | 5.295 | 7 | 10 |
| 361 | 200/200 | 5.245 | 7 | 6 |

The corrected sample lowered the mean by 0.05 guesses (about 0.94%) and reduced
seven-attempt cases by 40% on this fixed sample. This panel is deterministic but
not exhaustive. Its single-run wall-clock measurements (about 30.3 s and 35.2
s) are retained in the machine report for reproducibility, but are too noisy and
path-dependent to support a speed claim.

## Mechanism and benchmark implications

- Candidate-set belief ground truth remains exact.
- `suggest_exact` now exposes the complete legal-guess comparison for local
  one-step audits.
- The public browser adviser uses the same 361-probe policy as the Python model.
- The full multi-step adviser remains a **strong heuristic**. Exact one-step
  minimax partitioning does not prove a globally minimum expected or worst-case
  number of guesses.
- Mastermind remains useful as a held-out benchmark candidate because it offers
  exact belief truth and computable one-step regret without requiring a large
  general-game framework.

No paid model call was used. The full machine-readable branch and simulation
record is in
[`results/mastermind_sampling_audit_2026-08-23.json`](results/mastermind_sampling_audit_2026-08-23.json),
and the experiment can be repeated with
[`scripts/analyze_mastermind_sampling.py`](../scripts/analyze_mastermind_sampling.py).
