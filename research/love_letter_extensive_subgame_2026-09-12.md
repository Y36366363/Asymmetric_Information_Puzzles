# Love Letter extensive-form and subgame audit — 2026-09-12

## Outcome

Love Letter now has an immutable `CFRGame` model distinct from the mutable UI
engine. The model represents a complete two-player round from the 16-card deck,
including hidden burn, three public removals, private initial hands, later private
draws, alternating actions, protection expiry, all eight card effects, deck
exhaustion, discard tie-breaks, and zero-sum terminal utility.

This closes the **rules representation** milestone. It does not by itself solve the
full game. Straight exhaustive traversal passes one million histories without
finishing, so the full-round information-set inventory and independent NashConv are
still deliberately uncertified.

## Information-set design

A decision information set contains only information available to the acting
player:

- public face-up removals, protection flags, discard totals, deck size, and full
  public action/effect history;
- the acting player's current hand;
- that player's remembered initial card, later draws, own actions, Priest views,
  and cards received through King or Prince.

It excludes the hidden deck composition/order, burn card, opponent hand, and the
opponent's private observation history. Public history plus private observation
history also preserves the player's own action/observation recall.

The audit groups all histories sharing an information-set key and rejects any group
whose legal actions differ. It separately records the excluded hidden-world fields,
so a group is demonstrably imperfect-information only when multiple hidden worlds
share the same key.

## Completely enumerated four-card benchmark

To validate the entire pipeline before attempting the full tree, the same rules
engine is instantiated as a separately scoped river benchmark. Cards 1–4 (Guard,
Priest, Baron, Handmaid) are randomly assigned to both one-card hands and the two-card
draw order. All 24 hidden assignments are present at the root.

Exhaustive traversal reports:

| Measure | Result |
| --- | ---: |
| Histories | 1,081 |
| Chance histories | 217 |
| Decision histories | 240 |
| Terminal histories | 624 |
| Information sets | 60 |
| Information sets containing multiple hidden worlds | 60 |
| Maximum depth | 5 |
| Structural failures | 0 |

This is a complete certificate for this four-card benchmark only. It is not
transferred to the standard 16-card round.

## Independent best response

The new best-response evaluator does not use CFR regret tables. It first traverses
the complete tree against the fixed opponent policy to compute counterfactual reach
for every state in each responding player's information set. Working recursively
from later decisions, it chooses one pure action for the entire information set—not
a different action for each hidden world. Running it independently for both seats
produces half NashConv, the project's exploitability measure.

The evaluator strongly distinguishes policies:

| Policy | Half NashConv / exploitability |
| --- | ---: |
| Uniform action distribution | 0.375000000 |
| External-sampling MCCFR, 20,000 iterations, seed 20260912 | 0.000484423 |

The learned profile covers all 60 required information sets, has minimum visitation
1,631, maximum average-positive-regret diagnostic `0.009303104`, and passes the
declared subgame thresholds: 20,000 iterations, 1,000 minimum visits, regret at most
`0.015`, and exploitability at most ε=`0.001`.

A four-seed stress check at 20,000 iterations produced exploitability from
`0.000484` to `0.000658`; all seeds passed the hard exploitability threshold. Two
seeds exceeded a stricter hypothetical regret threshold of `0.01`, which is why the
regret diagnostic remains `0.015` rather than being misrepresented as a proof.

## Full-round next step

The full state transition system is now available, but exhaustive history expansion
duplicates many strategically equivalent continuations. The next implementation
should build a canonical DAG/sequence-form inventory that merges identical immutable
states while preserving information-set reach weights. It must then:

1. finish the complete 16-card information-set and legal-action audit;
2. measure memory/runtime before selecting full traversal or external sampling;
3. compute both independent best responses on the complete model;
4. apply cross-seed and convergence tests; and
5. freeze and expose a runtime policy only after the full-round ε gate passes.

Until those steps finish, the existing live Love Letter AI remains a belief heuristic.
The reproducible benchmark command is:

```bash
PYTHONPATH=src python scripts/audit_love_letter_subgame.py
```
