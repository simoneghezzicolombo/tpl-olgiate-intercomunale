# Gate F robust Pareto and uncertainty policy

Gate F must not turn uncertain upstream estimates into false precision. The point-estimate Pareto frontier is retained as a descriptive diagnostic, but a definitive automatic recommendation is based on a stricter **interval-robust frontier** whenever all upstream Gates are PASS.

## Uncertainty convention

For an objective `<metric>` classified `ESTIMATE`, Gate F accepts optional columns:

- `<metric>__lower`
- `<metric>__upper`

A definitive recommendation requires finite bounds for every `ESTIMATE` objective. If an estimate has no bounds, Gate F returns `PROVISIONAL / NO_DEFINITIVE_RECOMMENDATION_UNCERTAINTY` even if its point value appears to dominate another scenario.

The interval is not invented by Gate F. It must be produced and sourced by the upstream method that generated the estimate.

## Robust dominance

For objectives to maximize, scenario A robustly dominates B only if the **worst case** of A is at least the **best case** of B on every objective, with strict superiority on at least one objective.

For objectives to minimize, the inequality is reversed through the corresponding utility transformation. In practical terms, A's worst plausible cost/time/resource use must still be no worse than B's best plausible value on every minimized objective.

This deliberately makes robust dominance difficult. Overlapping uncertainty intervals preserve both scenarios on the robust frontier rather than manufacturing a winner.

## What this is not

- not Monte Carlo;
- not a weighted score;
- not a probability that a scenario is best;
- not an excuse to create arbitrary confidence intervals;
- not a replacement for sensitivity analysis upstream.

Gate F also retains leave-one-objective-out analysis, which asks whether non-dominance survives removal of one objective. It is weight-free and remains a robustness diagnostic, not a ranking.

## Eligibility before Pareto

Gate D road feasibility is a hard constraint. `road_feasible = false` excludes a scenario before Pareto comparison and produces an auditable exclusion row. A road-infeasible topology cannot compensate for physical infeasibility through better coverage, frequency or cost metrics.

## Audit outputs

The Gate F runner writes:

- `pareto_frontier.csv`: point frontier, leave-one-objective-out robustness and, when estimations are bounded, robust frontier flags;
- `tradeoffs_vs_baseline.csv`: metric deltas relative to the validated baseline row;
- `dominance_pairs.csv`: explicit point-estimate dominator/dominated relations;
- `epistemic_audit.csv`: one row per scenario/objective with gate, unit, status, source and uncertainty bounds;
- `objectives.json`: declared objective directions, gates and units;
- `verdict.json`: dependency/evidence blockers and recommendation state.

Scenario names and topology-family labels are metadata only. They never enter the dominance calculation.
