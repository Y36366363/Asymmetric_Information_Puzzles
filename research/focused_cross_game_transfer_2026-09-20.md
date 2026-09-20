# Focused cross-game transfer pilot (2026-09-20)

## Frozen scope and preregistration

The game count was frozen at three: certified four-card Love Letter and
one-die Liar's Dice are the **source** games; Guess Who is the held-out
**target**. Full-round Love Letter remains uncertified and was not used as an
equilibrium source. The source audit files and their SHA-256 fingerprints are
listed in
[`preregistration.json`](results/focused_transfer_2026-09-20/preregistration.json).
The preregistration hash is
`e018a8f3c028df0fbcf6d380293b2f4f093c29624c2248f9cbf209759d192fae`.
It was generated before model calls.

The four conditions were no prior memory, target-game advice (a supervised
positive control), surface descriptions of the two source games, and abstract
strategic memory distilled from the source games. The target-game control was
excluded from the primary transfer claim. The source-game blocks contain no
Guess Who character names or examples. The model was `gpt-5.6-luna`, low
reasoning, at most 4,096 output tokens and one completion attempt per cell.
Eight public target states (four fixed secrets after one or two oracle
questions) were crossed with all four conditions and shuffled with a frozen
seed. All conditions saw the same public state, legal actions, generic
instructions and output schema. Each condition's memory block was exactly
690 characters. The Responses API used structured outputs with storage off,
consistent with its [official API reference](https://developers.openai.com/api/reference/cli/resources/responses/methods/create).

The preregistered primary endpoint was mean **exact expected-turn action
regret**, including a prespecified one-turn-or-worse penalty for invalid or
missing decisions. The primary contrast was abstract memory minus no memory;
negative means better. Interpretation used a 10,000-resample paired bootstrap
interval: wholly below zero = benefit, wholly above zero = harm, otherwise
inconclusive. This is a small exploratory panel, not an equilibrium or
population-generalization test.

## Execution and observed outcomes

The first sandbox execution produced 32 connection errors, zero model tokens
and no valid actions. Its
[`report.json`](results/focused_transfer_2026-09-20/report.json) is marked as
infrastructure failure, **not** a null transfer result. With permitted network
access, the identical preregistration was run under a separate trial tag. The
[`approved-network report`](results/focused_transfer_2026-09-20/report_approved_network.json)
and [`cell-level records`](results/focused_transfer_2026-09-20/trial_rows_approved_network.json)
retain actions, exact scores, response fingerprints, usage and validation
failure evidence.

| Memory arm | Valid decisions / 8 | Penalized mean regret, turns | Valid-only mean regret, turns | Difference from no memory, turns | Paired 95% interval |
|---|---:|---:|---:|---:|---:|
| No memory | 6 | 0.270833 | 0.027778 | reference | — |
| Same-game control | 8 | 0.020833 | 0.020833 | −0.250000 | [−0.583333, 0.020833] |
| Surface source-game experience | 8 | 0.062500 | 0.062500 | −0.208333 | [−0.500000, 0.083333] |
| Abstract strategic memory | 7 | 0.145833 | 0.023810 | **−0.125000** | [−0.375000, 0.000000] |

All three intervals include zero, so the preregistered conclusion is
**inconclusive** for primary transfer and both controls. The abstract-memory
contrast is almost entirely an output-reliability contrast: among the six
probes where both abstract and no-memory decisions were valid, exact action
regret was equal to numerical precision. Three failed cells had malformed
belief distributions: no memory twice (one sum 1/3, one duplicate state) and
abstract memory once (sum 5/6). These were not silently repaired. A local
negative-transfer signal is also visible: surface experience selected a
suboptimal hair question in the Ada-after-one and Nico-after-one states,
incurring 1/6 turn regret each. This is a probe-level observation, not evidence
of aggregate harm.

## What this does and does not establish

This pilot demonstrates a reproducible four-arm evaluation harness that uses
an independently computed target-game optimum and preserves failures. It does
**not** establish that abstract memory improves strategic action selection.
The target is truthful information acquisition; it does not directly test
bluff/challenge thresholds or opponent modeling. The same-game control is
investigator-authored target advice rather than logged prior play, and the
other memory blocks are curated summaries rather than mechanically extracted
experience. They should be replaced by audited, fixed-length source traces in
a confirmatory experiment.

The memory blocks were character-matched, but actual provider input tokens
were **not** equal: totals over eight calls were 7,824 (no memory), 8,120
(same game), 8,200 (surface) and 8,208 (abstract). This means the prompt-length
requirement is met in characters, not in effective model tokens. The neutral
punctuation padding used to reach that length is itself an artificial prompt
feature. The model name
is an alias rather than a dated snapshot, no model sampling seed was supplied,
and eight correlated states are too small for a workshop-paper efficacy claim.
The next preregistration should lock a model snapshot if available, equalize
provider-counted prompt tokens, use actual experience records, increase the
state panel and independent repeats, and include a held-out adversarial game
if bluff/challenge transfer is the claim. Positive, null and negative outcomes
must all remain publishable; no condition should be dropped because it scores
poorly.

No runtime AI, GTO label, certification threshold or web game was changed.
