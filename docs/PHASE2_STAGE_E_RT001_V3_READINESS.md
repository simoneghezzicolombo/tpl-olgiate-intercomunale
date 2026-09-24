# Phase 2 — Stage E RT-001 V3 interface readiness

## Status

**Readiness workstream only.** This document does not certify a new final Stage-E run and does not authorise PRIMARY / RUNNER-UP selection.

Branch: `phase2-stage-e-rt001-v3-readiness`

Upstream state at creation:

- Stage E Final Operational Robustness V2 is already technically PASS on the old certified Stage-D fixture.
- RT-001 has been repaired upstream through a lossless Stage-D input manifest V3.
- The repaired manifest contains plan contexts that share one daily `(scenario_id, headway, span)` problem while retaining distinct budget and calendar memberships.
- Exact Stage-D V3 remains an independently certified upstream dependency. Stage E does not infer a PASS from source code alone.

## Why an interface check is required

The old Stage-D V2 output had one selected exact phase vector for each `stage_d_input_id`. The Stage-E V2 adapter therefore used `stage_d_input_id` as both the daily problem identity and the exact timetable identity.

RT-001 changes the downstream requirement. A single daily timing problem may contain plan contexts with different annual calendars or budget caps. If exact hard-cap feasibility causes those contexts to require different phase vectors, the daily problem must be split into more than one exact timetable without losing plan-context identity.

Silently keeping only one phase vector, duplicating `stage_d_input_id` without a stronger key or collapsing contexts after Stage D would reintroduce a loss of information downstream.

## Accepted exact-timetable identity

Stage E accepts:

1. the historical one-to-one form, where a unique `stage_d_input_id` identifies exactly one summary row and one trip set; or
2. a split form with a dedicated exact identity shared by summary and trips, currently recognised as `exact_timetable_id` or `selected_timetable_id`.

For the split form:

- each dedicated timetable ID must identify exactly one selected phase vector and deterministic trip set;
- all represented plan contexts declared by Stage D must be covered when a context mapping is materialised;
- multiple exact timetables may share one `stage_d_input_id` only when a dedicated exact timetable ID is present;
- every trip must point to a known exact timetable;
- every exact timetable must contain at least one public trip;
- each plan context must map to exactly one exact timetable;
- context-level phase identity, when materialised, must agree with the timetable summary.

Two lossless context-mapping forms are supported by the readiness layer:

- `represented_plan_context_ids_json` embedded in timetable summary rows; or
- a separate context table such as `plan_context_id -> selected_timetable_id`.

The observed Codex Stage-D RT001 V3 implementation uses the second form. Its source currently materialises:

- `selected_timetable_id = stable(stage_d_input_id, phase vector)`;
- `exact_plan_context_results_rt001_v3.csv.gz` with `plan_context_id -> selected_timetable_id`;
- `exact_selected_timetables_rt001_v3.csv` keyed by `selected_timetable_id`;
- `exact_selected_trips_rt001_v3.csv.gz` keyed by the same `selected_timetable_id`.

This is methodologically compatible with Stage E provided the Stage-D V3 CI and the independent interface audit both PASS. Stage E does not require Codex to rename a correct `selected_timetable_id` to another label.

## Non-decisional boundary

The interface validator rejects an exact Stage-D input if it has silently selected any of:

- decision budget;
- calendar;
- recovery;
- PRIMARY;
- RUNNER-UP;
- weighted composite score.

It also fails closed on an explicit ridership forecast, municipal-OD downscaling or technical vehicle closure used as a passenger return.

## Compatibility fixture

CI runs this validator against the already certified Stage-D V2 evidence. That is a **legacy compatibility fixture**, not the repaired final-selection lineage.

Expected compatibility properties are:

- identity remains `stage_d_input_id`;
- 5,345 exact timetable rows are recognised;
- 262,149 exact public trips are recognised;
- all exact timetables have trips;
- the old 16,883 context mapping remains lossless;
- no Stage-E algorithmic scoring or planned-connection logic is changed by this readiness workstream.

These historical cardinalities are fixture assertions in CI only. They are not hard-coded into the interface algorithm and are not expectations for Stage D V3.

Regression tests additionally exercise the observed V3 split schema with `selected_timetable_id` plus a separate plan-context table and deliberately fail on orphan timetables, overlapping context mappings, phase mismatches, ineligible context leakage and non-decisional-boundary violations.

## What this workstream can and cannot PASS

A PASS here means:

> the Stage-E consumer boundary is fail-closed against context collapse, remains backward-compatible with the certified Stage-D V2 fixture and has an explicit tested path for the observed V3 identity schema.

It does **not** mean:

> the repaired Stage-D V3 has passed, Stage E has been rerun on the repaired lineage or a network may be selected.

After Stage-D V3 is certified, Agent A must run the same interface check on the actual persisted V3 outputs. Only then may the Stage-E builder adapter be changed as necessary while preserving the already certified planned-connection-preserving robustness algorithm.

Until the final Decision Contract is executed:

`primary_selection_authorised=false`

`runner_up_selection_authorised=false`
