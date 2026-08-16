# Next playable game candidates — 2026-08-15

The next addition should be recognizable, genuinely driven by hidden
information, enjoyable against AI, operationally richer than a one-button
puzzle, and distinct from the fourteen games already in the lobby.

## Shortlist

Scores use a five-point scale. “AI feasibility” means the ability to build an
auditable opponent within this lightweight Python/browser architecture, not
the theoretical depth of the full game.

| Candidate | Familiarity | Player operations | AI feasibility | Browser fit | Distinct from current lobby | Recommendation |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| **Manor Mystery** (original Clue-like deduction) | 5 | 5 | 4 | 4 | 5 | **Prototype now** |
| **Goofspiel / Prize Bid** | 3 | 4 | 5 | 5 | 5 | Strong second choice |
| **Leduc Hold'em** | 3 | 4 | 5 | 4 | 2 | Research mode later |
| **Micro Stratego** | 5 | 5 | 2 | 3 | 4 | High-potential, high-cost later project |

### 1. Manor Mystery — recommended

The player holds private evidence cards, makes three-part suggestions, observes
which opponents cannot answer, privately sees one disproving card, maintains a
notebook, and eventually risks a final accusation. This produces several kinds
of information on every turn and supports a clear single-player loop with two
or more AI suspects.

The shipped version should use original names, setting, writing, and art rather
than Hasbro's protected title and characters. The mechanical reference is the
official rule structure: one hidden card from each category, suggestions that
opponents disprove in order, a card shown only to the questioner, and one final
accusation. See [Hasbro's official rules page](https://instructions.hasbro.com/en-us/instruction/f6420-clue-board-game)
and [classic rules PDF](https://www.hasbro.com/common/instruct/clueins.pdf).

Why it fits AIP:

- The information set includes both the secret solution and every legal deal
  of unseen cards—not just a list of possible culprits.
- Public passes and private reveals update beliefs differently.
- Suggestion choice has an information-value tradeoff; accusation adds an
  explicit failure risk.
- A notebook, mansion map, suggestion builder, response animation, and belief
  panel give the eventual web game varied operations without requiring online
  multiplayer.

### 2. Goofspiel / Prize Bid

Each player secretly selects one unused bid card for a revealed prize; bids
are then revealed together. It is compact, fast, and especially well suited to
minimax, regret matching, and opponent-model experiments. OpenSpiel lists
Goofspiel as a 2–10 player, simultaneous, imperfect-information game and uses
it as a suggested implementation example: [available games](https://openspiel.readthedocs.io/en/latest/games.html),
[developer guide](https://openspiel.readthedocs.io/en/latest/developer_guide.html).

It is the strongest engineering fallback because its browser UI is simple and
its strategy can be benchmarked rigorously. It ranks second because the name
and theme are less familiar to general players and a bare card-selection loop
could feel abstract without strong presentation or tournament modifiers.

### 3. Leduc Hold'em

Leduc adds a public card and multiple betting rounds to Kuhn Poker, making CFR
and exploitability exploration much richer. It is a standard imperfect-
information benchmark in OpenSpiel. However, it overlaps heavily with the
existing Kuhn Poker case and is less immediately recognizable than ordinary
poker, so it is better as a future “advanced research” mode than the next lobby
headline.

### 4. Micro Stratego

Hidden ranks, movement, combat reveals, memory, sacrifice, and flag protection
would make the most operationally rich candidate. The International Stratego
Federation publishes official variants and rules on its
[rules page](https://isfstratego.kleier.net/rules.html). A smaller original
hidden-rank tactics game could avoid an overwhelming board and reduce branding
risk.

The main blocker is AI credibility. Even a micro version needs hidden-setup
sampling, belief updates after movement and combat, tactical search, repetition
rules, and strong performance safeguards. It should follow—not precede—the
more tractable mystery prototype.

## Local Manor Mystery prototype

The current local-only model has four original cards in each of three
categories, three players, one hidden solution card per category, and three
cards per hand. From the detective's known hand it explicitly enumerates every
compatible secret and opponent deal. Opponents answer in order and reveal the
first matching card under a declared deterministic policy.

For each legal suggestion, the advisor partitions the full information set by
every response the detective could observe. It then minimizes:

1. expected remaining secret triples;
2. worst-case remaining secret triples;
3. expected remaining complete deals.

In one example, the detective began with 480 possible full worlds and 24 secret
triples. The recommended suggestion had five possible observable responses and
reduced the expected secret count to 12.11.

### Reproducible 200-case result

| Strategy | Solved within 16 suggestions | Mean suggestions | Worst suggestions |
| --- | ---: | ---: | ---: |
| Information advisor | **100.0%** | **4.430** | **12** |
| Non-repeating random | 77.5% | 10.345 | 16 |

The corrected observation model no longer assumes which of several legal cards
an opponent must reveal. Against the explicitly information-denying responder,
a separate 50-case audit solved **100% within eight suggestions**, averaging
**4.620** suggestions with a worst case of **6**. Mean Python wall time was
0.131 seconds per complete run; individual recommendation latency still needs a
browser-oriented benchmark before this game can pass the 100 ms gate.

Run with:

```bash
PYTHONPATH=src python research/simulate_manor_mystery.py
```

## What is and is not optimal

The advisor is exact for its **one-step information objective** under the
declared small deck and deterministic reveal policy. It is not yet a proof of
minimum total turns, and it is not an equilibrium for the full commercial
board game. Before web integration, the model should add adversarial card
selection by responders, public observations from AI turns, accusation utility,
and either map movement or a deliberate card-only pacing system.

## Proposed web-integration gate

Do not add a fifteenth playable lobby card until the local engine:

- preserves the true world after every legal observation in at least 1,000
  seeded cases;
- solves at least 99% within eight player suggestions against both transparent
  and information-denying reveal policies;
- keeps median recommendation latency below 100 ms in the intended browser
  state size;
- exposes a readable detective notebook explaining facts, deductions, and
  unresolved possibilities separately;
- uses entirely original names, story text, icons, and visual assets.

## 2026-08-16 integration decision

Goofspiel passed the current lightweight-web gate and is now the fifteenth
playable lobby game. The published version deliberately uses four bid cards:
that size admits an exact dynamic zero-sum solution, a compact 692-state policy
table, and instant browser decisions without a backend. The five-card exact
prototype remains a research target because recomputing its full policy is too
slow for the current deployment budget.

Manor Mystery gained an information-denying responder that may choose any legal
card which preserves the largest posterior ambiguity. The advisor now minimizes
worst-case remaining secrets against that responder. It remains local-only:
although the small model solves seeded cases, its recommendation latency is
still far above the 100 ms browser gate, and the full player experience still
needs opponent turns, accusation risk, and a readable notebook.
