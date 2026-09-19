# Focused Love Letter and Liar's Dice algorithm validation

Date: 2026-09-19

## Scope and acceptance rule

This audit focuses on the current AIP mechanisms for the complete four-card
Love Letter late-round subgame and the complete one-die-per-player stepwise
Liar's Dice game. The complete 16-card Love Letter round is tracked separately
because its resumable structural traversal is not finished.

The acceptance source is always an independent best response. Training regret,
iteration count and information-set visits remain diagnostics and cannot replace
NashConv or exploitability. No web or runtime strategy was modified.

## Exact references

| Game | Histories | Information sets | Sequences per player | Value to player 0 | Exploitability |
|---|---:|---:|---:|---:|---:|
| Love Letter four-card subgame | 1,081 | 60 | 61 / 145 | 1/6 | 0 |
| One-die Liar's Dice | 4,141 | 348 | 343 / 343 | 1/2 | 0 |

Both policies were compiled from the audited adapters, solved with sparse
sequence-form LPs through SciPy/HiGHS, and checked by the independent full-tree
best-response layer. A second game-specific evaluator agrees on all five
equilibrium metrics. The uniform-policy negative controls have exploitability
`0.375` for Love Letter and `0.6030092592592593` for Liar's Dice, demonstrating
that the oracle is not returning zero indiscriminately.

## Deterministic CFR convergence

The following values are independently measured exploitability, not trainer
regret:

| Game | Algorithm | 10 iterations | 100 iterations | 300 iterations |
|---|---|---:|---:|---:|
| Love Letter | Vanilla CFR | 0.0375000 | 0.0037500 | 0.0012500 |
| Love Letter | CFR+ | 0.00681818 | 0.0000742574 | 0.00000830565 |
| Love Letter | DCFR (1.5, 0, 2) | 0.00135281 | 0.00000153933 | 0.0000000575821 |
| Liar's Dice | Vanilla CFR | 0.0781341 | 0.00781544 | 0.00260515 |
| Liar's Dice | CFR+ | 0.0430559 | 0.000468926 | 0.0000524491 |
| Liar's Dice | DCFR (1.5, 0, 2) | 0.0551613 | 0.000101145 | 0.00000378356 |

All six traces improve between the first and final checkpoint. DCFR is the best
300-iteration approximation in this experiment, but the exact sequence-form
solution remains preferable for both small games because it supplies a zero-gap
reference rather than only empirical convergence.

## Bugs found by the broader adapters

Kuhn's shallow tree did not expose a numerical discontinuity in DCFR. On the
deeper Liar's Dice tree, ordinary batch accumulation could leave a mathematically
zero regret infinitesimally positive or negative when chance outcomes were
reversed. DCFR then selected different positive/negative discount exponents and
the maximum policy difference grew to `0.4688759383` after ten iterations.

Full-tree traversal now uses a canonical order for chance outcomes and actions,
while retaining each adapter's declared action tuple in a separate consistency
table. Thus global enumeration order cannot alter updates, but two members of
one information set that declare different action tuples are still rejected.
Reversing chance or action enumeration now produces maximum policy difference
`0.0` for Vanilla CFR, CFR+ and DCFR on both focus games.

The focused audit also found that one-die external-sampling MCCFR with seed
`20260919` visited only 324 of the required 348 information sets after 20,000
iterations. Previously, its custom evaluator failed later with a raw missing-key
exception. It now validates exact coverage, legal actions, finite probabilities
and normalization before calculating value or best response, and rejects the
candidate with explicit evidence. This result does not mean external sampling is
incorrect; it means iteration count alone cannot certify full policy coverage.

## Sampling paths and release conclusions

- Love Letter's existing 20,000-iteration external-sampling result reproduces
  exploitability `0.00048442312519414443` and passes its four-card subgame gate.
- Liar's Dice root-chance sampling reproduces the frozen runtime fingerprint and
  exploitability `0.0023538635972168154`, passing its current `0.01` gate.
- Liar's Dice external sampling at the same nominal iteration count fails closed
  on missing coverage and is not an ε-GTO candidate.
- For one-die Liar's Dice, exact sequence-form should replace approximate CFR
  only in a separate runtime-integration milestone. This audit deliberately does
  not change the live policy.
- Complete Love Letter remains uncertified: its saved traversal is at 1,012,965
  histories and 148,226 information sets with 79 frontier nodes. It still needs
  a closed structural audit, a complete candidate solve and independent best
  response before any ε-GTO label.

The machine-readable evidence is in
`research/results/love_letter_liar_algorithm_audit_2026-09-19.json`.
