# Generic adapter-to-sequence-form milestone — 2026-09-15

The new core compiler has no poker-specific imports or knowledge. It requires
explicit finite, two-player zero-sum/constant-sum perfect-recall properties and
runs the existing complete-tree structural audit itself. A previous audit is
not blindly trusted. Imperfect recall, illegal chance and unsupported properties
fail before compilation; history and matrix-cell budgets bound small-game use.

Each player sequence is its full earlier information-set/action history. The
empty sequence has realization weight one. For every information set the sum
of outgoing sequences equals its parent sequence. Chance probabilities never
enter flow constraints: terminal utility multiplied by complete chance reach
is aggregated into the payoff matrix. Multiple hidden worlds can contribute to
the same sequence pair, and their contributions are summed accurately.

Both players' sequence-form LPs use the existing MIT project-internal two-phase
simplex. Free dual variables are represented as positive-minus-negative parts;
equalities become paired inequalities. Both realization plans must pass flow
residual and primal-dual gap checks. Unreachable information sets receive a
normalized uniform behavioral continuation. Independent tree best response,
not LP objective agreement alone, is the final equilibrium check.

| Adapter | Sequences P0 / P1 | Value P0 | Independent exploitability |
|---|---:|---:|---:|
| Canonical Kuhn | 13 / 13 | -1/18 | below 1e-12 |
| Single-round E-Card | 6 / 6 | -1/5 | below 1e-12 |
| Love Letter four-card subgame | 61 / 145 | 1/6 | 0 |

Kuhn also matches the earlier independently constructed specialized LP.
Reversing root chance order yields identical compiled flow/payoff matrices and
solved policy. Existing permanent tests retain the analytic/matrix reference
checks and undertrained negative controls. New tests cover all three adapter
structures, unsupported games, imperfect recall, malformed chance, budget
failure, normalization, sparse export, and nonfinite solver tolerance.

`SequenceForm.to_artifact()` exports sparse flow and payoff entries with sequence
indices, shapes, RHS, and structural audit. The current internal solver still
uses dense matrices; sparse export is not a claim of scalable sparse solving.
No package dependency or license boundary changed. No CFR variant was added.

This research milestone does not replace runtime policies or promote the entire
Love Letter round. Its exact result applies only to the existing four-card
subgame; E-Card repeated adaptation remains heuristic. Adapter utility is defined
as player-zero net utility and player-one utility is its negative; a raw
constant-sum adapter must center its payoffs before using this convention.

Reproduce with `PYTHONPATH=src python scripts/audit_sequence_form.py`.
Numerical reports and sparse representations are in
`research/results/sequence_form_audit_2026-09-15.json`.
