# GTO routing update — 2026-10-07

## Decisions

Today's work resolves three open routes without weakening any certification
gate.

1. **Four-card Love Letter belief updating: stop.** After acquisition-order
   equivalent worlds are merged, 12 opening information sets have two hidden
   states but no observed opponent action. All 48 post-action information sets
   have singleton strategic hidden-state support. The subgame remains an exact
   GTO/value-decomposition control, not a belief-update target.
2. **Full-round Love Letter: continue.** The resumable audit advanced by 50,000
   histories to 1,541,622 histories, 693,380 terminals and 220,373 information
   sets. No structural failure is recorded, but 71 frontier nodes remain and
   certification is still false.
3. **Five-die Liar's Dice: split the scope.** The live arbitrary-raise mode
   remains heuristic. A separate two-player, five-die, wild-one, stepwise-bid
   contract is frozen for a future adapter and independent audit.

## Why these routes differ

The Love Letter full round already has a tested adapter, persistent frontier
and accumulating structural evidence, so continued bounded enumeration is
productive. Its frontier count may fluctuate and is not a completion percent.

The unchanged live five-die Liar game has about `1.15e18` possible nonempty bid
histories and an information-set lower bound near `2.91e20`; starting tabular
CFR would produce an unauditable claim. The new stepwise contract cuts this to
345 public chains and an estimated 43,881,265 complete histories. That scale
still requires resumable auditing and likely external-sampling MCCFR, but it is
a concrete engineering target rather than an open-ended tree.

## Next milestones

- Implement `five_die_liar_two_player_stepwise_v1` as a separate adapter using
  all 252 lossless five-die histograms.
- Measure information-set consistency and actual tree size before training.
- Add complete histogram-state best response; do not use MCCFR regret as the
  certificate.
- Continue full Love Letter in fixed bounded chunks until structural closure,
  then reassess whether exact sparse sequence form fits or MCCFR is required.
- Do not run another four-card Love Letter posterior manipulation simply by
  changing coefficients or inventing a private-history signal.
