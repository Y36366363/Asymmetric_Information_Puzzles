# AIP — Asymmetric Information Puzzles

## Updates 08/02/2026

- **Adversarial task-4 game mode** — Upgraded the moving-worm game from a
  random simulation to a true worst-case opponent, while retaining random mode
  for comparison and exposing whether capture was lucky or mathematically forced.
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

The lobby currently exposes **命运之箱** and **移动虫穴** as complete
single-player games. In 命运之箱:

1. Choose one of 26 sealed cases to keep.
2. Click other cases to reveal the required number for the current round.
3. Inspect the banker's offer, expected value, certainty equivalent, volatility,
   and probability that the chosen case beats the offer.
4. Accept the deal or reject it and continue opening cases.
5. Review the full decision history and final case value.

In 移动虫穴, choose one of five adjacent holes on every turn. A missed worm
immediately moves exactly one step left or right. **对抗模式** is now the
default and directly implements task 4: the computer keeps every trajectory
that is still legal and always chooses a surviving worst-case branch. It cannot
be beaten by luck—capture occurs only when the selected hole covers every state
left in the public information set. **随机模式** instead commits to one hidden
worm and samples a legal neighboring move after every miss, so early lucky
captures are possible.

The optional minimax sequence is highlighted one step at a time. Following
`2 → 3 → 4 → 2 → 3 → 4` from the beginning guarantees capture within six
checks for five holes. The result screen explicitly distinguishes an ordinary
random capture from a mathematically forced capture against the adversary.

The UI never receives the chosen case's hidden amount before the game finishes.
The Python-side `GameRegistry`, `PlayableSession`, and `LocalGameService`
separate lobby discovery, private state, legal actions, and public snapshots.
Upcoming pirate, Liar's Dice, and auction cards are already registered as
disabled previews; each can become playable by adding its own session adapter
without changing the local server or lobby shell.

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
PYTHONPATH=src python -m unittest discover -s tests -v
```
