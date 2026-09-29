# Swarm governance experiment: pre-registration (written before screening or any swarm run)

Date: 2026-09-27. Separate Squad research experiment. Does not touch the competition results.

## Regime B selection rule (declared before screening)
Screen official ALE SpaceInvaders variations on 12 configs x 6 seeds each (seeds 0-5, dev only).
Candidate order (smallest change first): difficulty 1 (mode 0), then modes 1, 2, 4, 6.
Pick the FIRST variation in that order that meets all three:
 1. the best config under A (by screen mean) is not in the top 3 under B;
 2. at least one A main effect (dodge on-off, fire aimed-ready, or move) reverses sign under B;
 3. mean score over all configs under B is within 0.5x-2x of A (task still recognizable).
If none qualifies: report that, and use the variation with the lowest rank correlation with A, flagged as a deviation.
The final landscapes use fresh seeds (100-139), not the screening seeds, so the choice cannot be tuned to them.

## Hypotheses (from the brief)
H1 shared memory reduces redundant rediscovery / speeds convergence (phase 1).
H2 memory drag after the regime change.
H3 pure decentralization explores well but wastes games after convergence.
H4 pure hierarchy exploits efficiently but converges prematurely / adapts slower after the change.
H5 JEV adaptive governance beats one or both fixed modes.

## Primary outcomes (declared)
- simple regret of the swarm's current pick (true mean of best config - true mean of pick), per round, per phase;
  "true" = mean over all 40 landscape seeds of that regime.
- phase-1 and phase-2 final regret, rounds-to-near-best (regret <= 10 points, held to phase end);
- memory benefit = phase-1 area under regret curve, no-memory minus memory (same governance);
- memory drag = phase-2 area under regret curve, memory minus no-memory (same governance).
Paired by trial seed across conditions. 95% CIs by paired bootstrap; primary comparisons D vs B, D vs C, D vs F, B vs A.
