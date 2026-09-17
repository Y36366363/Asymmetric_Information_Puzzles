# Local checkpoint and portable-policy milestone — 2026-09-17

## Delivered

The full-round structural audit can now pause and resume locally. SQLite stores
information-set records with compact integer IDs, action consistency and recall
sequences expressed as earlier IDs/action indices. The frontier stores integer
action-index paths. States are reconstructed through the adapter, avoiding a
large executable object/pickle checkpoint. Each bounded chunk commits progress
and information sets in one transaction; an unexpected exception rolls back the
whole chunk. Only one writer should use a checkpoint.

The supplied CLI binds its revision to the Love Letter adapter, rules and audit
implementation source bytes. The generic API requires an explicit revision;
callers must include all transitive rules and initial configurations. These are
trusted local checkpoints, not authenticated downloads. Rule revisions cannot
be resumed with a stale database. No symmetry or game abstraction is applied.

Closing/reopening the database for every 37-history chunk produces exactly the
same completed statistics as the existing independent recursive audit for both
Kuhn and the Love Letter four-card subgame. Tests also cover failed recall,
illegal chance, version mismatch, partial-result denial and interruption rollback.

## Measured full-round progress

Three actual closed/reopened chunks produced cumulative histories 8,739, 11,581,
and 18,998. At the last checkpoint: 8,460 terminals, 5,055 chance histories,
5,483 decisions, 3,285 information sets, maximum depth 26 and 77 frontier nodes.
No structural failure has been found in that prefix. **It is not a certificate**:
the frontier is nonempty and equilibrium certification remains false.

The persisted database is `research/local_checkpoints/love_letter_full_round.sqlite`
(local-only, ignored by git); the compact progress evidence is versioned in
`research/results/love_letter_local_progress_2026-09-17.json`.
Continue with `PYTHONPATH=src python scripts/advance_love_letter_local.py`.

Path replay and SQLite lookup introduce overhead. This prototype provides
bounded memory, transactional restart and evidence continuity, not a demonstrated
speedup over the earlier million-history traversal. The counts are an explored
prefix, not an estimate of total tree size. The next acceleration step is to
retain compact active states within chunks and benchmark before larger runs.

## Local strategy → browser-format bridge

The already enumerable four-card subgame is solved locally via sparse HiGHS.
Its independent evaluator measures exploitability zero and value 1/6. Export
requires a passed strategy-fingerprint-bound report and reruns independent
evaluation rather than trusting its pass flag. The portable JSON includes typed
card/target/guess actions, JSON information sets, normalized distributions,
rules revision, profile fingerprint, independent report and explicit subgame scope.

Python JSON roundtrip reconstitutes the identical behavioral profile and passes
independent certification. Node tests consume the same exported artifact without
SciPy or Python and check its schema, actions, distributions and scope. This is
format/transport compatibility evidence, **not deployment of a new browser AI**.
The artifact says `full_round_runtime_allowed=false`; neither the full local
match nor browser match may apply a four-card subgame policy to arbitrary states.

No new dependency was added. Full-round certification still requires exhaustive
structural completion, sequence/payoff compilation, solving, full independent
best response and profile-bound promotion. Once those gates pass, the same local
export approach can be used to build a browser policy lookup without web LPs.
