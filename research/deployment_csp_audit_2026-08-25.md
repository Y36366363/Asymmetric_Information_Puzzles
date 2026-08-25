# Deployment and CSP audit — 2026-08-25

## Scope

This maintenance slice addressed two delivery risks only: stale GitHub Pages
content and the remaining `style-src 'unsafe-inline'` exception. It changed no
game rules, policies, benchmark scores, or optimality labels.

## Automatic `main/docs → gh-pages` publication

The public site is configured to build from `gh-pages`, while maintained source
and generated static assets live on `main`. A new GitHub Actions workflow now:

1. runs only for relevant pushes to `main` or an explicit manual dispatch;
2. rebuilds `docs` and fails if the committed build differs;
3. compares the exact `main:docs` tree with the published branch tree;
4. exits without a commit when they already match;
5. otherwise creates a commit whose tree is exactly `main:docs` and whose parent
   is the current remote `gh-pages` head;
6. pushes that fast-forward commit to `gh-pages`.

The workflow never runs on `gh-pages`, so publication cannot recursively trigger
itself. Concurrency is serialized rather than cancelled, and it does not use a
force push. These constraints preserve deployment history and avoid two updates
racing against the same parent.

## Removing the inline-style exception

All seven application-level dynamic-style sites were removed:

- strategy probability bars now use accessible native `<progress>` elements;
- Love Letter beliefs and Goofspiel mixtures use the same progress primitive;
- Battleship applies one of three audited board-size classes;
- pirate allocation state uses a warning class;
- Hidden Pursuit nodes use the fixed graph's 18 position classes;
- Hidden Pursuit routes are drawn on a Canvas from the public edge list.

The local source, generated GitHub Pages assets, and Worker runtime now contain
neither `style=` generation nor JavaScript `.style.*` mutation. CSP is therefore
`style-src 'self'` with no `unsafe-inline`. The in-app browser itself injects a
sidebar overlay with an inline style after page load; that extension-owned node
is outside AIP source and does not produce a CSP warning.

## Validation boundary

- All 200 Python tests and all 12 Worker/static-build tests pass.
- Workflow YAML parses locally and regression tests assert its build-drift,
  parent, no-force-push, and branch-trigger invariants.
- Worker/static tests exercise all 15 playable decision loops under the stricter
  generated policy.
- A real local browser rendered the 18-node Canvas map, three RPS progress bars,
  and a 10-column Battleship board with no AIP inline styles and no console
  warning or error.
- Public verification is performed only after the workflow completes and the
  deployed asset hash changes.

This is a delivery and browser-policy improvement, not evidence about strategic
generalization.
