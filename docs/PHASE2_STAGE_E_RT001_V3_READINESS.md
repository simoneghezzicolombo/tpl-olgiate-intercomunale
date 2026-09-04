# Phase 2 — Stage E RT-001 V3 interface readiness

## Status

**Readiness workstream only.** This document does not certify a new final Stage-E run and does not authorise PRIMARY / RUNNER-UP selection.

Branch: `phase2-stage-e-rt001-v3-readiness`

Upstream state at creation:

- Stage E Final Operational Robustness V2 is already technically PASS on the old certified Stage-D fixture.
- RT-001 has been repaired upstream through a lossless Stage-D input manifest V3.
- The repaired manifest contains plan contexts that share one daily `(scenario_id, headway, span)` problem while retaining distinct budget and calendar memberships.
- The exact Stage-D V3 output is not assumed by this readiness workstream until it is independently certified.

## Why an interface check is required

The old Stage-D V2 output had one selected exact phase vector for each `stage_d_input_id`. The Stage-E V2 adapter therefore used `stage_d_input_id` as both the daily problem identity and the exact timetable identity.

RT-001 changes the downstream requirement. A single daily timing problem may contain plan contexts with different annual calendars or budget caps. If exact hard-cap feasibility causes those contexts to require different phase vectors, the daily problem must be split into more than one exact timetable without losing plan-context identity.

Silently keeping only one phase vector, duplicating `stage_d_input_id` without a stronger key or collapsing contexts after Stage D would reintroduce a loss of information downstream.

## Accepted exact-timetable identity

Stage E accepts either:

1. the historical one-to-one form, where a unique `stage_d_input_id` identifies exactly one summary row and one trip set; or
2. a V3 split form with an explicit `exact_timetable_id` shared by the exact summary and trip outputs.

For the V3 split form:

- each `exact_timetable_id` must identify exactly one selected phase vector and deterministic trip set;
- `represented_plan_context_ids_json` must not overlap across exact timetables;
- all represented plan contexts declared by Stage D must be covered when the mapping is materialised;
- multiple exact timetables may share one `stage_d_input_id` only when `exact_timetable_id` is present;
- every trip must point to a known exact timetable;
- every exact timetable must contain at least one public trip.

A separate lossless `plan_context_id -> exact_timetable_id` mapping would also be methodologically acceptable, but the current readiness validator expects the mapping to be materialised in exact-summary rows. If Stage D V3 chooses a separate mapping file instead, the adapter must be extended explicitly rather than inferring the relation.

## Non-decisional boundary

The interface validator also rejects an exact Stage-D input if it has silently selected any of:

- decision budget;
- calendar;
- recovery;
- PRIMARY;
- RUNNER-UP;
- weighted composite score.

It also rejects ridership forecasts or municipal-OD downscaling at this boundary.

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

## What this workstream can and cannot PASS

A PASS here means:

> the Stage-E consumer boundary is fail-closed against context collapse and remains compatible with the certified Stage-D V2 fixture.

It does **not** mean:

> the repaired Stage-D V3 has passed, Stage E has been rerun on the repaired lineage or a network may be selected.

After Stage-D V3 is certified, Agent A must run the same interface check on the new exact outputs. Only then may the Stage-E builder adapter be changed, if necessary, to consume `exact_timetable_id` while preserving the already certified planned-connection-preserving robustness algorithm.

Until the final Decision Contract is executed:

`primary_selection_authorised=false`

`runner_up_selection_authorised=false`
