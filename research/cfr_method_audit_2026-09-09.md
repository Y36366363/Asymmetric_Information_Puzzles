# CFR method-selection audit — 2026-09-09

> **2026-09-13 update:** The original immediate-update full-tree traversal was
> chance-order dependent. It has been replaced by per-player batched traversal;
> see `batched_full_tree_cfr_2026-09-13.md`. External-sampling MCCFR was not
> changed by that correction.

## Conclusion

The local regret update and reach weighting match vanilla alternating CFR for a
finite two-player zero-sum extensive-form game. The average policy—not the current
regret-matching policy—is exported, consistent with the original CFR result. The
one-die chance sampler samples the root deal from its true distribution and then
traverses every player action, so it is an unbiased root chance-sampling
specialization. As of 2026-09-11, the shared engine also contains a general
external-sampling MCCFR trainer that samples chance events anywhere in the tree
and opponent actions while traversing every action of the updating player.

The framework is therefore a sound small-game baseline, but it must not become a
universal solver. The original CFR guarantee is for regret minimization in
two-player zero-sum imperfect-information games, while sequence form can solve a
small perfect-recall two-player zero-sum tree by a linear program whose size is
linear in the game tree. MCCFR is the standard extension when full traversal is
too expensive, and CFR+ or discounted variants are reasonable performance
comparators—not substitutes for independent exploitability measurement.

Primary references:

- [Zinkevich et al., Regret Minimization in Games with Incomplete Information](https://papers.nips.cc/paper_files/paper/2007/file/08d98638c6fcd194a4b1e6992063e944-Paper.pdf)
- [Lanctot et al., Monte Carlo Sampling for Regret Minimization in Extensive Games](https://proceedings.neurips.cc/paper/2009/file/00411460f7c92d2124a67ea0f4cb5f85-Paper.pdf)
- [von Stengel, Efficient Computation of Behavior Strategies](https://www.sciencedirect.com/science/article/pii/S0899825696900500)
- [Tammelin, Solving Large Imperfect Information Games Using CFR+](https://arxiv.org/abs/1407.5042)
- [OpenSpiel's independent best-response and NashConv implementation](https://github.com/google-deepmind/open_spiel/blob/master/open_spiel/python/algorithms/exploitability.py)

## Framework findings and changes

1. **Mathematical update: pass.** Vanilla traversal uses opponent and chance reach
   for counterfactual regret and own/chance reach for average-policy accumulation.
   Alternating player updates and normalized chance traversal are appropriate.
2. **Independent metric: pass.** Liar's Dice uses an exhaustive best response that
   groups hidden worlds by the responder's information set. Its reported epsilon
   is half NashConv, matching the conventional two-player constant-sum definition.
3. **Eligibility metadata: fixed.** The gate now refuses certification without an
   explicit declaration of two players, finiteness, zero/constant-sum utility, and
   perfect recall. This prevents accidental use on the multiplayer general-sum
   auction and investment games.
4. **Malformed evidence: fixed.** The gate rejects negative/non-finite regret,
   mismatched visit keys, extra information sets in exact adapters, invalid policy
   distributions, and negative/non-finite exploitability. Trainers reject duplicate
   actions, duplicate chance outcomes, and non-finite terminal utility.
5. **Sampling scope: extended on 2026-09-11.** `ChanceSamplingCFRTrainer` remains
   intentionally root-only. `ExternalSamplingCFRTrainer` now supports later chance
   nodes and has been calibrated on a synthetic later-private-chance game and Kuhn
   Poker. This removes a solver limitation, but it does not supply Love Letter's
   still-missing complete extensive-form adapter or independent best-response oracle.

## Cross-seed stability test

At 10,000 iterations, all four tested seeds passed the hard independent
exploitability ceiling, ranging from `0.004709` to `0.008774`. One seed failed the
separate `0.03` average-positive-regret diagnostic at `0.037175`. This showed that
the old training budget was not robust enough for the complete promotion gate.

The budget was raised rather than the threshold weakened. The two stressed seeds
retested at 20,000 iterations passed: seed `20260909` reached exploitability
`0.002473` and regret `0.026064`; seed `7` reached `0.004552` and regret `0.013127`.
The reissued runtime artifact (seed `20260908`) covers all 348 information sets,
has minimum visitation 3,193, regret diagnostic `0.011446`, and exploitability
`0.002354`.

## Per-game method comparison

| Local game | CFR fit | Standard method comparison | Decision |
| --- | --- | --- | --- |
| Kuhn Poker | Strong | Sequence-form LP or closed-form equilibrium is exact at this size | Keep exact live policy; retain CFR as calibration test |
| One-die stepwise Liar's Dice | Strong | Sequence-form LP would be the best independent exact-policy comparator; exhaustive best response already certifies the learned profile | Keep ε-GTO; add sequence-form cross-check before expanding rules |
| Five-die Liar's Dice | Theoretically strong, tree much larger | MCCFR/CFR+ plus abstraction is more suitable than tabular full traversal | Keep heuristic until a separately scoped model and oracle exist |
| Single-round E-Card | Implemented on 2026-09-10 | Its sequence form collapses to an exactly solved 5×5 matrix; CFR reproduces it within ε=0.006 | Keep exact matrix as primary; separate cross-round adaptation |
| Two-player Love Letter | Strong only for a complete, perfect-recall round model | Later chance events favor external-sampling MCCFR; sequence form is the exact small-tree baseline | Reasonable second target after exhaustive rules/state validation |
| Goofspiel (4 cards) | Valid but unnecessary | Backward induction plus exact zero-sum matrix solving is exact | Keep current solver |
| Restricted RPS | Valid but unnecessary | Backward induction plus exact matrix minimax is exact | Keep current solver |
| Moving Worm | Poor | Belief-state adversarial BFS gives a shortest guaranteed policy | Keep proved search solution |
| Guess Who | Poor | Belief-state dynamic programming directly minimizes expected questions | Keep exact DP |
| Mastermind | Poor | Active information search/minimax partitioning matches the objective | Improve bounded search; do not call it GTO |
| Blackjack | Poor | This is a single-agent stochastic control problem; dynamic programming/EV tables are standard | Add exact scoped EV tables |
| Cases of Fate | Poor | Bayesian decision analysis under a declared utility function is appropriate | Keep risk/EV analysis |
| Pirate Council | Poor | Perfect-information backward induction directly solves the stated voting assumptions | Keep backward induction |
| Battleship | Theoretical only for a reduced model | Full tabular CFR is intractable; belief search/IS-MCTS or a very small MCCFR benchmark is more realistic | Keep heuristic; consider a reduced-board research adapter |
| Hidden Pursuit | Possible only after formalizing both players' information and payoff | Belief-state minimax/DP is preferable on the current small graph | Formalize a reduced zero-sum model before choosing CFR |
| Investment tournament | Unsupported | Six-player general-sum play lacks the two-player zero-sum CFR-to-Nash guarantee; fixed-opponent evaluation is an MDP | Keep Kelly/survival labels; do not use this CFR gate |
| All-pay auction | Unsupported | Multiplayer/general-sum equilibrium or correlated-equilibrium methods are required | Do not route through vanilla CFR |

## Next implementation order

1. Preserve the exact single-round E-Card matrix and CFR cross-check added on
   2026-09-10; expose an exact mode only if cross-round adaptation is disabled.
2. Add a general sequence-form LP oracle when a lightweight dependency policy is agreed.
   Use it to cross-check Kuhn and one-die Liar's Dice values and policies.
3. Before Love Letter, build exhaustive transition/information-set tests, then wire
   the complete round model to the now-available external-sampling MCCFR trainer and
   certify it with an independent best-response traversal.
4. Treat reduced Battleship or Hidden Pursuit as separate research games with new
   rules and certificates. Do not transfer ε claims from reductions to full modes.
