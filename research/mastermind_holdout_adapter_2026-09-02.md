# Mastermind held-out adapter and leakage gate — 2026-09-02

## Outcome

The first post-preregistration gate is complete. Mastermind can now run through
the same benchmark input, decision, transition, and trace boundary as the other
research environments. No paid model comparison was run today: the implementation
and leakage gate are now ready for that separate, budgeted smoke test.

## What is measured

Each action is `submit_guess` plus a four-digit payload. The adapter returns only
public exact/misplaced feedback and preserves a spoiler-safe episode ID. It keeps
the exact candidate support internally and verifies after every transition that
the true secret remains possible.

The belief target is the probability distribution over the *next public feedback*
for the chosen guess. That distribution is exactly computable from the current
candidate support, compact enough for a completion model to report, and scored
before feedback is revealed using Brier score, log loss, and total-variation
distance from the exact predictive distribution.

Action quality uses the existing bounded one-step minimax adviser. The trace
therefore reports heuristic-reference agreement, worst-case candidate gap, and
information gain. It deliberately does **not** report exact regret, optimal-policy
agreement, or exploitability: global Mastermind optimality has not been proved by
this project.

## Frozen transfer material and leakage audit

The generic prompt, cross-game memory, and five source-environment IDs are frozen
in a versioned SHA-256 manifest. The audit fails if any hash or source list drifts,
if Mastermind appears as a source environment, or if the material contains target
names, canonical opening examples, target action IDs, rules-specific terminology,
or heuristic recipes. The current audit has zero findings.

The completion schema also now carries `payload_json`. This is a strict JSON
string that decodes to the unified action payload map, with `{}` for payload-free
actions. It lets the same real-model boundary choose parameterized actions without
adding a Mastermind-only parser or changing the trace shape.

## Offline reference panel

Four fixed secrets exercised different digit patterns:

| Check | Result |
| --- | ---: |
| Solved within 10 guesses | 4 / 4 |
| Mean attempts | 4.0 |
| Worst attempts | 5 |
| True secret retained after every feedback | 100% |
| Heuristic-reference agreement | 100% |
| Predictive-belief output rate | 100% |
| Mean predictive TV distance | 0.0 |
| Mean information gain per guess | 4.9197 bits |

The 100% agreement is a self-consistency test because the panel executes the
reference agent itself. It does not estimate model performance or prove that the
reference policy is globally optimal.

## Ordered next gates

1. Record two immutable model IDs, decoding settings, retry policy, and a hard
   call/token ceiling; then run two independent repeats on a small secret panel.
2. Accept the smoke test only if parse/validation failures, retries, confidence,
   token counts, latency, beliefs, and actions all survive trace replay.
3. Add equilibrium-backed regret and exploitability for Kuhn Poker and Goofspiel.
4. Hold one Liar's Dice agent fixed across declared opponent shifts.
5. Only after those metric layers are reliable, execute the full prompt × memory
   × cross-game-experience ablation.

Machine-readable result:
[`results/mastermind_holdout_readiness_2026-09-02.json`](results/mastermind_holdout_readiness_2026-09-02.json).
