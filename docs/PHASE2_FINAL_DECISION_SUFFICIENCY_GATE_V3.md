# Phase 2 final decision sufficiency / blocker closure gate V3

## Purpose

This gate closes the **blocker-discovery phase**. It does not select a network.

Its purpose is to stop the recursive pattern in which completing one technical task creates several new tasks merely because an older schema expected unsupported fields. Every currently known requirement is assigned one of five states:

- `CLOSED`
- `CLOSED_WITH_CERTIFIED_BOUND`
- `OPEN_DATA_EVIDENCE`
- `HUMAN_DECISION_REQUIRED`
- `NOT_REQUIRED_UNDER_V3_CONTRACT`

The blocker universe is frozen after this audit. A new engineering blocker can be added only by reopening the gate because of a certified validation failure, an explicit requirement of the finally selected Decision Contract that has no certified source, or a certified lineage contradiction.

## Certified evidence consumed

The gate consumes the certified RT001 V3 lineage and independent audits already completed:

- Stage D lossless exact timetable lineage as certified through final Stage E and its Stage-D cross-implementation requirement;
- Stage E RT001 V3 planned-connection and vehicle-block robustness;
- A's semantic Stage E OLD-vs-NEW audit;
- Codex final-tournament readiness and legacy-contract audit;
- Codex non-decisional Pareto frontier plus A's independent red-team;
- Stage F Engineering Sensitivity RT001 V3;
- Current Service Access Baseline V3.

The separate `phase2-gjt-identifiability-bounds-v3` workstream is **not consumed as certified evidence** by this gate because, at gate definition time, it had no GitHub Actions certification or persisted certified validation. The GJT availability boundary is taken from the already certified final-tournament readiness and legacy-contract audits.

## What Stage F actually closes

Stage F is now a certified PASS over all 6,000 exact timetables and 16,495 plan contexts. It materializes 81 deterministic engineering cases per timetable using:

- bus runtime multiplier `0.9 / 1.0 / 1.1`;
- dwell `0 / 0.5 / 1.0` minutes per non-hub public stop occurrence;
- rail clock shift `-5 / 0 / +5` minutes;
- the three certified transfer profiles;
- recovery `5 / 10 / 15` minutes for vehicle-block sensitivity.

This closes the **engineering sensitivity** sub-blocker. It does not create empirical delay probabilities, route-level passenger weights, demand-weighted GJT or ridership.

## Current-service baseline V3

Current Service Access Baseline V3 strengthens the certified lower bound from 12 to **15 localized PDF stop rows out of 51**, leaving **36 unresolved/unlocalized**. Its contract still states:

`CERTIFIED_LOCALIZABLE_LOWER_BOUND_ONLY`

Therefore the lower-bound reference itself is considered `CLOSED_WITH_CERTIFIED_BOUND`. A claim of complete candidate-vs-current ordering or true current-service non-regression remains unsupported unless additional evidence is obtained.

The V3 safeguard is narrower and valid: a candidate may be rejected for regression below the **proven localizable current lower bound**; unresolved current stops cannot promote or reject a candidate.

## Two decision pathways, neither selected

### 1. `LEGACY_V2_FULL_EVIDENCE`

Retain the old evaluated-candidate semantics. This pathway remains blocked by four data-evidence requirements:

1. complete current-service non-regression / fair current-vs-candidate ordering;
2. full candidate-level demand-weighted GJT;
3. empirical missed-connection probability;
4. route-level demand-weight perturbation sensitivity.

After those exist, the caller must still supply the decision budget and uncertainty band.

### 2. `V3_CERTIFIED_METRICS_DETERMINISTIC_ROBUSTNESS`

This pathway uses only quantities the project can currently certify:

- Stage-C accessibility and equity descriptors;
- exact Stage-D production;
- Stage-E and Stage-F deterministic engineering robustness;
- field/operational uncertainty descriptors;
- explicitly labelled current-service lower-bound evidence.

Under these semantics the four legacy/full-passenger data gaps are not reinterpreted or imputed. They are `NOT_REQUIRED_UNDER_V3_CONTRACT` because the V3 pathway would make **no claim** of full demand-weighted GJT, empirical missed-connection probability, route-level demand sensitivity or complete-current-service non-regression.

This pathway currently has **zero additional technical data blockers**, but it is still not authorized for final selection. Simone must explicitly choose this decision semantics, select a certified bus-km envelope, decide the uncertainty-band semantics/value if retained and provide an explicit no-weight normative decision rule over the remaining trade-offs.

## Pareto frontier boundary

The 12,284 descriptive Pareto-frontier contexts and 4,211 descriptive nonfrontier contexts do not form a shortlist. A's red-team established:

- `frontier_membership_may_authorize_pruning=false`
- `nonfrontier_pruning_authorized=false`

All **16,495** contexts therefore remain preserved until a separately certified final decision contract authorizes elimination.

## Decision boundary

This gate may say that a technical blocker is closed, bounded, not required under a specific V3 contract or genuinely dependent on new evidence. It may also identify human choices. It may not:

- rank topologies;
- fabricate GJT or passenger demand;
- turn deterministic stress into probability;
- relabel lower-bound current-service evidence as complete;
- select a budget, uncertainty band, calendar, recovery, PRIMARY or RUNNER-UP;
- create hidden weights;
- create a new engineering task merely because a legacy field is absent.

The next action after this gate is intentionally finite: **choose the final decision semantics pathway**. Everything after that follows one of the two explicit branches in the machine-readable pathway summary.
