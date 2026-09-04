# Phase 2 final-tournament readiness — RT001 V3

## Outcome

The readiness audit passes, but the final tournament remains **BLOCKED**. The audit joins the repaired Stage-C RT001 V3 evidence to the cross-audited exact Stage-D lineage and the final Stage-E robustness outputs without ranking or selecting a network.

The materialised join contains:

- 16,495 budget-qualified plan contexts;
- 6,000 distinct exact selected timetables;
- all 646 Stage-C frontier contexts recovered by the RT-001 repair;
- six exact annual bus-km envelopes: 89,135.2; 100,277.1; 111,419.0; 122,560.9; 133,702.8; and 144,844.7 km/year;
- Stage-C accessibility screening, exact Stage-D annual bus-km, Stage-E deterministic connection retention and block sensitivity, and the certified current-service continuity lower bound kept as separate dimensions.

No weighted composite score is calculated. No decision budget, uncertainty band, calendar, recovery value, PRIMARY or RUNNER-UP is selected.

## Why the final tournament is blocked

The existing finalizer requires real `CandidateEvaluation` rows. Those rows require robust demand-weighted GJT and a missed-connection probability. Neither quantity is present in the certified lineage:

1. the passenger journey universe remains at municipal-OD resolution, reports `full_gjt_ready=false`, and has no authorised spatial allocation to candidate routes;
2. Stage E reports deterministic retention under explicit engineering stress. It explicitly does not estimate an empirical delay distribution or missed-connection probability;
3. the required Stage-F sensitivity set is incomplete: dwell variation, bus-runtime decrease, non-zero rail delay and route-level demand-weight perturbation are absent;
4. current-service continuity is a certified localisable lower bound, not a complete non-regression proof;
5. the Decision Contract still requires caller selection of one materialised budget envelope and a finite non-negative uncertainty band.

Using resident catchment population as route demand, allocating municipal OD to routes without evidence, or converting the four deterministic delay cases into probabilities would fabricate decision inputs and is prohibited.

## Outputs

- `final_tournament_context_readiness_rt001_v3.csv.gz`: lossless context-level evidence join. Stage-E retention columns are explicitly labelled `engineering`; blank bus-to-rail values mean that no planned bus-to-rail connection was present for that timetable/profile, not zero retention.
- `final_tournament_budget_envelopes_rt001_v3.csv`: available budget envelopes and their context/timetable coverage. Every row keeps `decision_budget_selected=false`.
- `final_tournament_sensitivity_readiness_rt001_v3.csv`: required Stage-F/Decision-Contract dimensions, available grids and missing evidence.
- `final_tournament_readiness_rt001_v3_validation.json`: lineage hashes, exact counts, blockers and the non-selection boundary.

## Decision boundary

`scripts/phase2_build_final_tournament_readiness_rt001_v3.py` never imports or calls `scripts/phase2_finalize_tournament.py`. It does not create the candidate metrics expected by that finalizer. Once the missing empirical/evaluated inputs exist and the two explicit policy inputs are supplied, the existing finalizer can be run as a separate, auditable decision action.
