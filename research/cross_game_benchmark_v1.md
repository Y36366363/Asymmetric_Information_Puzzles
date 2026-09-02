# AIP Cross-Game Strategic Intelligence Benchmark v1

Date: 2026-08-18

## Research question and scope

> **Can a general strategic reasoning agent transfer reusable principles across
> heterogeneous imperfect-information games?**

AIP v1 is a lightweight benchmark over small, auditable environments already in
the repository. It is not a catalogue-growth project and not an OpenSpiel clone.
The benchmark layer standardizes decisions, traces, references, and metrics; each
game keeps its own small solver and transition logic.

Non-goals for v1:

- adding games to increase an environment count;
- a universal extensive-form game engine;
- one aggregate score that hides which claims are actually proved;
- calling an LLM action “optimal” because it agrees with a heuristic.

## 1. Capability taxonomy

Definitions:

| Capability | Operational meaning |
|---|---|
| Hidden-state reasoning | Act using an information state rather than the inaccessible world state. |
| Belief updating | Revise a support set or probability distribution after observations/actions. |
| Mixed strategy | Randomize intentionally so an opponent cannot exploit a deterministic pattern. |
| Opponent modelling | Infer or adapt to an opponent policy/type beyond fixed game rules. |
| Information acquisition | Choose actions partly for how much they reduce future uncertainty. |
| Deception/bluffing | Manipulate an opponent's belief through strategically ambiguous actions. |
| Adversarial search | Optimize against worst-case or strategically chosen responses. |
| Risk-sensitive decision making | Trade expected value against variance, tail loss, survival, or utility. |

`P` means a primary capability, `S` a meaningful secondary capability, and `—`
means the current environment is not intended to measure it.

| Existing environment | Hidden | Belief | Mixed | Opponent | Info | Deception | Adversarial | Risk |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Cases of Fate | P | S | — | S | P | — | — | P |
| Blackjack | P | S | — | — | — | — | — | P |
| Restricted RPS | — | — | P | P | — | S | S | — |
| Mastermind | P | P | — | — | P | — | S | — |
| Guess Who | P | P | — | — | P | — | S | — |
| Hidden Pursuit | P | P | — | S | P | — | P | — |
| Battleship | P | P | — | S | P | — | P | — |
| E-Card | P | S | P | P | — | P | S | P |
| Pirate Council | — | — | — | P | — | S | P | — |
| Love Letter | P | P | S | P | S | P | S | P |
| Kelly Survival | — | — | — | P | — | — | S | P |
| Kuhn Poker | P | P | P | P | — | P | P | P |
| Liar's Dice | P | P | S | P | — | P | S | P |
| Goofspiel | S | — | P | P | — | S | P | — |
| Moving Worm | P | P | — | — | S | — | P | — |
| Manor Mystery (local prototype) | P | P | — | S | P | S | P | — |

The unfinished all-pay auction remains research material, not a v1 benchmark
environment. Risk-sensitive games remain useful future evaluation strata, but
their preference/utility specification must be fixed before cross-agent ranking.

## 2. First benchmark environment set

Six environments give complementary evidence without pretending every reference
has the same status.

| Environment | Benchmark role | Exact optimal | Equilibrium | Regret | Exploitability | Belief truth | Heuristic truth |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Kuhn Poker | Equilibrium anchor for hidden cards and bluffing | — | Yes | Yes | Yes | Yes | — |
| Goofspiel | Finite-horizon mixed-strategy anchor | — | Yes | Yes | Yes | — | — |
| Guess Who | Exact information-acquisition anchor | Yes | — | Yes | — | Yes | — |
| Moving Worm | Exact worst-case belief-search anchor | Yes | — | Yes | — | Yes* | — |
| Liar's Dice | Calibration, deception, and opponent-shift probe | — | — | — | — | Yes | Yes |
| Mastermind | Primary held-out transfer environment | — | — | — | — | Yes | Yes |

`*` Worm ground truth is an exact reachable support set. Probabilistic calibration
requires a separately declared worm policy; a worst-case adversary does not imply
a probability distribution.

Why these six:

- Kuhn and Goofspiel test reusable randomization/equilibrium principles in very
  different action representations.
- Guess Who and Worm supply proved policies with exact belief-state transitions.
- Liar's Dice prevents the suite from containing only clean exact solvers: claim
  probabilities are exact, while bidding remains explicitly heuristic.
- Mastermind is a clean held-out transfer test from question selection and belief
  filtering to multi-valued feedback partitions. Its current one-step minimax
  adviser is strong but not globally proved optimal.

## 3. Minimal unified agent interface

One decision request contains only:

1. `observation`: directly visible private and public facts;
2. `information_state`: adapter-defined support, sufficient statistic, or belief;
3. `legal_actions`: stable action IDs plus optional payload schemas;
4. `action_history`: ordered actor/action/public-observation records;
5. optional `natural_language_rules`;
6. stable environment, episode, and step IDs.

One agent response contains only:

1. `action_id` and optional declared payload (`payload_json` at the strict
   completion boundary, decoded back to the same payload map);
2. optional belief distribution over adapter-defined stable labels;
3. confidence in `[0, 1]`.

The interface intentionally omits simulator internals, hidden world state, and a
mandatory chain-of-thought field. Agents may reason internally, but evaluation
uses actions, stated beliefs, confidence, and outcomes. The implemented contract
and current Guess Who and Mastermind adapters live in `aip.benchmark`.

## 4. Experimental conditions

All systems receive identical legal actions and observations. Rule text and
experience are controlled factors rather than silently different prompts.

| Condition | Access |
|---|---|
| Algorithmic oracle | Puzzle-specific exact/equilibrium solver where one exists; labelled heuristic otherwise. |
| Generic LLM | Generic strategic-reasoning instruction, rules, no target examples, no persistent memory. |
| Single-game prompted LLM | Target-game rules, terminology, and target-game demonstrations. |
| Reasoning/memory agent | Generic prompt plus structured within-episode belief/action memory; no cross-game demonstrations. |
| Cross-game-experience agent | Generic interface plus solved traces/principles from other training games; no target-game examples. |
| Held-out-game evaluation | Freeze prompts/memory procedures, withhold all Mastermind traces and game-specific advice, then evaluate Mastermind. |

Primary comparison on the held-out game:

- generic LLM versus cross-game-experience agent measures transfer;
- single-game prompted LLM is a target-supervised ceiling, not evidence of transfer;
- reasoning/memory agent separates general memory benefits from cross-game
  experience;
- the algorithmic reference provides metric targets only at its declared evidence
  level.

After the primary Mastermind holdout, v1 can run leave-one-environment-out folds.
Seeds, opponent policies, decoding parameters, prompt tokens, and retry rules must
be fixed before evaluation.

## 5. Required metrics

Metrics are reported per environment and evidence stratum; unavailable metrics
are `N/A`, never fabricated.

### Exploitability and regret

- **Exploitability:** value lost against a best response relative to the game
  value. Primary for Kuhn and Goofspiel.
- **Decision regret:** oracle action value minus chosen action value at the same
  information state. For exact search tasks, also report excess expected/worst-
  case steps. Heuristic disagreement is not called regret.

### Equilibrium/optimal-policy agreement

- For deterministic optima: fraction of decisions choosing an optimal action.
- For set-valued optima: credit any action in the optimal support.
- For mixed equilibria: report support violations and distribution distance
  (total variation or Jensen-Shannon), not only top-action agreement.

### Belief calibration

- Brier score, log loss, and calibration error when probabilistic belief truth is
  defined.
- Support precision/recall and true-state retention when only an exact candidate
  set is defined.
- Belief scores are computed before the hidden outcome is revealed.

### Information efficiency

- entropy or candidate reduction per action;
- expected and worst-case steps to identification/capture;
- normalized excess queries relative to an exact oracle where available.

### Transfer gain

For a metric where higher is better:

`transfer gain = held-out cross-game score - held-out generic score`.

For loss metrics, reverse the sign. Also report a normalized gain divided by the
gap between the generic baseline and the appropriate oracle/reference. Never mix
an equilibrium oracle and a heuristic reference in the same normalization.

### Robustness to opponent shift

Evaluate unchanged agents against at least equilibrium/fixed, naive, adaptive,
and adversarial opponent families where legal. Report absolute performance and
the worst degradation from the training opponent. Liar's Dice opponent types and
Kuhn/Goofspiel best responses are the first probes.

## 6. Evidence labels are not interchangeable

1. **Proved optimality:** a proof or exhaustive dynamic/search certificate shows
   no policy can do better under the stated objective and rules.
2. **Equilibrium-backed behavior:** a Nash/minimax policy is protected against
   unilateral exploitation; an individual sampled action need not be uniquely
   optimal.
3. **Strong heuristic:** reproducible and empirically validated, but lacking a
   global optimality/equilibrium certificate.
4. **Exploratory LLM behavior:** an experimental policy. Agreement with a
   heuristic remains heuristic agreement, not proof of optimality.

Every result table must carry one of these labels beside its reference. Language
such as “optimal”, “equilibrium”, and “exploitability” is reserved for conditions
where the corresponding object is actually computed.

## 7. Implementation status and ordered roadmap

Implemented foundations:

1. **Benchmark Contract v0** — unified input/output, legal-action validation,
   capability taxonomy, evidence labels, and the six-environment catalog.
2. **Exact trace slice** — Guess Who adapter, replayable traces, exact action
   regret, optimal-policy agreement, belief Brier/log loss, and information
   efficiency.
3. **Completion boundary** — the same real completion model can run generic and
   single-game prompts with parse/retry/token/latency/confidence telemetry.
4. **Experiment Protocol v1** — deterministic trial identities across model,
   seed, repeat, condition, environment, and opponent shift; a full
   prompt × memory × cross-game-experience ablation matrix; and metric names
   gated by exact/equilibrium/heuristic ground truth.
5. **Held-out Mastermind gate** — spoiler-safe action/feedback traces, exact
   next-feedback belief truth, bounded-heuristic action comparison, a generic
   completion payload bridge, and frozen prompt/memory hashes with target leakage
   checks. This gate authorizes a small model smoke test; it is not model evidence.

Future work proceeds one evidence-bearing slice at a time:

1. **Two-model smoke comparison.** Run a two-model, two-repeat frozen panel first;
   promote it to
   the full seed/repeat grid only if completion and scoring reliability pass.
2. **Kuhn/Goofspiel equilibrium adapters.** Add mixed-policy distance, exact
   regret, and exploitability before reporting either word in model results.
3. **Liar's Dice opponent-shift panel.** Hold the agent fixed across reference,
   naive, adaptive, and adversarial policies; exact belief calibration can be
   scored even though action quality remains heuristic-backed.
4. **Factorial ablation execution.** Compare generic prompt, memory, and
   cross-game experience with main effects and interactions. Do not infer a
   memory or transfer gain from unrelated prompts or different model snapshots.

The complete v1 matrix contains 4,608 planned trials for two models and is a
preregistration target, not authorization to spend tokens blindly. Every stage
starts with a small reliability pilot and records failures as outcomes.
