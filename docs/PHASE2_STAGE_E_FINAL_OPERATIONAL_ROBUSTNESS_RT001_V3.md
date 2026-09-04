# Phase 2 — Stage E Final Operational Robustness RT-001 V3

## Scope

This workstream reruns the already certified Stage-E planned-connection-preserving robustness engine on the repaired RT-001 exact-timetable lineage.

It does not change the Stage-E mathematical kernel and it does not select a budget, calendar, recovery, topology, PRIMARY or RUNNER-UP.

Branch: `phase2-stage-e-rt001-v3-final-a`

## Robustness unit after RT-001

RT-001 makes `stage_d_input_id` insufficient as a final exact-timetable key. One daily timing problem may contain budget/calendar contexts whose exact hard-cap-feasible optimum has a different route phase vector.

The final Stage-E robustness unit is therefore:

`selected_timetable_id`

The Stage-D V3 lineage currently contains:

- 5,325 daily timing problems;
- 16,495 represented Stage-C plan contexts;
- 6,772,755 exhaustively evaluated phase vectors;
- 6,000 distinct selected exact timetables in the Codex implementation;
- 634 daily timing problems with more than one budget/calendar-specific selected phase vector;
- 285,748 exact public trips in the Codex implementation.

Stage E must process the distinct exact timetable universe, not collapse it back to 5,325 daily input IDs.

## Lossless context mapping

Stage E emits a dedicated mapping artifact:

`stage_e_plan_context_map_rt001_v3.csv.gz`

It preserves:

- `plan_context_id`;
- `plan_id`;
- `selected_timetable_id`;
- original `stage_d_input_id`;
- scenario and topology identity;
- budget identity;
- calendar identity and annual service days;
- exact annual production and its hard cap.

Every Stage-C context must map to exactly one selected exact timetable and every selected exact timetable must represent at least one context.

## Engine preservation

The files below remain byte-identical to the certified Stage-E readiness parent:

- `src/phase2_final_operational_robustness_v2.py`;
- `scripts/phase2_build_final_operational_robustness_v2.py`;
- `config/phase2_final_operational_robustness_v2.json`.

The V3 adapter only translates the repaired exact-timetable schema into the already certified engine interface and relabels the resulting exact-unit key as `selected_timetable_id` in final V3 artifacts.

No connection-planning, miss-retention, alternative-connection or block-sensitivity formula is changed.

## Passenger-return semantics

Stage-D V3 `public_service_end_min` is treated as a public hub return only for a route whose certified route semantics explicitly have `bus_to_rail_passenger_event_supported=true`.

For open routes whose public service ends away from the hub, `public_service_end_min` is not converted into a BUS→RAIL event. The later technical vehicle return remains available for vehicle blocking only.

This preserves the existing no-technical-return-leakage contract.

## Vehicle blocks

The canonical Stage-D V3 input for this Stage-E rerun must provide exact per-trip nominal block identity for all declared recovery values 5/10/15 minutes.

The Codex Stage-D V3 evidence does so. Stage E verifies at zero runtime stress that the nominal block assignment reproduces the Stage-D exact fleet count independently for each recovery value before running stressed cases.

No block assignment may be inferred heuristically.

## Sensitivity provenance

The repaired Stage-D V3 validation does not itself re-declare the runtime stress grid. Stage E therefore keeps the runtime sensitivity provenance explicit and separate:

- bus runtime stress: `0/+5/+10/+15` minutes, inherited unchanged from the previously certified Stage-D/Stage-E engineering-sensitivity contract;
- recovery: `5/10/15` minutes, present in the repaired exact Stage-D V3 evidence;
- rail arrival delay: `0` only, because no certified non-zero rail-delay sensitivity contract exists in the current lineage.

The bus runtime and recovery cases are deterministic engineering sensitivities. They are not empirical probabilities and do not constitute a stochastic delay model.

## Stage-D cross-implementation prerequisite

A final Stage-E V3 run must fail closed unless the independent Stage-D V3 cross-implementation audit is PASS with zero decision-relevant differences in:

- plan-context coverage;
- selected phase vector;
- exact daily and annual bus-km;
- hard-budget eligibility;
- S8 objective values;
- exact fleet counts 5/10/15;
- semantic timetable universe;
- exact public-trip timing.

Implementation-specific timetable ID prefixes are not substantive differences because comparison is made on `plan_context_id` and `(stage_d_input_id, phase vector)`.

## Decision boundary

Stage E produces operational robustness evidence only.

`primary_selection_authorised=false`

`runner_up_selection_authorised=false`

Final selection remains blocked until the downstream robustness tournament and Decision Contract are explicitly executed.