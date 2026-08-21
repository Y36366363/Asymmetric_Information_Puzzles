# AIP — Asymmetric Information Puzzles

> 🌐 **[Play AIP online / 在线打开独立游戏大厅](https://y36366363.github.io/Asymmetric_Information_Puzzles/)**
> · [ChatGPT-hosted backup / 备用入口](https://aip-asymmetric-games.jyao27254718.chatgpt.site)
> · [Local lobby / 本地大厅](http://127.0.0.1:8765/)
> · [GitHub repository](https://github.com/Y36366363/Asymmetric_Information_Puzzles)

## Updates 08/21/2026

- **Independent prompt replication** — Repeated the same four-secret paired
  Guess Who experiment with the same resolved `gpt-5.6-luna` model. All eight
  new episodes completed. Generic repeated 5.75 mean turns, 89.47% exact-policy
  agreement, and 0.01754 regret; single-game recorded 6.00 turns, 75.00%
  agreement, and 0.03611 regret. [Read the replication](research/completion_replication_2026-08-21.md).
- **Pooled difference remains visible** — Across two stochastic runs and eight
  episodes per condition, generic reached 89.47% optimal-question agreement
  versus 79.49% for single-game, with lower regret and better confidence
  calibration. This is a narrow one-game result, not a cross-game transfer claim.
- **Policy stability is now measured** — Exact aligned action agreement across
  repeats was 75.00% for generic and 45.24% for single-game. Equal terminal
  success therefore does not imply a stable or equivalent policy.
- **Bounded live usage** — Today's eight-episode run consumed 56,548 tokens. At
  the official price observed today, estimated token cost was $0.02527. One
  single-game belief required a validation retry; no generic retry was needed.
- **Historical traces are executable data** — `EpisodeTrace` now supports strict
  `from_dict`, `from_json`, and `read_json` reconstruction. Saved traces can be
  rescored offline without another API call, while unknown schema versions and
  malformed shapes are rejected.
- **Regression verification** — All 195 Python tests and all 11 public
  engine/static-build tests pass, including trace round trips, malformed-trace
  rejection, and the localhost health check.

## Updates 08/20/2026

- **First real-model paired experiment** — Ran the same resolved
  `gpt-5.6-luna` model on generic and single-game prompts across four fixed
  Guess Who secrets. Both completed panels solved 4/4 with 5.75 mean turns, but
  generic had 89.47% exact optimal-question agreement versus 84.21% for the
  single-game prompt. This small one-environment panel is operational evidence,
  not a cross-game transfer claim. [Read the experiment](research/completion_real_model_experiment_2026-08-20.md).
- **Trace differences are measurable** — Generic recorded 0.01754 mean action
  regret and 0.63920 belief Brier; single-game recorded 0.02339 and 0.65700.
  Their aligned action sequences agreed only 45.83% of the time despite equal
  mean turns, confirming that the trace and scoring layer reveals differences
  hidden by terminal success.
- **Operational reliability is explicit** — First-run completion was 3/4 for
  generic and 4/4 for single-game. A targeted generic recovery completed, and
  each successful panel used 24 provider attempts for 23 strategic decisions.
  Report v1 now separates those counts and retains full failure telemetry.
- **Belief contract hardened** — Guess Who now declares the exact belief target
  and allowed state labels. Small probability-rounding deviations up to 2% are
  normalized with the raw sum and event recorded; larger deviations, unknown
  states, and wrong targets are rejected and retried. The live runs exercised
  both normalization and strict rejection paths.
- **Credential handling secured** — `.env` and `.env.*` are ignored (except a
  future `.env.example`), and the runner reads `OPENAI_API_KEY` literally without
  shell evaluation. Keys and raw completion text are never written to traces.
- **Reproducible live runner** — Added selective `--condition` recovery, safe
  terminal-error capture, input/output token totals, belief-normalization counts,
  low-reasoning backend metadata, and `store=false` requests. Sanitized raw
  traces and a machine-readable panel report are retained under
  `research/results/completion_gpt-5.6-luna_2026-08-20/`.
- **Regression verification** — All 194 Python tests and all 11 public
  engine/static-build tests pass. The Python suite includes the localhost health
  check under an environment that permits a temporary loopback socket.

## Updates 08/19/2026

- **Completion-backed agent boundary** — Added a provider-neutral request and
  response contract, strict decision parser, bounded retry loop, and shared-model
  pair for generic versus single-game Guess Who prompts. Both conditions must
  use the same backend instance and requested model.
- **Operational telemetry in every trace** — Decision steps now record parse,
  validation, and transport failures; retries; per-attempt and total latency;
  input/output/total tokens; response IDs; requested and resolved models; output
  fingerprints; and final self-reported confidence. Failed raw text is not
  retained.
- **Optional real OpenAI adapter** — Added a `store=false` Responses API backend
  with strict JSON-schema output and an optional `llm` dependency group. The
  guarded runner requires `OPENAI_API_KEY`, accepts an explicit model or snapshot,
  runs both prompt conditions, and rejects resolved-model drift. No real-model
  result is claimed today because this host has no API credential. [Read the
  boundary and run protocol](research/completion_agent_boundary_2026-08-19.md).
- **Failure-path regression coverage** — Added deterministic tests for malformed
  JSON, illegal actions, transport failures, successful and exhausted retries,
  usage aggregation, latency, confidence, trace serialization, and the official
  Responses request shape. All 191 Python tests and 11 public-engine/build tests
  pass.
- **Generic weak control** — Added a game-agnostic, stateless baseline that uses
  a stable seeded hash to choose among legal actions. It reads no rules,
  observations, history, beliefs, or game-specific state, emits no invented
  belief, and is reproducible across processes.
- **Single-game prompted control** — Versioned a Guess Who prompt and a local
  deterministic proxy that follows its one-step balanced-split instruction
  using only public `AgentInput`. It is explicitly recorded as a strong
  heuristic with `isLlm=false`, not presented as either a real LLM result or a
  proof of optimality.
- **Trace provenance and fairer metrics** — Added structured agent-condition
  metadata to every trace. Policy agreement and action regret now exclude the
  forced final identity guess, preventing a trivial action from inflating weak
  policies' scores.
- **Hidden-state channel closed** — Removed secret character names from default
  episode IDs and excluded episode IDs from the generic policy hash, so tracing
  identifiers cannot accidentally influence actions through hidden state.
- **Baseline discrimination confirmed** — Across 100 weak seeds and all 24
  secrets, the generic control averaged 5.9033 turns, 70.29% exact-policy
  agreement, and 0.0483 regret. The prompted proxy averaged 5.6667 turns, 100%
  agreement, and zero regret; this equality with the oracle is an exhaustive
  result for the fixed roster, not a general proof. [Read the baseline study](research/guess_who_baseline_discrimination_2026-08-19.md).
- **Regression coverage** — All 185 Python tests and 11 public-engine/build tests
  pass. No game, web feature, or deployment artifact was added.

## Updates 08/18/2026

- **First executable benchmark slice** — Connected Guess Who to the unified
  agent contract through a small reusable episode runner, a proved-optimal
  algorithmic oracle, and an auditable `aip-benchmark-trace-v0` JSON export.
  Traces contain observations, information states, legal actions, beliefs,
  choices, confidence, public outcomes, and scores without private reasoning
  text or pre-decision secret leakage.
- **Exact policy and belief scoring** — Every decision now reports tied-optimum
  policy agreement, exact continuation regret, multiclass Brier score, log
  loss, true-state probability, candidate-support mass, and realized
  information gain, plus resolved prior bits per question as information
  efficiency. Missing belief outputs remain explicitly unscored.
- **Proof boundary made explicit** — Benchmark guesses become legal only after
  one candidate remains. This matches the dynamic-programming proof model and
  avoids incorrectly calling the web variant's early-guess action space proved
  optimal.
- **Exhaustive oracle baseline** — Across all 24 secrets, the oracle solved 100%
  in 5.6667 mean turns (worst case 6), with 100% exact-policy agreement and zero
  action regret. [Read the executable-slice analysis](research/guess_who_benchmark_slice_2026-08-18.md).
- **Cross-game benchmark direction** — Reframed AIP around one research
  question: whether a general strategic-reasoning agent can transfer reusable
  principles across heterogeneous imperfect-information games. Environment
  count is no longer a primary progress metric, and a universal OpenSpiel-style
  engine is explicitly out of scope.
- **Capability and evidence taxonomy** — Classified the existing environments
  across hidden-state reasoning, belief updating, mixed strategy, opponent
  modelling, information acquisition, deception, adversarial search, and
  risk-sensitive decisions. Policy references are now separated into proved
  optimality, equilibrium-backed behavior, strong heuristics, and exploratory
  LLM behavior.
- **Six-environment v1 design** — Selected Kuhn Poker, Goofspiel, Guess Who,
  Moving Worm, Liar's Dice, and held-out Mastermind, with an explicit matrix for
  exact policy, equilibrium, regret/exploitability, belief truth, and heuristic
  truth. [Read the benchmark design](research/cross_game_benchmark_v1.md).
- **Benchmark Contract v0** — Implemented the only milestone in this update: a
  dependency-free agent input/output contract, legal-action and belief
  validation, capability/evidence enums, and a version-controlled environment
  catalog. No new game or unrelated web feature was added.
- **Regression coverage** — All 180 Python tests and 11 public-engine/build tests
  pass, including six new contract, calibration, evidence-level, and holdout
  checks.

## Updates 08/17/2026

- **Spoiler-safe worm challenge** — The minimax hint and guaranteed capture
  sequence are now hidden behind separate Hint and Answer controls; the opening
  guide no longer leaks the solution, and long search histories scroll inside
  their panel instead of overflowing the page.
- **Sharper case-game negotiation** — Banker offers are now deliberately below
  the remaining prize expectation, the offer screen preserves the latest
  reveals and every remaining value, and the negative reservation-price label
  has been replaced with a clear nonnegative risk reference. Players also get
  one counter-offer per game, with acceptance ending the game and rejection
  automatically continuing it.
- **Two-mode Blackjack learning** — Added Normal and Practice modes, clearer
  dealer/player seat framing, and per-decision basic-strategy feedback. The UI
  now states the exact implemented action set: Hit, Stand, and Double are live;
  Split, Surrender, and Insurance remain intentionally unavailable.
- **Readable code entry** — Bulls & Cows input now uses high-contrast dark,
  heavier digits on a brighter field, including clearer placeholder and caret
  treatment.
- **First-turn guidance for harder games** — Added bilingual, action-specific
  opening briefings to Kuhn Poker, Liar's Dice, Love Letter, Kelly Survival,
  Goofspiel, and the adversarial worm puzzle; the guide disappears after the
  player commits the first meaningful action. A dedicated 15×15 Battleship
  briefing explains its large-board cadence before combat.
- **Probability-based post-match reviews** — Restricted RPS and Goofspiel now
  separate score variance from policy quality, reporting equilibrium-support
  coverage, the average probability assigned to chosen actions, repeated-move
  exposure, and any zero- or low-frequency bidding rounds.
- **Faster, auditable large-board Battleship** — The 15×15 board now uses fair
  two-shot salvos for both sides, shows shots remaining before the AI responds,
  and reports search-versus-target mode, density coverage, tied best cells,
  explored-board progress, and confirmed enemy segments.
- **Protected-target bug fixed** — Love Letter now disables the AI as a Prince
  target while Handmaid protection is active and automatically selects the only
  legal self-target instead of letting a visible action fail after submission.
- **Honest mixed-strategy guidance** — Goofspiel now calls the highlighted bid
  the highest-frequency equilibrium action and explicitly tells players to
  randomize by the full distribution, rather than implying one fixed card is
  always optimal.
- **Mobile and keyboard usability** — Enlarged lobby, GitHub, language, and home
  controls to 44 px touch targets on phones and added visible focus treatment to
  native select menus without introducing horizontal overflow.
- **Full player-route audit** — Traversed all 15 public detail pages and ran
  complete game loops in both runtimes; checked rules/restart/back controls,
  translations, duplicate IDs, unnamed controls, busy states, 390 px overflow,
  and browser logs. [Read the
  audit and next priorities](research/player_experience_audit_2026-08-17.md).
- **Daily stability pass** — All 167 Python tests plus 11 public-engine and
  static-build tests pass, including a deterministic regression for the
  protected Prince edge case.

## Updates 08/16/2026

- **Secret Bidding is playable** — Added a bilingual four-round Goofspiel game
  to the public lobby, with hidden simultaneous bids, public finite inventories,
  reveal history, clear beginner-facing rules, and responsive controls.
- **Exact equilibrium AI** — Solved every four-card public state with rational
  zero-sum dynamic programming and primal/dual LP checks, then exported 692
  policies so the zero-backend browser can respond instantly without seeing the
  player's current bid. [Read the strategy audit](research/goofspiel_ai_2026-08-16.md).
- **Strategy stress test** — Across 2,000 fixed-seed games, equilibrium play
  stayed near the symmetric value of zero while uniform random and always-high
  play lost 1.644 and 2.093 points per match on average, respectively.
- **Adversarial Manor Mystery** — Opponents can now choose the legal reveal that
  preserves the most ambiguity, while the advisor minimizes worst-case remaining
  solutions. It solved all 50 adversarial seeded cases within eight suggestions,
  but remains local-only pending opponent turns, accusation risk, and notebook UI.
- **Daily stability pass** — Expanded Python and public-engine decision-loop
  coverage for the new game, rebuilt the static deployment, and checked the
  bilingual player journey and mobile layout; all 163 Python plus 10
  public-engine tests pass.

## Updates 08/15/2026

- **Next-game shortlist** — Compared a Clue-like original mystery, Goofspiel,
  Leduc Hold'em, and Micro Stratego across familiarity, player agency, AI
  feasibility, browser fit, and overlap with the current lobby. [Read the ranked analysis](research/next_game_candidates_2026-08-15.md).
- **Local Manor Mystery prototype** — Added an exact hidden-deal information
  set, ordered passes, private card reveals, posterior filtering, and a
  one-step information advisor without exposing the game in the web lobby.
- **Early strategy evidence** — Across 200 seeded cases, the information
  advisor solved 100% in 3.995 suggestions on average (worst 6), versus 81.5%
  within the limit and 9.595 suggestions for non-repeating random play.
- **Exact Kuhn Poker equilibrium** — Corrected the AI's first-seat Q call
  frequency from `1/3` to `2/3` after check-bet while retaining `1/3` for the
  distinct second-seat information set.
- **Exhaustive exploitability oracle** — Added an exact rational evaluator that
  checks all 64 pure best responses from each seat. It proves zero
  exploitability for the corrected policy and reproduces the old policy's
  `1/9`-chip-per-hand weakness. [Read the full audit](research/kuhn_poker_ai_2026-08-15.md).
- **Private-card-aware guidance** — Expanded the bilingual rules and made the
  live bet prompt respect the player's known card: a J holder can rule out a J
  bluff, while a K holder can identify the equilibrium bet as a J bluff.
- **Cross-runtime consistency** — Published strategy-scope metadata and the
  position-aware policy in both the Python service and zero-backend browser
  engine, then rebuilt both deployable targets.
- **Daily stability pass** — Verified complete single-player loops, the local
  health endpoint, 390px responsive layout, first-screen navigation, language
  switching, and clean browser logs; all 156 Python plus 10 public-engine tests
  pass.

## Updates 08/14/2026

- **Strategy optimality audit** — Classified every playable game as exact,
  rule-scoped optimal, equilibrium-backed, strong heuristic, or
  objective-dependent instead of using “optimal” as a generic quality label.
  [Read the comparisons and limitations](research/strategy_audit_2026-08-14.md).
- **Smarter Battleship hit pursuit** — On 10×10 and 12×12 boards, density AI
  now requires candidate ships to explain a full connected hit line, removing
  misleading perpendicular targets after consecutive hits.
- **Evidence-gated large-board behavior** — Kept the legacy 15×15 focus rule
  after the first generalized prototype worsened tail risk; paired same-seed
  tests now protect both mean performance and P90 before accepting an AI change.
- **Reproducible cross-policy tooling** — Added a Love Letter match simulator,
  legacy-versus-enhanced Battleship audits, strategy-scope metadata, and fresh
  2,000-match / 3,000-tournament / 1,000-chase comparisons.
- **Daily stability pass** — Completed the local player journey on a 12×12
  board through a two-hit information update, verified 390px layout and clean
  browser logs, and passed all 146 Python plus 10 public-engine tests.

## Updates 08/13/2026

- **Player-journey hierarchy cleanup** — Restored the lobby's beginner-to-
  challenge progression, moved the two medium games ahead of the hard tier,
  and synchronized every bilingual detail page to unique CASE 01–14 labels.
- **Case-order regression guard** — Added an asset-level test that fails when
  the lobby order, Chinese detail label, or English detail label drifts again.
- **Honest multi-target verification** — Fixed the one-command verifier so it
  rebuilds both the deployable Worker bundle and the zero-backend GitHub Pages
  lobby before testing them, eliminating stale-build false failures.
- **Full player-facing regression pass** — Rechecked first-entry rules, top-of-
  page entry, visible lobby return, console output, all complete single-player
  decision loops, and the shared service contract; all 143 Python and 10 web
  tests pass.
- **Kelly survival tournament** — Added a virtual-capital single-player game
  with a permanent 1:1 / 50% baseline, dynamic odds-probability tradeoffs,
  five skill-based AI rivals, periodic eliminations, and a 12-round title race.
- **Growth versus survival audit** — A repeatable 3,000-game comparison found
  Kelly won 22.93% with 54.03% survival, while double Kelly raised title rate
  to 28.73% but cut survival to 46.70%. [Read the model and results](research/investment_tournament_ai.md).
- **Risk-literate interface** — Added bilingual beginner rules, expected-return
  and Kelly calculations, selectable 0–75% virtual positions, hidden rival
  decisions, responsive rankings, and explicit no-real-money framing.
- **Daily regression expansion** — Added deterministic mathematics, checkpoint
  elimination, seeded tournament, service, full browser-engine match, and
  shared-state contract coverage before rebuilding the public lobby; all 142
  Python and 10 web tests pass.

## Updates 08/12/2026

- **Love Letter duel shipped locally** — Added a complete two-player 16-card
  deduction match with all eight role effects, bilingual rules, responsive UI,
  public discard beliefs, and first-to-four scoring.
- **Belief-aware opponent** — The new AI estimates the player's card only from
  information it is legally allowed to observe; a 2,000-match seeded audit found
  a 92.00% win rate against random play. [Read the strategy scope and results](research/love_letter_ai.md).
- **Full-match regression coverage** — Python and browser tests now play entire
  Love Letter matches, verify hidden-hand boundaries, forced Countess play, and
  repeatable advice before rebuilding the zero-backend lobby; all 137 Python
  and 10 web tests pass.
- **Cross-project architecture audit** — Compared AIP with OpenSpiel,
  PettingZoo, and Gambit, then [recorded which ideas fit this lightweight lobby](research/platform_comparison_2026-08-12.md)
  and which would add unnecessary research-framework complexity.
- **Enforced playable-state contract** — Every game now publishes `gameId`,
  `phase`, and unique `legalActions`; the Python service and both JavaScript
  runtimes reject malformed future game plugins at their shared boundary.
- **Dynamic conformance coverage and parity fix** — Registry-wide tests now
  audit every playable game automatically, and the public Moving Worm engine
  now matches Python's valid 2–12-hole range instead of rejecting two holes.
- **Clear cross-game operation feedback** — Added one bilingual, accessible
  processing indicator shared by session creation, restarts, and every game
  action, so clicks never appear to be silently ignored while the UI is locked.
- **Safer local-service boundaries** — Prevented oversized or invalid-length
  JSON bodies from being read, disabled stale caching for local UI assets, and
  added regression coverage around the request boundary.
- **One-command architecture verification** — Added `scripts/verify.py` to run
  the Python suite, rebuild the zero-backend public mirror, and test the browser
  engine with an explicit Node fallback for environments without global `npm`.
- **History-aware game navigation** — Added stable `#lobby` and `#game/<id>`
  routes so browser Back and Forward move between the lobby and an active game
  instead of unexpectedly leaving the site. Direct game routes also recover
  safely, while invalid routes return to the lobby.
- **Keyboard-safe rule dialogs** — Rules now receive focus when opened, keep
  keyboard focus inside the modal, close with Escape, and return focus to the
  control that opened them (or the visible Rules button after an automatic
  first-visit tutorial).
- **Daily cross-runtime verification** — Rebuilt the zero-backend public mirror,
  exercised the local lobby and Pirate Council in a real browser, checked clean
  browser logs and route/focus behavior, and passed all 131 Python plus 10 web
  engine/build tests.

## Updates 08/10/2026

- **Playable Guess Who identity lab** — Promoted the researched 24-character
  model into the public bilingual lobby with eight public yes/no questions,
  clickable character guesses, live eliminations, explicit information sets,
  session scores, and complete beginner rules.
- **Exact strategy adviser** — Added a one-click dynamic-programming adviser
  that minimizes expected questions for the fixed roster and question bank. It
  averages 5.667 turns including the final guess and has a proven six-turn
  worst case; the UI labels this model-specific scope instead of claiming a
  universal Guess Who optimum.
- **Cross-runtime and user-journey verification** — Kept the Python server and
  zero-backend public engine behavior aligned, completed a browser-played optimal
  round, exercised wrong guesses and bilingual state retention, checked 390px
  mobile overflow, and passed all 126 Python plus 10 web tests.

## Updates 08/09/2026

- **Eleven-game user journey audit** — Tested every playable game as a new
  desktop and 390px mobile user, including rules, first decisions, feedback,
  lobby returns, responsive overflow, and browser error logs.
- **Clarity and mobile fixes** — Removed Blackjack's narrow-screen overflow,
  synchronized Liar's Dice inputs with each new legal bid floor, and made the
  Pirate Council explain exactly why Submit is locked.
- **Guess Who optimal-policy laboratory** — Added a local-only 24-character
  information-set model and compared random, fixed-order, entropy, minimax, and
  exact dynamic-programming agents. The proven model-scoped optimum averages
  5.667 turns including the final guess and needs at most 6.

## Updates 08/08/2026

- **Playable Hidden Pursuit** — Added an 18-node, two-detective hidden-movement
  game with Taxi/Bus signals, scheduled reveals, live belief-set elimination,
  an evasive-information AI, bilingual rules, responsive map controls, match
  history, and ephemeral browser-only sessions.
- **AI exploration before integration** — Built the Python model first and ran
  1,000-game policy comparisons. Random detectives captured the information-aware
  fugitive in 38.2% of games, while belief-pursuit captured it consistently,
  confirming that public-signal reasoning materially changes results.
- **Cross-runtime parity** — Added equivalent Python, local-service, public-worker,
  complete-game-loop, hidden-information, and static-build tests so the new game
  follows the same modular session boundary as the existing lobby.

## Updates 08/07/2026

- **Daily reliability audit** — Re-ran the complete Python and zero-backend
  browser-engine suites, repeated full game loops, and checked build and public
  entry behavior before release.
- **Bounded AI memory** — Converted the Bulls and Cows adviser cache to a
  256-state least-recently-used window, preventing one long-running local
  session or research process from accumulating information sets without limit.
- **Backend Battleship strategy audit** — Added a repeatable Python-only
  experiment across 10×10, 12×12, and 15×15 fleets, including paired tail-risk
  comparisons so probability density is measured as a strong heuristic rather
  than incorrectly presented as a per-game optimum.

## Updates 08/06/2026

- **Stability and flow hardening** — Bounded temporary sessions to prevent
  long-running memory growth, made preferences safe when browser storage is
  unavailable, cancelled stale game requests when returning to the lobby,
  stabilized consecutive toast messages, localized network/session failures,
  and added full 15×15 Battleship and session-expiry regression coverage.
- **Cross-game usability audit** — Repeated every playable game entry/exit flow,
  verified language switching preserves active input, confirmed 390px mobile
  layouts have no page-wide overflow, and completed ten repeated browser-engine
  stress rounds without console warnings or errors.
- **Bulls and Cows strategy lab** — Upgraded the small Mastermind prototype into
  a standard 0–9 four-digit deduction game with 5,040 hidden worlds, explicit
  candidate elimination, leading-zero support, optional minimax AI suggestions,
  worst/expected partition analysis, per-guess information gain, and session averages.
- **AI benchmark and next-game review** — Added a repeatable browser-engine
  simulation and documented the bounded minimax strategy, its non-optimality caveat,
  a 100-game 5.29-attempt benchmark, and Scotland Yard as the leading next solo game.
- **Regression review** — Expanded Python and public-browser tests around hidden-code
  feedback, malformed input, candidate accounting, complete AI play, and static UI wiring.

## Updates 08/05/2026

- **Scalable, colored Battleship fleets** — Enlarged the desktop boards, added
  10×10, 12×12, and 15×15 seas with density-matched fleets, assigned every ship
  a distinct color, added collision-safe 90° rotation controls, and preserved
  usable cell sizes on mobile with board-local scrolling.
- **Playable solo Battleship** — Promoted the Battleship research prototype into
  the bilingual web lobby with fleet randomization, hidden enemy deployment,
  alternating fire, sink detection, probability-density AI, decision explanations,
  responsive 10×10 boards, complete rules, and future multiplayer-ready sessions.
- **First-play guidance and Battleship research** — Added explicit lobby action
  labels and one-time automatic rule tutorials, plus a local Battleship simulator
  comparing random, hunt/target, and probability-density AI before future UI integration.
- **Hardening and mobile usability pass** — Fixed a Liar's Dice AI private-hand
  information leak, rejected malformed and fractional game inputs, corrected
  double-digit lobby numbering, improved compact-screen controls and rule panels,
  added keyboard/focus accessibility, and expanded randomized regression tests.

## Updates 08/04/2026

- **End-state hardening and difficulty order** — Fixed the browser case game's
  missing final opening round, added explicit final-offer and kept-case results,
  sorted the lobby from beginner to challenge, and added complete multi-game
  decision-loop regression coverage.
- **Full beginner rulebooks** — Expanded every playable game's help panel into
  a six-part tutorial covering the player's role, objective, click-by-click
  flow, a concrete example, end conditions, and plain-language terminology.
- **Beginner-friendly game guidance** — Rewrote every rules panel as an actionable
  tutorial with goals, exact clicks, feedback interpretation, end conditions,
  and strategy tips; entering a game now jumps to the top and the lobby return
  control is a prominent button.
- **Playable Mastermind information-set lab** — Added a solo hidden-code game with
  exact/partial feedback, candidate-world elimination, a worst-case partition
  suggestion, ten-attempt pressure, bilingual controls, and a visible solve log.
- **Playable Liar’s Dice** — Added a two-player hidden-dice match with wild ones,
  public lexicographic raises, explicit challenge decisions, exact binomial odds,
  an adaptive AI, round history, and a bilingual information-set panel.
- **Backend-free public mirror** — Published all nine playable games at
  [y36366363.github.io/Asymmetric_Information_Puzzles](https://y36366363.github.io/Asymmetric_Information_Puzzles/).
  Game state and AI now run entirely inside the visitor's browser, with no
  ChatGPT request, account, server session, or saved data; refreshing starts over.

## Updates 08/03/2026

- **Public production deployment** — Published the bilingual lobby and all
  seven playable games at
  [aip-asymmetric-games.jyao27254718.chatgpt.site](https://aip-asymmetric-games.jyao27254718.chatgpt.site),
  with dependency-free edge execution, ephemeral sessions, and live health checks.
- **Playable blackjack strategy lab** — Added a six-deck S17 table, hidden
  dealer hole card, hit/stand/double decisions, rule-scoped basic-strategy AI,
  autoplay, bankroll tracking, and per-decision strategy auditing.
- **Playable restricted RPS lab** — Added finite public move inventories,
  simultaneous hidden choices, an exact finite-state minimax baseline,
  bounded adaptive exploitation, probability diagnostics, and match simulation.
- **Playable E-Card asymmetric duel** — Added alternating Emperor and Slave
  roles, simultaneous hidden card selection, five-times underdog rewards,
  adaptive mixed-strategy AI, public duel history, and bilingual round analysis.
- **Playable Kuhn Poker** — Added a repeatable three-card poker match against
  a mixed-strategy AI, with alternating first position, bluffing, live chip
  scores, private-card information sets, bilingual play, and post-hand analysis.

## Updates 08/02/2026

- **Bilingual navigation and project links** — Added a persistent Chinese/English
  switch across all playable games, a GitHub mark linking to the repository,
  and direct local-lobby and GitHub links at the very top of this README.
- **Deterministic smart-worm opponent** — Removed random capture entirely,
  made every miss preserve a worst-case legal escape trajectory, emphasized the
  live check counter, and added a regression proving repeated wrong checks never win.
- **Playable pirate council** — Added a human-authored gold proposal screen,
  rational continuation-aware voters, individual vote explanations, survival
  consequences, and comparison with the backward-induction equilibrium.
- **Adversarial task-4 game mode** — Upgraded the moving-worm game from a
  random simulation to a true worst-case opponent driven by its public belief state.
- **Playable moving-worm search** — Added a second lobby game with a hidden
  moving target, interactive hole checks, public belief-state tracking, random
  legal movement, and the shortest minimax capture sequence as an optional hint.
- **Reliable local preview launch** — Added a double-click macOS launcher,
  health endpoint, existing-server detection, automatic occupied-port fallback,
  and verified the complete first-round flow in a real browser.
- **Local playable game lobby** — Added a dependency-free local browser UI,
  pluggable game registry, private in-memory sessions, and a fully playable
  26-case banker game with live risk metrics and decision history.
- **Liar's Dice belief and challenge engine** — Added private-hand information
  sets, exact binomial claim odds, cost-sensitive challenge thresholds, legal
  raise ranking, Bayesian bluff-type inference, and Monte Carlo verification.
- **Sequential case-and-banker lab** — Added the standard 26-case prize board,
  configurable opening and offer schedules, expected value and CARA certainty
  equivalents, exact next-offer projection, reproducible simulation, and Bayesian
  learning over hidden banker types.

## Updates 08/01/2026

- **Public leadership and convention selection** — Separated raw high-bid
  dominance from majority legitimacy, added competing 101+ leadership signals,
  pairwise public-price runoffs, and median selection among 1/5/25 conventions.
- **Costly leadership and majority enforcement** — Added a 101-price leadership
  signal, symmetric all-bid-1 norm, majority expulsion of attributable defectors,
  social-deviation simulation, and the finite-horizon enforcement boundary.
- **Price-only tacit auction coordination** — Added anonymous public-price
  signals, a low-price convention with collective punishment, deviation-noise
  simulation, and patience thresholds for indefinite repeated auctions.
- **Repeated all-pay auction lab** — Added a formal 100-value auction model,
  symmetric mixed-equilibrium benchmark, finite-budget multi-round simulation,
  and comparisons of naive, cautious, rational-benchmark, and cooperative play.
- **Prisoner timing and risk analysis** — Added exact coupon-collector and
  single-counter completion distributions, closed-form expectations, Monte Carlo
  validation, confidence deadlines, and a configurable false-declaration trade-off.
- **Prisoners-and-light coordination** — Added safe designated-counter plans
  for known-off and unknown initial light states, reproducible random simulation,
  execution traces, and an explicit distinction between safety and finite-time completion.
- **Village eye-colour induction** — Added a configurable common-knowledge
  solver that identifies the simultaneous action night, exposes the day-by-day
  counterfactual reasoning, and demonstrates why a public announcement is essential.

## Updates 07/31/2026

- **Guaranteed moving-worm capture** — Added shortest-path search over evolving
  hole information sets, a six-check guarantee for five holes, and a stepwise
  explanation of the forced parity change after every miss.
- **Robust bean-taking analysis** — Added five-player minimax solving over an
  uncertain pile-size interval, exact-count safe-action ranges, zero-risk action
  intersection, and a conservative recommendation when no action is universally safe.
- **Public-knowledge hat solver** — Added finite-world information sets,
  simultaneous public announcements, repeated world elimination, and explicit
  discovery-delay traces for arbitrary two-colour hat configurations.

AIP is a modular Python environment for exploring dynamic games, backward
induction, common knowledge, information sets, and robust strategies.

The project currently solves pirate gold allocation, public coloured-hat and
village eye-colour reasoning, prisoners-and-light coordination, robust
sequential bean taking, repeated all-pay auctions, adversarial moving-worm
search, a sequential case-and-banker lab, and Liar's Dice. Its shared core
supports both deterministic elimination and Bayesian belief updates.

## Start the local game lobby

The first genuinely playable AIP experience is now available locally:

On macOS, the easiest method is to double-click **`启动 AIP 游戏.command`** in
the project folder. Keep the Terminal window that appears open while playing.
Closing that window stops the local page.

The command-line equivalent is:

```bash
PYTHONPATH=src python -m aip play
```

Or, after installing the project in editable mode:

```bash
aip-play
```

The program normally opens `http://127.0.0.1:8765` in the default browser. If
that port belongs to another program, AIP automatically selects a free port and
prints its exact address in the launcher window. Starting the launcher twice
detects the existing AIP process and simply reopens it. It listens
only on the local machine unless `--host` is explicitly changed. No account,
network connection, JavaScript build tool, or third-party runtime dependency is
required. Game sessions live only in memory and disappear when the local server
stops.

The lobby now orders its complete single-player games from approachable to demanding:
**命运之箱**, **21 点策略实验室**, **限定猜拳实验室**, **密码破解**,
**E-Card 皇帝牌**, **海盗议会**, **库恩扑克**, **骗子骰子**, and **移动虫穴**.
In 命运之箱:

1. Choose one of 26 sealed cases to keep.
2. Click other cases to reveal the required number for the current round.
3. Inspect the banker's offer, expected value, certainty equivalent, volatility,
   and probability that the chosen case beats the offer.
4. Accept the deal or reject it and continue opening cases.
5. Review the full decision history and final case value.

In 移动虫穴, choose one of five adjacent holes on every turn. A missed worm
immediately moves exactly one step left or right. **对抗模式** is now the
only mode and directly implements task 4: the computer keeps every trajectory
that is still legal and always chooses a surviving worst-case branch. It cannot
be beaten by luck—capture occurs only when the selected hole covers every state
left in the public information set. There is no preselected random position and
no random movement; twenty repeated checks of the wrong hole still produce
twenty misses. The live counter updates after every attempt.

The optional minimax sequence is highlighted one step at a time. Following
`2 → 3 → 4 → 2 → 3 → 4` from the beginning guarantees capture within six
checks for five holes. A capture is therefore always mathematically forced,
never lucky.

In 海盗议会, you play the most senior pirate A. Allocate all 100 coins among
five pirates and submit the proposal. Every other pirate compares the offer
with the already-solved equilibrium that follows if A is killed, then votes
according to survival first and gold second. The council displays every vote,
its continuation outcome, the realized survival result, and the subgame-perfect
benchmark only after the human proposal is locked in.

限定猜拳 gives both sides three copies each of Rock, Paper, and Scissors.
Every move permanently consumes one card and both remaining inventories are
public. A backward dynamic program solves the zero-sum matrix game at every
reachable pair of remaining inventories; the AI keeps most of that minimax
distribution while assigning a bounded weight to exploiting the player's
observed bias. The page reveals both the equilibrium and exploit components
after each simultaneous choice.

21 点策略实验室 uses six decks, U.S.-style hole-card checking, dealer stands
on soft 17, blackjack pays 3:2, and no split, surrender, or insurance actions.
Its AI implements the total-dependent basic-strategy table for Hit, Stand, and
Double, and audits every manual decision against that table. This is the
optimal baseline for the stated action abstraction without card counting; it
is not a universal optimum. Exact shoe composition, splitting, surrender,
different soft-17 rules, and payout changes can alter the best action. A future
composition-dependent expected-value solver therefore remains worthwhile for
research, although it is unnecessary for ordinary basic-strategy training.
The rule distinctions and composition-dependent boundary follow the
[Wizard of Odds 4–8 deck strategy](https://wizardofodds.com/games/blackjack/strategy/4-decks/)
and its [total-versus-composition comparison](https://wizardofodds.com/games/blackjack/composition-dependent-benefit/).

The UI never receives the chosen case's hidden amount before the game finishes.
The Python-side `GameRegistry`, `PlayableSession`, and `LocalGameService`
separate lobby discovery, private state, legal actions, and public snapshots.
Liar's Dice and Mastermind are now playable through the same session adapter;
the auction remains a disabled preview and can be enabled without changing the
local server or lobby shell.

## Mastermind: a single-player information-set game

The **猜数字 / Mastermind** game hides a four-digit code made of four distinct
decimal digits from 0–9, including possible leading zeroes. Each guess returns two public signals: exact matches
(right symbol, right position) and partial matches (right symbol, wrong
position). The secret itself remains private until the player solves the code or
uses all ten attempts.

This is a compact asymmetric-information game: the computer knows the code,
while the player only observes feedback. The live candidate count is the size
of the player's information set. A suggested guess is chosen by a minimax-style
partition heuristic that tries to minimize the largest surviving candidate
bucket, so the player can compare intuition with systematic experimentation.

## Guess Who: exact identity deduction

**猜猜我是谁 / Guess Who?** presents all 24 public character cards while the
AI privately selects one identity. A turn can ask one unused yes/no question or
submit a direct character guess. Every answer eliminates inconsistent cards and
updates the player's information set; the secret is revealed only when the
round ends.

The adviser solves the fixed roster and eight-question bank by exact dynamic
programming. It chooses the policy with the lowest expected remaining number of
questions, then spends one final turn naming the unique candidate. Under the
uniform-secret assumption this takes 5.667 turns on average and no more than
six. These guarantees belong to this explicit model: changing the roster,
question bank, secret prior, or guess cost creates a different optimization
problem.

## Project layout

```text
.
├── pyproject.toml
├── README.md
├── src/aip/
│   ├── cli.py                    # command-line interface
│   ├── core/
│   │   ├── game.py               # reusable game/solver protocols
│   │   └── information.py        # information sets, beliefs, public history
│   ├── ui/                       # local game lobby, API, and browser assets
│   └── puzzles/
│       ├── pirates/              # complete backward-induction solver
│       │   ├── models.py
│       │   ├── solver.py
│       │   └── formatting.py
│       ├── hats/                  # common-knowledge evolution solver
│       ├── eyes/                  # village eye-colour induction
│       ├── prisoners/             # one-bit distributed coordination
│       ├── auctions/              # repeated all-pay auction analysis
│       ├── cases/                 # sequential case opening and banker signals
│       ├── guess_who/             # exact identity-question policy and roster
│       ├── liars_dice/            # private dice, bluff odds, and challenges
│       ├── beans/                 # interval minimax and robust strategies
│       └── worm/                  # shortest adversarial search strategy
└── tests/
    ├── test_information.py
    └── test_pirates.py
```

## Run the pirate solver

No third-party runtime dependency is required:

```bash
PYTHONPATH=src python -m aip pirates --pirates 5 --gold 100
```

Or install the project in editable mode and use its command:

```bash
python -m pip install -e .
aip pirates --pirates 5 --gold 100
```

The solver prints every suffix game, beginning with the youngest pirate alone,
so the full backward-induction chain is visible. For every round it shows the
allocation, threshold, individual vote, rejection outcome comparison, and
reasoning.

Useful rule variants:

```bash
aip pirates --pirates 5 --gold 100 --strict-majority
aip pirates --pirates 5 --gold 100 --accept-equal
```

## Default pirate assumptions

1. Pirates rank outcomes lexicographically: survival first, then gold.
2. The proposer votes for their own feasible proposal.
3. At least half of all votes passes, so an exact tie passes.
4. A non-proposer rejects when survival and gold are exactly equal.
5. If multiple cheapest winning coalitions exist, the more senior candidate is
   chosen to make the displayed equilibrium deterministic.

Both the vote threshold and equal-outcome preference are configurable through
`PirateRules`. If a coalition is unaffordable, the solver records the
proposer's death and carries forward the already-solved continuation outcome.

## Run the coloured-hat solver

```bash
PYTHONPATH=src python -m aip hats --colors BBBRR --target B --other R
```

Every player sees all hats except their own. The announcement “at least one hat
is B” is public knowledge, and all answers are simultaneous and public. With
three B hats, nobody knows in rounds one and two; all three B-hat players know
in round three. The output exposes each player's information set at every round.

## Run the village eye-colour solver

```bash
PYTHONPATH=src python -m aip eyes --target-count 3 --other-count 7 \
  --target-color white --other-color black
```

Assumptions: everyone sees everyone else's eyes but not their own; all villagers
are perfect reasoners; an outsider publicly announces that at least one person
has the target eye colour; and every night's actions are publicly observed. If
there are `N` target-colour people, nobody acts on nights 1 through `N-1`, then
all `N` target-colour people infer their colour on day `N` and act simultaneously
that night (in the stated puzzle, they die by suicide). Other-colour people do
not act under this rule.

The announcement is not redundant: it turns a visible fact into common
knowledge and supplies the induction's base case. Use
`--no-public-announcement` to show that no synchronized day is guaranteed.

## Run the prisoners-and-light solver

```bash
PYTHONPATH=src python -m aip prisoners --count 100 --initial off \
  --goal turned-on --seed 42
```

Before separation, prisoner 0 is designated as the counter. If the light is
known to start off, every other prisoner turns it on exactly once—the first
time they find it off—and otherwise does nothing. The counter turns it off and
increments a private count. At `N-1`, the counter can safely declare that all
non-counters have operated the light. For the literal `turned-on` goal in this
puzzle, the counter must additionally turn the light on personally before
declaring. The standard `--goal visited` variant omits this extra self-signal.

If the initial state is unknown, use `--initial unknown`. Every non-counter then
signals twice, and the counter waits for `2(N-1)` off-events. A possibly
initially-on light contributes at most one phantom count, which is insufficient
to cause a premature declaration. Use `--actual-initial-on` to simulate that
branch.

Under independent fair random selection the strategy completes with probability
1, but it has no finite worst-case deadline: a particular prisoner could be
skipped for an arbitrarily long time. Each simulated visit performs at most one
light operation, matching the puzzle's restriction.

### Timing, alternatives, and risky deadlines

```bash
PYTHONPATH=src python -m aip prisoners-analysis --count 100 \
  --trials 2000 --false-cost 1000000 --daily-cost 1 \
  --confidences 0.9 0.95 0.99 0.999 \
  --sample-days 500 700 900 1100 1300
```

For `N` prisoners, the expected day on which everyone has physically visited is
the coupon-collector value `N × H_N`. The standard known-off single-counter
protocol has exact expectation `N × H_(N-1) + N(N-1)`: each new signal takes an
average `N/k` days to appear, and each of the `N-1` signals then waits an average
`N` days for the counter. For `N=100`, these are approximately 518.74 and
10,417.74 days respectively.

A blind fixed-day declaration is a deliberately simpler alternative. Its
success probability is exactly the probability that all coupon types have been
seen by that day, but it can never be 100% at any finite day. More sophisticated
zero-error protocols also exist—dynamic counter selection, multiple assistant
counters, staged counting, and binary-token protocols—so the elementary single
counter is easy to prove but is not time-optimal.

An intentionally slower but still zero-error variant lets every non-counter
send the same signal several times and raises the counter's threshold by the
same factor. It adds no information and only delays completion, but demonstrates
that many successful protocols exist. Merely waiting for a calendar deadline is
simpler still, but is a positive-risk policy rather than a puzzle solution.

The analyzer reports the earliest 50%, 90%, 95%, 99%, and 99.9% coverage days.
It also illustrates a cost-based deadline by minimizing
`wait_days × daily_cost + P(error) × false_cost`. This deadline is not universal:
if a false claim means certain collective death, the appropriate false cost is
effectively enormous and the rational zero-error choice is to wait for a valid
light-based proof.

For `N=100` and one unit of cost per waiting day, illustrative error-cost ratios
produce the following fixed deadlines (these are decision assumptions, not new
mathematical guarantees):

| False-claim cost | Chosen day | Probability all visited |
|---:|---:|---:|
| 1,000 | 678 | 89.5585% |
| 10,000 | 916 | 99.0003% |
| 100,000 | 1,146 | 99.9005% |
| 1,000,000 | 1,375 | 99.9900% |

Further reading: [Majerech's one-light retrospective](https://arxiv.org/abs/2208.00771)
surveys faster protocols and reports sub-3390-day average designs. William Wu's
[protocol survey](https://www.ocf.berkeley.edu/~wwu/papers/100prisonersLightBulb.pdf)
develops single-counter, dynamic-counter, two-stage, and binary-token methods.

## Run the sequential case-and-banker lab

```bash
PYTHONPATH=src python -m aip cases --risk-tolerance 100000 \
  --trials 1000 --seed 42
```

The default board contains the 26 standard amounts from 0.01 to 1,000,000. The
player keeps one sealed case, then opens `6, 5, 4, 3, 2, 1, 1, 1, 1, 1` other
cases between offers. The included classroom banker offers 50%, 50%, 60%, 60%,
70%, 70%, 80%, 90%, 99%, and 99% of the remaining mean. Both schedules and all
prizes are configurable Python data.

For remaining values `x₁…xₘ`, the risk-neutral reservation value is
`EV = (Σxᵢ)/m`. A player with constant absolute risk aversion and tolerance `T`
uses the certainty equivalent `CE = -T log[(1/m)Σ exp(-xᵢ/T)]`; lower `T` means
stronger dislike of downside risk. The report also gives volatility, the chance
that the chosen case beats the offer, and the offer/EV ratio. The exact
next-round enumerator shows an important trap: the probability that the next
offer rises is not the same as the expected value of continuing.

The CLI's `deal/no-deal` recommendation is deliberately labeled a reservation
rule: it compares today's offer with the terminal case lottery. Before the last
round, a truly optimal decision also values the option to reject future offers
and therefore needs a specified future banker policy. The simulator supplies a
reproducible behavioral benchmark, not a claim that this simple stopping rule is
the unique dynamic optimum.

Standard U.S.-style play is primarily a decision under uncertainty, not
automatically an asymmetric-information game: the contestant does not know the
case value, but the banker generally appears not to know it either. AIP's
`BankerHypothesis` extension creates the game-theoretic version: the contestant
holds a belief over hidden banker profiles and updates it from each public offer
using Bayes' rule. An unusually high offer raises the posterior probability of a
generous banker; an omniscient banker could instead signal private knowledge of
the chosen case.

The rules, prize table, classroom discount schedule, exponential-utility
calculation, and the distinction between the ordinary U.S. banker and an
omniscient variant follow Timothy Chan's peer-reviewed
[decision-analysis treatment](https://pubsonline.informs.org/doi/10.1287/ited.2013.0104).

## Run the Liar's Dice analyzer

```bash
PYTHONPATH=src python -m aip liars-dice --players 4 --dice-per-player 5 \
  --hand 1 3 3 5 6 --bid-quantity 9 --bid-face 3 --trials 100000
```

Each player's dice are private; bids are public. Under the included common
variant, ones are wild for bids on faces 2–6 but a bid on ones counts only ones.
A legal raise increases quantity, or keeps quantity fixed and increases face.
Rules vary across tables, so wild ones can be disabled and player, hand, and die
sizes are configurable.

Suppose your hand already contributes `s` matches to a claim of at least `q`
matching dice. If `h` dice remain hidden, then the bid is true with probability

`P(X ≥ q-s) = Σ C(h,k)pᵏ(1-p)^(h-k)`,

where `p=2/6` for an ordinary face when ones are wild and `p=1/6` for a bid on
ones (or any face when wilds are disabled). If a correct challenge gains `G`
and a wrong challenge costs `L`, challenging has value
`(1-P(true))G - P(true)L` and is attractive when
`P(true) < G/(G+L)`. With symmetric one-die stakes, the cutoff is 50%.

The module ranks legal raises by their raw chance of being true, then checks the
closed-form probability against seeded Monte Carlo. “Safest raise” is not the
same as equilibrium play: bids also reveal information, influence later bids,
and sometimes need deliberate bluffing to prevent opponents from decoding a
player's hand.

For explicit asymmetric information, AIP adds a transparent two-type model.
An observer starts with a prior that the bidder is honest or a bluffer; credible
bids are more likely under the honest type and incredible bids under the bluff
type. The posterior is computed through the shared `InformationSet` API. This is
a configurable behavioral inference model, not a claim to solve the full
multi-round game, whose equilibrium generally requires mixed strategies and a
much larger game tree. Ferguson and Ferguson's mathematical
[Liar's Dice models](https://www.math.ucla.edu/~tom/papers/LiarsDice.pdf) show
how even reduced variants become nontrivial zero-sum games; Sanford Research's
[one-page rules](https://research.sanfordhealth.org/-/media/research/promise/resources/printables/liars-dice/liars-dice-how-to-play.pdf)
provide a concise conventional rules reference.

## Run the repeated all-pay auction lab

```bash
PYTHONPATH=src python -m aip auction --players 5 --rounds 10 \
  --value 100 --budget 100 --trials 1000
```

This formalizes the *Kakegurui* “100 Votes Auction” as a sealed simultaneous
all-pay auction: a zero bid abstains, every positive integer bid is lost, the
highest bidder receives 100 reusable units, and a tied highest bid is broken
uniformly. The main model now treats bidder identities, bids, and the winning
price as public, while forbidding direct conversation; prices are the only
language. `tacit` and `--social-identity-hidden` preserve the earlier anonymous
information variants for comparison. The auctioneer does not secretly bid.
Changing sequential visibility or allowing auctioneer bids creates a different
game. See the anime's [official rules](https://kakegurui-anime.com/game_rules/).

### 1. Ordinary or bounded-rational players

There is no single prediction without a behavioral model. Players may anchor
near 100, overreact to earlier losses, overbid, abstain too often, imitate past
winners, or conserve cash. Since losers also pay, errors transfer wealth to the
auctioneer and can quickly bankrupt bidders. Early wins replenish a bankroll,
so finite budgets create path dependence and concentration: a lucky rich player
can remain aggressive while poorer players lose the ability to challenge.

The simulator includes `naive`, `cautious`, `equilibrium`, and `cooperative`
modes. The first two are explicit bounded-rational scenarios rather than claims
about universal human behavior.

### Price as the only communication channel

The `tacit` mode treats the public winning price as a noisy shared language:

- price `1`: continue the low-price convention;
- price above `1`: somebody defected, but anonymity hides who;
- after detection: everyone switches to the one-shot mixed-equilibrium
  punishment benchmark for all remaining rounds.

The cooperative role rotates by a public clock and player labels. This rotation
must already be a focal convention; observing a price of 1 proves only that no
one bid above 1, not that every player privately accepted the same agreement.
Thus prices can coordinate behavior and detect a deviation, but cannot create
logical common knowledge of private intentions or support targeted punishment.

```bash
PYTHONPATH=src python -m aip auction --players 5 --rounds 20 \
  --deviation-rate 0.02 --modes tacit equilibrium cooperative
```

For an indefinitely repeated rotating convention, let `delta` be the per-round
discount/continuation factor. A non-designated player can defect with bid 2 and
gain `V-2` immediately. In the worst place in a rotation, their next cooperative
win is `m-1` rounds away. Collective punishment can deter that deviation only if

`delta^(m-1)(V-1)/(1-delta^m) >= V-2`.

For five players and `V=100`, the threshold is approximately `delta=0.8556`.
Below it, future low-price wins are not valuable enough to offset the immediate
98-unit deviation gain. More players raise the threshold because each player
waits longer for their designated win.

### Costly leadership, conformity, and majority enforcement

Pure payoff maximization misses a plausible human coordination mechanism. In
`social` mode, one player first bids `V+1` (101 for a 100-value lot). Winning
costs that leader only 1 net unit, but publicly demonstrates willingness to
break the high-price contest and creates a focal authority. From the next round,
supporters all bid 1. This symmetric rule needs less private coordination than a
rotation: everyone follows the same visible norm, the winner is selected by the
tie rule, and group surplus per round is `V - supporter_count`.

If supporters are a strict majority and individual compliance is attributable,
they expel anyone who does not bid 1. Expulsion converts conformity, fear of
missing future lots, fairness preferences, and willingness to punish into a
real strategic cost. For five supporters and `V=100`, cooperative expected flow
is `100/5 - 1 = 19` per round. A bid-2 defection improves the current expected
payoff by `98 - 19 = 79`; permanent exclusion deters it when
`delta*19/(1-delta) >= 79`, or `delta >= 79/98 ≈ 0.8061`.

```bash
PYTHONPATH=src python -m aip auction --players 5 --rounds 10 \
  --budget 200 --social-supporters 3 --leader-bid 101 \
  --modes social equilibrium cooperative
```

There is an essential observability boundary. A public price above 1 reveals
that someone defected, but a truly anonymous price does not reveal whom to
expel. Targeted majority enforcement therefore requires attributable bids,
observable winner identity, or an external auction rule that can identify
noncompliance. Use `--social-identity-hidden` to remove that channel; the model
then detects rejection through price 2 but cannot remove the rejectors.

With three supporters out of five, the simulated sequence is: price 101 signals
leadership; in the acceptance round supporters bid 1 while two rejectors bid 2;
the majority expels those two; the three remaining members continue bidding 1.
Across ten rounds this produces auctioneer revenue 132 versus roughly 1,014 in
the budget-truncated noncooperative benchmark. This outcome is socially
enforced, not a one-shot Nash equilibrium.

Finite horizons still matter. Exclusion loses force near the final round because
there are fewer future low-price prizes to lose. A final-round defection can be
prevented only by an immediate expulsion penalty, preferences for norm
compliance or fairness, reputational consequences outside the auction, or an
uncertain continuation—not merely by intelligence.

### Competing leaders and competing equilibrium prices

```bash
PYTHONPATH=src python -m aip auction-coordination \
  --candidate 0:101:1 1:105:5 2:130:25 \
  --ideals 1 1 5 25 25 --remaining-rounds 10 \
  --discount 0.9 --leader-bonus 1
```

Each candidate is encoded as `player:public-leadership-bid:proposed-future-price`.
Operationally this represents a two-stage public price code: a fixed candidacy
window records each 101+ commitment, then a fixed proposal window records the
same identified candidate's intended operating price. No spoken message is
needed, but the common clock and code must be known from the auction rules or
learned as a focal convention.
The model deliberately separates two concepts:

1. **Raw dominance:** the highest 101+ bidder controls the current lot.
2. **Legitimacy:** the candidate whose proposed convention wins public pairwise
   majority comparisons becomes the socially recognized leader.

A bid of 101 does not lock leadership. A rival can bid 102, but escalation is
rational only when leadership has private continuation value. If leadership
adds `L` per future round, a guaranteed winner's break-even cap is
`100 + sum(delta^t L)`. Symmetric candidates competing for the same leadership
rent create another all-pay contest, so deterministic escalation can dissipate
the entire future benefit. A fixed candidacy window and majority ratification
prevent an endless 101/102/103 leadership war.

The future norm price should not be encoded mechanically as `100 + price` and
awarded to the highest bid: that would make a proposal of 25 automatically beat
5 and 1 even though it destroys more surplus. Candidate commitment and proposed
operating price are therefore separate public fields.

If `q` symmetric supporters all bid a common price `p`, then

- expected payoff per supporter is `100/q - p`;
- group surplus is `100 - qp`;
- economic participation is positive only when `p < 100/q`.

For five equal participants, price 1 yields 19 each, price 5 yields 15 each, and
price 25 yields -5 each. Thus 1 strictly dominates 5 and 25 on monetary surplus.
Higher norms can still attract human support as entry barriers, status signals,
fairness conventions, or tools favoring wealthier players. Interestingly, the
incremental temptation to defect from common `p` to `p+1` is
`[100-(p+1)] - [100/q-p] = 100(1-1/q)-1`, so merely raising the norm does not
solve the enforcement problem; it mainly burns more group wealth.

When preferences over 1, 5, and 25 are single-peaked, pairwise majority voting
selects the median ideal. With ideals `[1,1,5,25,25]`, no proposal has an
immediate strict first-choice majority, but 5 defeats both 1 and 25 in public
runoffs. A bidder offering 130 for leadership may therefore win raw dominance,
while the bidder proposing 5 becomes the majority-recognized leader. Without a
predeclared rule choosing between “highest bid” and “majority recognition,”
leadership itself remains ambiguous and no unique equilibrium can be inferred.

### 2. Fully rational players

For one continuous-bid round with `m` identical risk-neutral bidders, common
value `V=100`, and nonbinding budgets, there is no symmetric deterministic bid.
The symmetric mixed benchmark has
`F(b)=(b/V)^(1/(m-1))` on `[0,V]`. Consequently each player bids `V/m` in
expectation, total expected bids equal `V`, and each player's expected net
payoff is zero. For five players, the mean bid is 20 and the mean winning bid is
`500/9 ≈ 55.56`, while the auctioneer receives 100 in expectation.

Everyone bidding zero is not an equilibrium because one bidder can profitably
bid 1. A rotating agreement where one person bids 1 creates almost the full
group surplus, but is not self-enforcing: another bidder can bid 2 and steal a
98-unit gain unless sufficiently valuable future price-triggered punishment is
available. Complete-information all-pay auctions can also have asymmetric
equilibria, so “all rational” does not imply one deterministic outcome. See
[Baye, Kovenock, and de Vries](https://repub.eur.nl/pub/12406/).

### 3. A finite number of rounds

In the final round there is no value to preserving budget for later, so the
one-shot all-pay incentives apply. Earlier rounds attach continuation value to
cash: with binding budgets, optimal bids depend on every bankroll, remaining
rounds, public history, tie rules, and whether winnings can be rebid. Rich players
gain strategic endurance, poor players rationally abstain more often, and late
rounds can become more aggressive as the option value of saved cash disappears.

If all budgets are large enough never to bind, independently repeating the
one-shot mixed equilibrium is a subgame-perfect benchmark and dissipates roughly
100 units per round in expectation. With binding budgets it is only a benchmark,
not an exact dynamic equilibrium; the CLI labels its samples accordingly. A
finite horizon also weakens unsupported cooperation because the final round has
no future punishment, and backward-induction pressure propagates toward earlier
rounds.

## Run the bean-taking solver

```bash
PYTHONPATH=src python -m aip beans --min-beans 4 --max-beans 7 \
  --players 5 --min-take 1 --max-take 3
```

The default model has five cyclic players taking one to three beans, with the
last taker losing. Player 1 initially knows only an inclusive pile-size range;
all other players are conservatively treated as a coalition trying to make
player 1 lose. The solver reports safe actions for every exact pile size, their
intersection across the information set, and the action with least worst-case
exposure when an absolute guarantee is impossible.

## Run the moving-worm solver

```bash
PYTHONPATH=src python -m aip worm --holes 5
```

The worm starts in any of five adjacent holes. After every unsuccessful check,
it must move exactly one hole left or right. A breadth-first search over belief
states proves that `2 → 3 → 4 → 2 → 3 → 4` is a shortest guaranteed sequence:
if all first five checks miss, only hole 4 remains possible at the sixth check.
The repeated sweep handles both possible starting parities.

## Architecture notes

`InformationSet[StateT]` is the extension seam for imperfect-information
puzzles. It records all states a player regards as possible, private
observations, public history, and optional Bayesian beliefs. Domain modules
provide the compatibility rule used to eliminate states after an observation.

The modules use the shared information interface without coupling their reasoning styles:

- **Hats:** each public answer becomes a timestamped public observation;
  repeated state elimination models common-knowledge evolution and delay.
- **Beans:** hidden quantities or opponent types live in possible states;
  beliefs can support expected utility while intervals support worst-case play.
- **Worm:** a belief state is the set of holes still reachable after each forced
  move; actions update that set adversarially.
- **Prisoners:** the light is a shared one-bit memory channel; local signal
  quotas and the counter's private state form a distributed protocol.

Puzzle solvers remain self-contained under `puzzles/<name>`, while shared state,
transition, and information abstractions stay dependency-free in `core`.

## Tests

```bash
python scripts/verify.py
```

If Node.js is not on `PATH`, pass it explicitly with
`python scripts/verify.py --node /path/to/node` or set `AIP_NODE`.
