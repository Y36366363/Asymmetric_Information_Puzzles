# Frozen Guess Who rules and preregistered signaling test — 2026-10-03

## Frozen rule boundary

The strategic three-character Guess Who rules are now frozen as
`strategic_guess_who_simultaneous_v1`. The machine-readable contract fixes:

- two-player zero-sum win/draw/loss utility;
- private simultaneous secret selection represented by hidden sequential nodes;
- simultaneous ask-or-guess rounds;
- truthful binary answers revealed only after both actions commit;
- an immediately winning correct unilateral guess and immediately losing wrong
  unilateral guess;
- draw resolution when simultaneous guesses have equal correctness;
- no automatic terminal merely because a public candidate set is a singleton;
- zero question cost and rejection of already uninformative questions.

The implementation contract is compared byte-for-value with
`configs/strategic_guess_who_rules_v1.json` in regression tests. This freezes
the game semantics, not the 24-character game and not a runtime strategy label.

## Preregistration

Before evaluating the new equilibrium outcome, the experiment fixed:

- roster: Ada, Bruno and Hugo;
- questions: black hair, brown hair, glasses and hat;
- structural asymmetry: the useful questions isolate the identities with
  multiplicities 1, 1 and 2;
- primary endpoint: maximum, within either seat, of the L1 distance between
  opening policies conditioned on different protected private identities;
- positive threshold: `1e-6`; zero-result threshold: `1e-8`;
- validity gate: exact sparse sequence form plus independent full-tree best
  response with exploitability at most `1e-10`;
- CFR/CFR+/DCFR cross-check budget: 3,000 iterations and exploitability at most
  `0.001`;
- mandatory retention of positive, zero and ambiguous outcomes.

The preregistration is stored at
`configs/guess_who_signaling_preregistration_2026-10-03.json`.

## Primary result: valid zero signal

The asymmetric game has 3,397 histories, 1,897 terminal histories, 1,000
information sets and maximum depth eight. Its sparse sequence form has 689
sequences per player and a 689×689 payoff matrix with 1,244 nonzero entries.
SciPy/HiGHS returns value zero. The independent full-tree best response reports
exploitability approximately `1.73e-16`.

The primary L1 endpoint is approximately `1.11e-16`, and reversing roster and
question enumeration produces approximately `5.55e-17`. Both fall below the
preregistered zero-result threshold. Thus duplicating the number of questions
that isolate one identity does not make the canonical equilibrium opening
policy depend on the protected private identity.

This is narrower than proving that every equilibrium is non-signaling. A
zero-sum game can have multiple equilibria, and two deterministic LP orderings
do not enumerate the entire equilibrium polytope. The correct claim is that the
independently certified canonical solution and its reversed enumeration both
produce the preregistered zero result.

The asymmetric roster still changes secondary behavior: ambiguous terminal
guessing falls from 77.78% in the balanced model to 66.67%, expected both-ask
rounds rise from 1.1111 to 1.2222, and 102 of 1,000 information sets have
positive equilibrium reach. There is strategic timing, but no observed opening
signal under the primary endpoint.

## Cross-method failure retained

At the preregistered 3,000-iteration budget:

| Algorithm | Independent exploitability | 0.001 gate |
|---|---:|---|
| Vanilla CFR | 0.00109196 | fail |
| CFR+ | 0.000426656 | pass |
| DCFR (1.5, 0, 2) | 0.000315148 | pass |

The all-method cross-check therefore fails and the audit artifact keeps
`passed=false`. The exact primary result remains independently valid, but the
experiment does not satisfy every preregistered cross-method condition. The
threshold was not relaxed.

A clearly labeled post-hoc diagnostic ran Vanilla CFR for 5,000 iterations and
obtained exploitability `0.000609172`, below the original threshold. This is
useful for sizing a future budget but does not rewrite the 3,000-iteration
failure. A ten-iteration negative control has exploitability about `0.1750` and
is rejected.

## Other games and next work

Focused regression tests for Guess Who, one-die Liar's Dice, four-card
Goofspiel, Kuhn and the shared readiness classifier remain green. Full-round
Love Letter advanced to 1,431,622 histories, 643,565 terminals and 206,752
observed information sets. Seventy frontier nodes remain, structural failures
remain empty and `complete=false`; full-round ε-GTO remains forbidden.

The next signaling experiment should not merely reshuffle public question
multiplicity. Under the current rules, a player's question helps identify the
opponent while revealing one's own identity is weakly harmful, so independence
is unsurprising. A meaningful next mechanism is a separately versioned game
with a small, private identity-dependent question cost. To preserve zero sum,
player-zero utility can be defined as terminal outcome minus player-zero cost
plus player-one cost. That change must receive a new rules ID and a fresh
preregistration; it must not be silently inserted into v1.

The main result is in
`research/results/guess_who_signaling_2026-10-03.json`; the post-hoc diagnostic
is stored separately in
`research/results/guess_who_signaling_posthoc_2026-10-03.json`.
