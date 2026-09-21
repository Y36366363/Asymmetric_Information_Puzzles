# Token-balanced held-out Liar's Dice transfer test (2026-09-21)

## Why this update exists

The 2026-09-20 pilot used a truthful information-acquisition target and matched
memory blocks by characters rather than actual model tokens. It therefore did
not cleanly test bluff/challenge thresholds or opponent modeling. This update
uses one-die Liar's Dice as the held-out adversarial target and uses the
Responses input-token counting endpoint documented in the
[official OpenAI API reference](https://developers.openai.com/api/reference/cli/resources/responses/subresources/input_tokens).

The source games were frozen as Guess Who and the independently certified
four-card Love Letter subgame. Full Love Letter remains uncertified and was
not used. Source experience is no longer a fictional narrative:

- Guess Who records were emitted by its exact dynamic-programming agent;
- Love Letter decisions were emitted by its audited sequence-form LP policy;
- the exact record payload and its SHA-256 are embedded in the preregistration;
- the same-game positive control uses exact Liar's Dice action-value examples
  that are disjoint from the test probe information sets.

## Frozen protocol

The preregistration was written before completion calls. Its SHA-256 is
`f3dbe4b38bd867397cc8e8b76acc86d79d119fac86c8edc83766aaeb9fb59de3`.
It contains 12 exact decision probes, four memory conditions and two repeats,
for 96 model calls. Six probes have challenge as the unique exact best action
and six have a raise as the unique exact best action. Three raise probes place
the model in player 1's seat. The fixed model configuration was
`gpt-5.6-luna`, low reasoning, 4,096 maximum output tokens, one attempt per
cell and structured JSON output.

For every probe, the complete request was counted through the provider before
the trial. Neutral `PAD` tokens made all four conditions exactly equal for
that probe. Expected input sizes varied across states from 810 to 1,055 tokens,
but never across conditions within a state. All 96 observed usage counts
matched their preregistered values. There were no transport failures, invalid
outputs or model-name discrepancies.

The independent oracle is the sequence-form equilibrium plus the existing
exhaustive best-response action-value traversal. The primary loss is the
conditional utility difference between the best action and the chosen action;
training regret is never used. Invalid outputs would receive a preregistered
penalty of at least two utility units. The primary contrast is abstract memory
minus no memory, paired by probe and repeat. A fixed 10,000-resample bootstrap
interval wholly below zero is benefit, wholly above zero is harm, and any
interval crossing zero is inconclusive.

## Results

| Memory condition | Valid | Exact-best action rate | Mean action regret | Difference from no memory | Paired 95% interval | Result |
|---|---:|---:|---:|---:|---:|---|
| No memory | 24/24 | 70.83% | 0.486111 | reference | — | — |
| Same-game positive control | 24/24 | 70.83% | 0.472222 | −0.013889 | [−0.340278, 0.319444] | inconclusive |
| Surface source records | 24/24 | 75.00% | 0.423611 | −0.062500 | [−0.312500, 0.187500] | inconclusive |
| Abstract strategic memory | 24/24 | 70.83% | 0.493056 | **+0.006944** | [−0.236111, 0.270833] | inconclusive |

The preregistered conclusion is a **null/inconclusive transfer result**. The
abstract memory was numerically slightly worse, not better, and its interval
comfortably spans both benefit and harm. The same-game control also failed to
produce a detectable improvement. The surface-record arm was numerically best,
but its interval also spans zero; treating this as positive transfer would be
post-hoc selection.

Exploratory decomposition exposes a concrete policy weakness. With no memory,
the model chose all 12 challenge-optimal decisions correctly, but only 5 of 12
raise-optimal decisions. Its challenge selection rate on raise-optimal probes
was 58.33%, producing mean regret 0.972222 in that subgroup. Abstract memory
reduced challenge selection there to 50% and achieved 6/12 exact actions, but
also incorrectly raised once in a challenge-optimal state. Its repeat action
agreement was 75%, versus 91.67% for no memory and same-game experience. These
are exploratory diagnostics, not new primary endpoints.

Reported beliefs were poor in every condition: mean squared distance to the
exact posterior was approximately 0.493 throughout. The memory interventions
changed neither belief accuracy nor the primary decision metric reliably. The
important result is therefore not an efficacy claim; it is that the framework
can now separate legal-output reliability, posterior quality and exact action
quality under a genuine adversarial hidden-information target.

## Mechanism and game conclusions

1. Provider-counted token matching is feasible and should replace character
   padding in future AIP completion experiments.
2. Mechanical source records and their fingerprints prevent an investigator
   from quietly rewriting the claimed experience after observing results.
3. Liar's Dice reveals a challenge bias that the truthful Guess Who target could
   not expose. Future memory should teach calibrated continuation value rather
   than merely mention bluffing or challenges.
4. Four target examples are too weak to serve as a reliable positive control.
   A later preregistration should compare richer, mechanically sampled
   same-game records and an abstraction produced by a separately frozen
   transformation procedure.
5. Twelve probes and two repeats are still a mechanism-validation study, not a
   workshop-paper efficacy result. A confirmatory paper run needs more
   independently selected information sets, more repeats and preferably a
   dated model snapshot.

No GTO certificate, runtime AI policy, promotion threshold or web game was
changed. Complete Love Letter remains uncertified.

Machine-readable evidence is in
[`research/results/liar_transfer_confirmatory_2026-09-21`](results/liar_transfer_confirmatory_2026-09-21/).
