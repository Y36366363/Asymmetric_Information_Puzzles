# Love Letter combinatorial prior audit — 2026-09-29

## Result

The certified four-card Love Letter subgame now has an explicit two-stage belief
model for all 17 equilibrium positive-reach information sets:

`combinatorial chance prior × fixed opponent-policy reach -> conditioned posterior`

The base prior is generated from the audited extensive-form adapter. It does not
reuse Goofspiel's experimental uniform-action baseline and does not infer a prior
from the equilibrium posterior.

## Construction

The traversal carries two independent masses to every decision state:

1. **chance reach** multiplies only adapter chance probabilities;
2. **opponent-policy reach** multiplies only the fixed opponent's behavioral
   action probabilities.

At the acting player's information set, their own actions are traversed with unit
counterfactual weight. States are grouped by the existing `hidden_world` contract.
For each hidden world (w):

- `base_prior(w)` is its chance mass divided by total chance mass;
- `policy_reach_weight(w)` is conditioned mass divided by chance mass;
- `posterior(w)` is the normalized product of those two quantities.

The chance distributions come from the game adapter. In a full Love Letter deal,
they use the count of each remaining card divided by the total remaining cards,
after burn cards, face-up removals, deals, draws and Prince redraws. Public actions
and the acting player's private history select the appropriate information set;
they are not assigned invented likelihoods.

## Four-card subgame findings

- 60 total information sets remain independently covered by action values.
- 17 have positive reach under the exact equilibrium and receive conditioned
  decompositions.
- 43 have zero opponent reach and still receive no fabricated posterior.
- Every positive-reach state has two hidden-world arrangements.
- Because the subgame uses one copy each of Guard, Priest, Baron and Handmaid,
  those two arrangements have equal chance mass. The resulting numerical base
  prior is `0.5 / 0.5`, but this is an output of the 24 equiprobable deal/draw
  orders—not an assumed uniform action distribution.
- On this particular 17-state equilibrium panel, all relevant opponent-policy
  reach weights are equal, so the conditioned posterior equals the combinatorial
  prior. Thus the panel is valid for card accounting and value decomposition, but
  by itself does not create a nontrivial belief-update manipulation.

## Independent checks

The permanent tests verify that:

- the 17/43 reach partition remains exact;
- every base prior normalizes and reconstructs the posterior through Bayes'
  product rule;
- all opening information sets correspond to two `1/24` chance-mass histories;
- current hands, hidden hand, remaining deck and publicly played cards reconstruct
  exactly the multiset `{1,2,3,4}` at every positive-reach state;
- public histories in contributing states exactly match the information-set key;
- replacing the equilibrium profile with a uniform behavioral profile changes
  policy reach and makes all 60 information sets reachable, while the base prior
  of the original 17 information sets remains unchanged;
- exact action values, additivity and independent best-response certification are
  unchanged.

The updated artifact is
`research/results/value_decomposition_audit_2026-09-25.json`; its audit passes
with zero Love Letter Bayes reconstruction error, zero value reconstruction error
and zero additivity residual.

## Next experimental choice

Before making model calls, freeze one of two estimands:

1. keep the exact-equilibrium 17-state panel, honestly treating it as a
   combinatorial-card-tracking and value-composition check with no posterior
   shift; or
2. preregister a fixed, non-equilibrium full-support opponent policy so policy
   reach produces nontrivial belief updates. That policy must be fixed before
   results are observed and must not be presented as GTO.

The second option is more informative for belief updating. A tremble policy can
also cover the 43 currently zero-reach information sets, but it changes the
reference distribution and must remain a separately labeled experiment.

## Full-round boundary

The full-round structural traversal advanced independently to 1,352,853
histories, 195,167 observed information sets, depth 26 and 73 frontier nodes,
with zero structural failures. It remains incomplete and uncertified; no runtime
or ε-GTO label changed.
