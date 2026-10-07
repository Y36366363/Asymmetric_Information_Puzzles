# Love Letter collapsed-posterior decision — 2026-10-07

## Registered representation change

Yesterday's fixed-policy audit showed that the four-card Love Letter hidden
worlds differed by private card acquisition order that a current-hand policy
could not identify. Before recomputing the panel, today's experiment froze a
new strategic hidden-state target containing only:

- remaining card counts;
- burn card;
- opponent current hand.

Opponent private acquisition history was the only removed field. The same
full-support fixed policy and all of its coefficients were reused without
changes. The preregistered stopping rule said that if no information set after
an observed opponent action retained at least two strategic hidden states, the
four-card subgame would be retired as a belief-update target.

## Result

All mechanical checks pass:

- all 60 information sets have positive reach;
- Bayes reconstruction error is zero;
- independent action-value reconstruction error is zero;
- additivity residual is zero;
- the fixed policy remains independently rejected as an equilibrium at
  exploitability `0.358319`.

The support structure resolves the experimental question:

| Information-set group | Count | Collapsed support |
|---|---:|---:|
| Opening, before any opponent action | 12 | 2 |
| After an observed opponent action | 48 | 1 |

No information set combines an observed opponent action with a nontrivial
strategic hidden-state posterior. Maximum posterior L1 shift remains zero.
This matches the preregistered prediction.

## Routing decision

The four-card Love Letter subgame is now retired as a belief-update
manipulation target. It remains valuable as:

- an exact later-chance sequence-form benchmark;
- an independent best-response and exploitability control;
- a 60-information-set action-value/additivity benchmark;
- a regression target for CFR, CFR+ and DCFR.

A history-sensitive policy could create an acquisition-order signal, but that
would test recall-sensitive opponent modeling rather than belief about the
current strategically relevant hidden state. It should not be used merely to
rescue a positive result.

Meaningful Love Letter belief updating must move to a longer subgame or the
complete round, where an opponent action can occur while uncertainty about the
opponent's current strategically relevant state remains. The full-round tree
must still complete structural audit and independent certification before it
can supply such a panel or any ε-GTO runtime label.

The frozen design is
`configs/love_letter_collapsed_posterior_preregistration_2026-10-07.json` and
the reproducible result is
`research/results/love_letter_collapsed_posterior_2026-10-07.json`.
