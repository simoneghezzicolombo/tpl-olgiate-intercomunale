# Phase 2 — Stage E OLD-vs-NEW Robustness Audit

## Scope

This is an independent semantic audit of two already certified Stage-E lineages:

- legacy Stage E V2, frozen at `a0bd5f01c75c9316eff4977ab9648343e1a7ffbc` on `phase2-final-operational-robustness-v2`;
- RT001 Stage E V3, frozen at evidence commit `063e1190a7be1e948edc7239ab2e5946908afe70` on `phase2-stage-e-rt001-v3-final-a`;
- the raw Stage-D V3 evidence consumed by the final Stage E is frozen at `d41bb678382d018929c1c6b46542f12549f20d4f`.

The audit does **not** run a final tournament and does not rank or select a topology, budget, calendar, recovery value, PRIMARY or RUNNER-UP.

## Semantic identity

Old and new exact timetables are compared through a canonical identity composed of:

1. `scenario_id`;
2. topology family;
3. route set with each route paired to its selected integer phase;
4. uniform headway;
5. declared service span `[span_start_min, span_end_min)`.

Route/phase pairs are canonicalised by route ID, so a harmless row-order change cannot create a false mismatch. A second phase-free base identity is retained to distinguish context-dependent RT-001 phase splitting from an upstream addition/removal of a service problem.

The audit separately verifies the operational trip universe for every common semantic timetable using route, trip ordinal, selected route phase, exact departure and exact vehicle return. This prevents two timetables with the same high-level label but different materialised trips from being treated as fully interchangeable.

## RT-001 context-dependent timetable splitting

Stage D V3 maps all 16,495 plan contexts to `selected_timetable_id`. The audit recomputes the set of source `stage_d_input_id` values that map to more than one selected timetable and fails closed unless the result is exactly the certified **634** source inputs.

The output `rt001_context_split_inputs.csv.gz` retains, for every split source input, all selected timetable IDs, represented plan-context count, budget suffixes, calendar IDs and selected phase vectors. No budget or calendar is selected.

## Robustness comparison

For semantic timetables present in both lineages, the audit compares the Stage-E robustness surface using the full key:

`semantic timetable × transfer profile × connection type × direction × perturbation dimension × engineering stress`

The compared evidence includes planned connection counts, retained and missed planned connections, retention share, nominal transfer evidence, useful-connection gaps, service-gap increase and alternative-after-miss descriptors.

BUS→RAIL is checked independently at deterministic runtime stresses `0 / +5 / +10 / +15` minutes. These are engineering sensitivity cases only. They are **not** empirical delay probabilities.

RAIL→BUS is checked independently by transfer profile and direction at the only certified rail-arrival case, `0` minutes. The audit does not manufacture a non-zero rail-delay distribution.

## Vehicle-block comparison

The audit compares every common semantic timetable at each recovery value `5 / 10 / 15` and every runtime engineering stress `0 / +5 / +10 / +15`. It checks:

- nominal Stage-D fleet;
- exact minimum vehicle requirement under stress;
- maximum simultaneous vehicle requirement;
- additional vehicle requirement;
- conflicts on nominal blocks;
- turnaround violations;
- nominal block infeasibility;
- hub-turnaround and block-slack descriptors.

An operationally identical common timetable with a block mismatch is a fail-closed condition.

## `[span_start, span_end)` passenger-return audit

Legacy Stage D V2 materialised `public_hub_return_min` for every publicly returning trip even when that return occurred at or after `span_end_min`. Legacy Stage E therefore had no input-level span filter for those returns.

Stage E V3 corrects the interface before calling the unchanged robustness kernel: a physical/public return is exposed as BUS→RAIL passenger service only when

`span_start_min <= public_return_min < span_end_min`.

The audit therefore performs two independent checks:

1. it enumerates every legacy raw public return outside the declared service span, then scans the legacy Stage-E connection audit to quantify exactly how many BUS→RAIL candidate rows and planned connections were created from those events, separated by transfer profile and direction;
2. it enumerates the corresponding class of physical V3 return events from raw Stage-D V3 trips and asserts that **zero** such events appear as BUS→RAIL passenger-source rows in final Stage E V3.

Technical vehicle returns remain a vehicle-block concept only and must never be passenger service.

## Difference classes

The audit does not infer a cause merely from different aggregate row counts. Timetable-level changes are classified conservatively as:

- `UNCHANGED_CASE`;
- `UNCHANGED_COMMON_PHASE_WITHIN_RT001_CONTEXT_SPLIT`;
- `OUT_OF_SPAN_PUBLIC_RETURN_CORRECTION`;
- `OUT_OF_SPAN_PUBLIC_RETURN_CORRECTION_WITHIN_RT001_SPLIT`;
- `RT001_CONTEXT_SPLIT_NEW_PHASE`;
- `RT001_CONTEXT_SPLIT_REPLACED_LEGACY_PHASE`;
- `RT001_PHASE_RESELECTION_WITHOUT_CONTEXT_SPLIT_*`;
- `CHANGED_TIMETABLE_TRIP_UNIVERSE_*`;
- `UNEXPLAINED_COMPARABLE_MISMATCH`.

A BUS→RAIL robustness mismatch is attributed to the span correction only when the semantic timetable and materialised operational trip universe are otherwise identical and the legacy timetable actually contains at least one out-of-span public return. RAIL→BUS and vehicle-block mismatches are never excused by the passenger-return correction.

## PASS semantics

`PASS_PHASE2_STAGE_E_OLD_VS_NEW_ROBUSTNESS_AUDIT` means:

- all input evidence is certified and lineage hashes close;
- the 634 context-split Stage-D inputs are independently recovered;
- semantic comparison completed across common timetables, profiles, directions, connection types, stresses and recoveries;
- V3 has zero out-of-span BUS→RAIL passenger-service leaks;
- V3 has zero technical-return passenger-service leaks;
- no unexplained robustness mismatch remains for operationally equal common timetables;
- no unexplained nominal RAIL→BUS mismatch remains;
- no unexplained vehicle-block mismatch remains;
- deterministic rebuild is byte-identical;
- no decisional or demand semantics were introduced.

PASS does **not** mean that legacy and repaired lineages have identical aggregate counts. RT-001 deliberately changed the exact timetable universe and the span correction deliberately removes invalid legacy passenger-return events.

## Prohibited in this audit

The audit creates no ridership observations, municipal OD allocation, passenger weights or synthetic observations. It does not create or infer `demand_weighted_gjt_improvement_min`, `missed_connection_probability` or any other probability/utility field unsupported by the certified evidence.

The final readiness/tournament implementation is outside this branch. Once that implementation lands, it must be independently red-teamed against these epistemic boundaries before any decision contract is accepted.
