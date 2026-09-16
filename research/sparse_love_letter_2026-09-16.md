# Sparse LP and Love Letter certification boundary — 2026-09-16

## Dependency decision before implementation

SciPy is an **optional** extra (`aip-puzzles[sparse-lp]`, SciPy >=1.13,<2).
The base MIT project remains dependency-free. SciPy is BSD-licensed and its
HiGHS path accepts sparse LP matrices:
https://scipy.org/faq/ and
https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linprog.html.
Its compiled distribution and NumPy add binary-wheel download/storage cost;
unsupported platforms may need a substantially more expensive source build.
No package was installed today: the local environment already has SciPy 1.16.3.
The alternative remains the internal dependency-free simplex for tiny games.
There is no AGPL backend or poker-source dependency.

## What is fixed

`compile_sequence_form(..., sparse=True)` creates coordinate flow/payoff storage
without allocating the sequence-pair Cartesian matrix. Sparse compilation uses
an explicit nonzero budget instead of the dense-cell budget; history limits
remain mandatory. Optional SciPy imports are delayed until the backend is selected.

`solve_sequence_form(..., backend='scipy_highs', time_limit=60)` assembles CSR
constraints directly. Realization variables are nonnegative; LP dual variables
are free. Equality flow constraints remain equalities rather than duplicated
dense inequalities. Both seats are solved, then finite-value, flow-residual and
primal-dual-gap gates apply. Unsuccessful/time-limited backend output cannot be
converted into a policy. The solver is not the independent certifier.

Kuhn, E-Card and the four-card Love Letter subgame match the internal dense LP
value and pass the separate full-tree best-response oracle at the unchanged
1e-12 threshold. Love Letter subgame: value 0.16666666666666663, flow residual 0,
primal-dual gap 2.7755575615628914e-17, independent exploitability 0.

Both Python and public browser Love Letter sessions now explicitly expose:

- `strategyEvidence = heuristic`;
- `certificationStatus = full_round_not_independently_certified`;
- `epsilonGtoRuntimeAllowed = false`.

Requesting an epsilon-GTO mode for the complete game is rejected instead of
silently executing a heuristic. Existing default play remains compatible.

## What is not fixed, and why

A fresh structural audit of the **complete 16-card round** exceeded 1,000,000
histories after 44.38 seconds without finishing. This is a measured lower bound,
not an estimate of the complete tree size. No full sequence representation or
full-game best response has been completed. The scoped sparse LP result must
not be used to promote the full game or repeated-match runtime.

Sparse LP eliminates a matrix-allocation bottleneck, not extensive-tree growth
or information-set enumeration. Today therefore delivers the sparse backend and
runtime fail-closed labeling, but **does not claim full Love Letter GTO**.
Completing that goal requires bounded/checkpointed enumeration with compact
history/sequence IDs, measured total information-set/nonzero counts and resource
planning, followed by full independent best-response certification. Any symmetry
or abstraction shortcut requires a separate game-equivalence proof.

Reproduce: `PYTHONPATH=src python scripts/audit_sparse_love_letter.py`.
The artifact retains both success evidence for the subgame and the full-round
failure evidence in `research/results/sparse_love_letter_2026-09-16.json`.
