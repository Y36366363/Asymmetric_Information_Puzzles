# Guess Who executable benchmark slice

Date: 2026-08-18  
Status: first runnable environment for Benchmark Contract v0

## Why this is the first milestone

Guess Who isolates three capabilities that can be scored without relying on a
judge model: hidden-state reasoning, Bayesian support tracking, and active
information acquisition. Its 24-state prior and eight-question bank are small
enough for exhaustive dynamic programming, while still producing multi-step
decision traces. It therefore tests the benchmark plumbing before equilibrium,
opponent-model, and language-agent complications are introduced.

This update does not add a new game or a web feature. It turns one existing
environment into a complete vertical slice:

`AgentInput -> AgentDecision -> environment transition -> exact evaluation -> JSON trace`

The public information state includes the visible trait profile of every
remaining candidate. This matters for generic agents: names plus question text
alone would expose legal actions without enough information to predict their
outcomes, unfairly making the adapter oracle-dependent.

## Declared game model

- The hidden character is uniformly sampled from the fixed 24-character roster.
- An agent asks one unused, truthful yes/no question per turn.
- Questions and the final identity guess each cost one turn.
- A final guess becomes legal only when exactly one candidate remains.
- Natural-language rules can be included or withheld without changing state or
  legal actions.

The last restriction is scientifically important. The current playable web
version permits an early wrong guess to remove one candidate. Under that action
space, early guessing can sometimes dominate another question, so the existing
question-only recurrence would no longer prove global optimality. The benchmark
therefore declares the narrower model instead of silently overclaiming.

## Oracle and metrics

The algorithmic oracle minimizes expected remaining questions using exact
dynamic programming over `(candidate mask, unused-question mask)`. All tied
optimal actions are retained for agreement scoring; deterministic tie-breaking
is used only to run the reference agent.

Each decision records:

- exact optimal-policy agreement;
- exact one-step continuation regret in expected questions;
- multiclass Brier score and log loss when the agent supplies a belief;
- probability assigned to the true state and mass assigned to the exact
  candidate support;
- realized information gain in bits;
- episode-level information efficiency in resolved prior bits per question;
- the public action and answer, without private chain-of-thought.

Missing beliefs remain `null`; they are not converted into a fake zero score,
and aggregate reports track belief-output coverage separately.
For strict JSON portability, zero probability on the truth receives log loss at
a declared `1e-15` probability floor and a separate
`zeroProbabilityOnTruth=true` flag instead of a non-standard infinity literal.
The terminal result reveals the secret for offline auditing, while no
pre-decision observation or information state contains it.

## Exhaustive baseline result

The oracle was run once against every character in the roster (24 episodes):

| Measure | Result |
| --- | ---: |
| Solved rate | 100% |
| Mean turns including final guess | 5.6667 |
| Worst-case turns including final guess | 6 |
| Exact optimal-policy agreement | 100% |
| Mean exact action regret | 0.0000 questions |
| Mean multiclass Brier score | 0.6544 |
| Mean belief log loss | 1.5910 nats |

The nonzero belief scores are expected: before enough answers arrive, even an
exactly calibrated posterior spreads probability uniformly across several
remaining candidates. They must not be interpreted as an oracle error.

As a metric sanity check, choosing `hair_black` on the initial state instead of
one of the four exact optimum questions incurs exactly `1/6` expected-question
regret and fails policy-agreement scoring.

## Trace contract

`aip-benchmark-trace-v0` serializes the decision input, chosen action, optional
belief, public outcome, evaluator metrics, evidence level, and terminal result.
It deliberately excludes free-form rationales. This keeps evaluation auditable
without treating an agent's unverifiable verbal explanation as ground truth.

## What this milestone does not claim

- It does not measure transfer gain yet; that requires at least two executable
  training environments and one held-out environment.
- It does not measure exploitability; Guess Who has no strategic opponent.
- It does not establish that Brier score alone captures reasoning quality.
- It does not turn the shared contract into a universal game engine.

The next implementation decision should be made only after traces from a
generic or deliberately weak agent are inspected. The highest-value candidate
is then a compact equilibrium environment (Kuhn Poker), because it adds
exploitability and opponent shift rather than duplicating information search.
