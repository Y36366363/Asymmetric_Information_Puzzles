# Guess Who duel boundary and solver regression — 2026-09-30

## What the current Guess Who actually solves

The shipped 24-character Guess Who solver has a hidden state, but only one
decision-maker: the secret is sampled uniformly and all answers are fixed and
truthful. Its exact dynamic program minimizes expected (or worst-case) question
count for that declared roster and eight-question bank. There is no opponent
policy, profitable unilateral deviation, or Nash equilibrium to certify. It is
an exact partially observed search task, not a two-player strategic GTO result.
For that task the existing exact expected policy remains at 5.667 turns
including the final guess (worst case six). This is a useful information-gain
control, but a narrow GTO research target.

## Bounded adversarial prototype

The new `GuessWhoDuel` is deliberately a different, limited rule set. Both
players privately choose a character and privately commit to a priority order
for truthful yes/no questions. Each asks simultaneously; uninformative
questions are skipped, and the final guess takes a round. The first to identify
the opponent wins; simultaneous identification is a draw. A pure strategy is
`(own secret, question priority order)`, so choosing a hard-to-find own secret
is a genuine defensive choice. The current audited instance uses Ada, Hugo,
Nico, three hair questions, and all six priority permutations: 18 pure actions
per player. The complete 18×18 payoff matrix is solved by a dependency-free LP;
the independent certificate enumerates all pure best responses to each solved
mixed strategy. It does not use training regret as an exploitability proxy.

The exact value is zero, `NashConv/2 < 1e-8`, and the secret marginal is 1/3
for each character. In contrast, pure maximin is -1 while pure minimax is +1:
no fixed secret-plus-question plan is a saddle point. This is real, albeit small,
mixed-strategy interaction. It does **not** certify the full 24-character game,
adaptive question policies, sequential timing, adversarial or false answers,
or any browser/runtime ε-GTO label. Reversing action enumeration leaves the
value and best-response gate unchanged.

The next design decision should be made before expanding the tree: keep truthful
answers and add adaptive questioning with explicit timing, or introduce a
costed defensive action such as shielding/obscuring a feature. Simply allowing
both players to choose a secret creates a finite hide-and-search game, but its
interaction is mostly pregame selection; it need not justify a large CFR tree.
For either variant, first audit information sets and perfect recall, then
compare a small exact matrix/sequence-form solution against CFR/DCFR and an
independent best response. Do not promote this restricted certificate to the
existing game.

## Other game gates checked today

The frozen PokerCapabilityLab Kuhn comparison at 10,000 iterations passes all
nine value, exploitability and convergence-trace checks. Independent
exploitability (`NashConv/2`) is 0.00011332446 for Vanilla CFR, 0.00000962319
for CFR+, and 0.00001234705 for DCFR (1.5, 0, 2). All values remain near the
canonical -1/18. This is a regression and cross-method comparison, not a claim
that DCFR must outperform CFR+ on every game or iteration budget. Exact
one-die Liar's Dice and the Love Letter subgame retain their existing scoped
independent-evaluation tests; no new runtime labels were enabled.

The full-round Love Letter structural checkpoint was advanced by two bounded
10,000-history chunks. Its latest cumulative state is 1,372,853 histories,
197,617 information sets, 75 frontier nodes, no structural failures, and
`complete=false`. This is still prefix evidence, not a complete tree or GTO
certificate. Full-round runtime ε-GTO remains disallowed. The four-card
late-round subgame remains a separate certified scope.

Solver routing remains scope-dependent: keep exact dynamic programming for the
original Guess Who search task, LP plus independent best response for the tiny
duel, exact sequence form for one-die Liar's Dice and the four-card Love Letter
subgame, and exact dynamic matrices for four-card Goofspiel. Vanilla/CFR+/DCFR
are useful convergence comparators on Kuhn, not automatic upgrades to an
already exact solution. Full-round Love Letter is not ready for a DCFR-vs-CFR
GTO claim while its state tree and independent best response remain incomplete.

Reproduce the finite duel with `PYTHONPATH=src python3
scripts/audit_guess_who_duel.py`; the numerical record is
`research/results/guess_who_duel_audit_2026-09-30.json`. The Kuhn numerical
record is `research/results/regret_minimization_check_2026-09-30.json`.
