# Private identity-dependent question costs — 2026-10-04

## Frozen v2 rule

The new rule version is
`strategic_guess_who_private_question_cost_v2`. It inherits the frozen v1
simultaneous secret, ask-or-guess and wrong-guess conventions, then adds a
private identity-dependent cost for every committed ask.

Player-zero utility is defined as:

`terminal outcome - player 0 cumulative ask cost + player 1 cumulative ask cost`.

Player-one utility is its negative, so the game remains exactly zero sum.
Costs are charged even when an opponent's same-round guess ends the game,
because the question was already committed. Costs must be finite and
nonnegative. The semantic contract is frozen in
`configs/strategic_guess_who_private_cost_rules_v2.json`; changing any of these
choices requires another rules ID.

## Preregistered design

Before solving the game, the experiment fixed the same Ada, Bruno and Hugo
roster and the black-hair, brown-hair, glasses and hat questions. The cost rows
follow roster order and columns follow question order:

| Protected identity | black hair | brown hair | glasses | hat |
|---|---:|---:|---:|---:|
| Ada | 0.00 | 0.02 | 0.01 | 0.02 |
| Bruno | 0.02 | 0.00 | 0.02 | 0.01 |
| Hugo | 0.01 | 0.02 | 0.00 | 0.02 |

The largest single cost is 2% of the terminal win unit. The primary endpoint
remained the maximum within-seat L1 distance between opening policies for
different protected identities. Positive and zero thresholds remained `1e-6`
and `1e-8`. Exact sparse sequence form plus independent full-tree best response
at exploitability `1e-10` remained mandatory.

The CFR cross-check budget was preregistered at 5,000 iterations rather than
3,000. This choice was made from the separately labeled 2026-10-03 post-hoc
diagnostic, where Vanilla CFR passed `0.001` at 5,000 but not 3,000 iterations.
The cost matrix was not adjusted after observing the new result.

## Primary result: another valid zero signal

The complete tree remains 3,397 histories and 1,000 information sets. The
sparse sequence form has 689 sequences per player; private costs increase
payoff nonzeros from 1,244 to 1,662. The exact value is zero. Independent
exploitability is approximately `8.26e-17`, maximum flow residual is below
`8.4e-17`, and the primal-dual gap is zero.

The primary L1 endpoint is approximately `5.55e-17`. Reversing roster and
question enumeration gives approximately `2.78e-16`. Both are below the
preregistered zero threshold. In the canonical solution every private identity
uses the same opening mix: black-hair and glasses questions at probability 1/2
each.

The result indicates pooling: the protected identities accept different private
costs in order to avoid making the opening question informative about their
identity. It does not prove all equilibria are pooling, because canonical and
reversed LP solutions do not enumerate a potentially nonunique equilibrium
polytope. It does show that a cost differential capped at 0.02 did not produce
the preregistered signal in either deterministic enumeration.

## Secondary behavior and cross-method checks

Expected question cost is 0.01 for each seat. Relative to the cost-free
asymmetric experiment, ambiguous terminal guessing rises from about 66.67% to
88.89%, expected both-ask rounds fall from 1.2222 to 1.0, and positive-reach
information sets fall from 102 to 54. Thus small costs alter timing and tree
usage even though they do not separate opening policies by private identity.

At the preregistered 5,000-iteration budget:

| Algorithm | Independent exploitability | 0.001 gate |
|---|---:|---|
| Vanilla CFR | 0.000529185 | pass |
| CFR+ | 0.0000188092 | pass |
| DCFR (1.5, 0, 2) | 0.00000247645 | pass |

All cross-method gates pass. A ten-iteration Vanilla CFR negative control has
exploitability about 0.14746 and is rejected. Exact sequence form remains the
primary result; the regret-minimization numbers are independent cross-checks,
not substitutes for best response.

## Other games and next decision

Focused tests covering the new cost semantics, Guess Who certificates,
one-die Liar's Dice, four-card Goofspiel, Kuhn and readiness remain green.
Full-round Love Letter advanced to 1,451,622 histories, 652,473 terminals and
209,410 observed information sets. Sixty-nine frontier nodes remain, structural
failures remain empty and `complete=false`; full-round ε-GTO remains forbidden.

The two consecutive preregistered zero results are informative. Public question
multiplicity and a 2% private cost are not sufficient to overcome pooling in
this symmetric zero-sum race. The next step should be a mechanism decision, not
an unregistered cost sweep. Reasonable choices are:

1. stop the signaling branch and retain Guess Who as a challenge-threshold
   benchmark;
2. preregister a cost-strength dose response with fixed values and multiplicity
   correction, explicitly treating it as a boundary-finding experiment;
3. introduce a limited defensive action whose effectiveness depends on the
   protected identity, under a new rule ID.

Option 2 is the cleanest next scientific test if signaling remains important.
It should freeze the cost levels before solving and report the smallest level
at which the independently certified canonical policy crosses the L1 threshold,
including the possibility that no tested level crosses it.

The reproducible artifact is
`research/results/guess_who_private_cost_signaling_2026-10-04.json`, generated
by `scripts/audit_guess_who_private_cost_signaling.py`.
