# Phase 2 tournament-contract audit and non-decisional frontier — RT001 V3

## Outcome

The legacy V2 tournament contract is **not compatible** with the certified RT001 V3 evidence. The V2 finalizer remains valid only for future inputs that actually satisfy its semantics; it is not authorised for the present lineage.

The incompatibility is machine-audited field by field. It is not repaired through proxy substitution:

- `median_gjt_improvement_min` and `lower_quantile_gjt_improvement_min` are missing because municipal work OD has not been spatially allocated to routes/passengers;
- Stage-E deterministic connection retention and miss counts are not `median_missed_connection_probability`;
- final hard eligibility is incomplete because current-service non-regression is known only against a localisable lower bound;
- route count is not silently renamed as public-pattern complexity;
- field-check count and unknown-distance share remain separate quantities rather than an invented `unverified_elements` count;
- retained-stop share remains explicitly labelled as a lower bound;
- there is no integrated final-sensitivity run count;
- the V2 identity `(scenario_id, plan_id)` has only 9,534 unique values for 16,495 plan contexts and would collapse 6,961 budget-qualified exact-timetable contexts.

`decision_budget_km` and `uncertainty_band_min` remain valid caller-declared Decision Contract inputs, but neither has been supplied or defaulted.

## Machine-readable input audit

`legacy_v2_tournament_input_compatibility_rt001_v3.csv` maps all 11 required V2 candidate columns, the budget envelope and both explicit caller inputs to:

- certified source and source field;
- required versus certified semantics;
- availability;
- V2 compatibility;
- permitted V3 use.

The companion JSON records the identity collision count and explicitly sets `legacy_v2_finalizer_run_authorized=false`.

## V3 non-decisional Pareto contract

Because compatibility fails, `config/phase2_nondeci_tournament_frontier_rt001_v3.json` defines a separate contract over supported metrics only:

- identity is `(plan_context_id, selected_timetable_id)`;
- each of the six annual bus-km envelopes is a separate partition, so no decision budget is selected;
- contexts with and without supported BUS_TO_RAIL generalized-access/Stage-E metrics occupy separate evidence-completeness partitions; missing values are never imputed;
- 29 monotonic axes retain service availability, Stage-C accessibility screening, exact Stage-D production, Stage-E engineering retention/block behaviour, field uncertainty and current-continuity lower bounds;
- dominance uses exact decimal comparisons with zero tolerance;
- a row is dominated only when another row is no worse on every applicable axis and strictly better on at least one;
- equivalent metric vectors are all retained and their multiplicity is reported;
- there are no weights, scores, uncertainty-band filtering, ranks or finalist labels.

The resulting 12 partitions contain 16,495 contexts. Exactly 12,284 are non-dominated under this broad evidence-preserving contract and 4,211 are dominated. The large frontier is expected: without normative preferences and without the missing final passenger metrics, Pareto analysis exposes trade-offs rather than resolving them.

## Decision boundary

The V3 frontier is not a substitute for full Passenger GJT, empirical reliability, final hard eligibility or a political/operational choice of budget. It must not be described as a shortlist, ranking or recommendation.

The following remain false:

- `decision_budget_selected`;
- `uncertainty_band_selected`;
- `calendar_selected`;
- `recovery_selected`;
- `primary_selection_authorised`;
- `runner_up_selection_authorised`;
- `weighted_composite_score`.
