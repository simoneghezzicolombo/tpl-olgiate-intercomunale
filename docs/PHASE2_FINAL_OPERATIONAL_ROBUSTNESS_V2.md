# Phase 2 — Stage E Final Operational Robustness V2

## Scope

Stage E is a **non-decisional operational robustness evidence engine**. It consumes a certified exact Stage-D timetable and reports how the same nominal timetable behaves under declared transfer-friction, runtime and recovery sensitivities.

It does not rank networks and it does not select a budget, calendar, recovery value, PRIMARY or RUNNER-UP. It creates evidence that can later support the reliability-first tie-break in the Phase 2 Decision Contract.

## Current development lineage

The current development/regression fixture is the technically certified Stage D exact evidence:

- evidence commit: `96e033e77f2b9b7b82ff4555b682816bf8c71111`
- workflow run: `33866312583`
- artifact: `9934216350`
- status: `PASS_PHASE2_STAGE_D_EXACT_TIMETABLE_V2`

This fixture is **not the final-selection lineage** because the independent red-team RT-001 demonstrated an upstream hard-budget losslessness defect. All current Stage-E outputs therefore declare:

`CURRENT_STAGE_D_USED_AS_ENGINE_VALIDATION_FIXTURE_NOT_FINAL_SELECTION_LINEAGE`

When a new lossless Stage D is independently certified, this same builder can consume it without changing the algorithm. Only then may the lineage role be changed to `LOSSLESS_STAGE_D_FINAL_SELECTION_LINEAGE`.

## Planned-connection-preserving robustness

The historical Stage-D runtime diagnostic searched for the next train after delaying the bus. That is useful as a next-available-service diagnostic but it cannot define planned-connection retention because a later train can make the apparent miss share improve.

Stage E instead freezes the nominal target identity first.

For **BUS_TO_RAIL**:

1. take the exact public passenger return to the hub;
2. add the certified transfer walk for the selected sensitivity profile;
3. select the nominal reachable S8 departure and persist its `trip_id` as the planned target;
4. under bus runtime stress, test whether that same train remains reachable;
5. if it is lost, record `planned_connection_retained=false`;
6. only then search the next available rail departure and report its wait as a separate alternative metric.

A later train can therefore never turn a missed planned connection into a success.

For **RAIL_TO_BUS** the symmetric rule applies: the frozen S8 arrival identifies the nominal exact bus departure, and a rail-arrival perturbation tests retention of that same bus. A later bus is reported only as an alternative.

## Directionality

Evidence is kept separate for:

- `BUS_TO_RAIL × MILANO`
- `BUS_TO_RAIL × LECCO`
- `RAIL_TO_BUS × MILANO`
- `RAIL_TO_BUS × LECCO`

A later summary may expose minima/worst cases across directions, but the underlying directional rows remain available and no weighted bidirectional score is created.

## Frozen S8 evidence

The engine uses only `outputs/phase2/s8_events.csv` from the certified Stage-D lineage. The fixture contains 74 S8 events, 37 `MILANO` and 37 `LECCO`. There is no live GTFS refresh or timetable scraping in Stage E.

## Transfer-friction sensitivity

Transfer profiles are read from the certified contract `config/phase2_s8_phasing_sensitivity_v2.json`, not copied from prose. The current contract contains three assumption profiles:

- `LOW_TRANSFER_FRICTION`: transfer walk 1.5 min, preferred wait 3 min;
- `MID_TRANSFER_FRICTION`: transfer walk 2.0 min, preferred wait 4 min;
- `HIGH_TRANSFER_FRICTION`: transfer walk 3.0 min, preferred wait 5 min.

The miss-transition and wait-decay parameters remain part of the upstream profile contract but Stage E planned-retention itself is an explicit reachability test against the frozen planned target, not a probabilistic logistic score.

No profile is selected as the true one.

## Runtime and rail-delay sensitivities

The bus runtime sensitivity set is read dynamically from the exact Stage-D validation. In the current fixture it is:

`0, +5, +10, +15 minutes`

These are deterministic engineering stress cases. They are not observations of a delay distribution and are never described as failure probabilities.

No certified non-zero rail-delay sensitivity contract was found in the current lineage. The Stage-E source-closed sensitivity config therefore authorises only rail-arrival delay `0` for the current fixture run. The kernel supports explicit rail-delay cases, but a non-zero set may be used only after an independently authorised source-backed contract is supplied.

## Recovery and vehicle blocks

Recovery values are read from the exact Stage-D validation. The current fixture contains `5, 10, 15` minutes and none is selected.

For every timetable, recovery and bus-runtime stress case, Stage E reports:

- Stage-D nominal fleet for that recovery;
- minimum vehicle requirement after adding runtime stress to the exact vehicle return;
- maximum simultaneous vehicle requirement;
- additional vehicles required relative to the nominal Stage-D blocking;
- conflicts on the nominal block assignment;
- turnaround violations;
- minimum, median and maximum block slack;
- minimum hub turnaround where an inter-trip turnaround exists.

At zero runtime stress the builder must exactly reproduce the Stage-D fleet requirement for every recovery case. Under positive stress the nominal block assignment may become infeasible and the engine recomputes the minimum fleet independently.

## Technical-return semantics

A technical vehicle return is never passenger service. BUS_TO_RAIL candidates are generated only from `public_hub_return_min`. Open public routes whose vehicle returns technically have no `public_hub_return_min`, so they cannot create passenger BUS_TO_RAIL connections or improve passenger robustness.

This boundary is both validated against the route input semantics and covered by a dedicated regression test.

## Outputs

`outputs/phase2/final_operational_robustness_v2/` contains:

- `final_operational_connection_audit_v2.csv.gz`: nominal connection identities and per-case perturbation outcomes;
- `final_operational_robustness_surface_v2.csv.gz`: directional/profile/sensitivity summaries including retained/missed planned connections, nominal slack, alternatives and service-gap effects;
- `final_operational_block_sensitivity_v2.csv.gz`: recovery × runtime vehicle-block evidence;
- `final_operational_robustness_summary_v2.csv.gz`: compact timetable/profile worst-case descriptors without a composite score;
- `final_operational_robustness_v2_validation.json`: machine-readable contract, lineage and epistemic flags.

## RT-003 current-service limitation

The current-service territorial baseline remains a **certified localisable lower bound only**. Passing a non-regression comparison against that lower bound does not prove that a municipality is no worse than the complete real current D184/D185 service. Stage E does not infer unresolved current stops. See `docs/PHASE2_RT003_CURRENT_SERVICE_BASELINE_LIMITATION.md`.

## RT-004 governance

`AGENT_PROTOCOL.md` has not historically existed in this lineage. Stage E does not invent it retroactively. `AGENT_STATUS.md` is refreshed on the Stage-E branch to point to the current critical path and to distinguish the technically PASS Stage-D fixture from the blocked final-selection lineage.

## Selection boundary

Even if this engine passes its own validation:

- `budget_selected=false`
- `calendar_selected=false`
- `recovery_values_selected=false`
- `primary_selected=false`
- `runner_up_selected=false`
- `weighted_composite_score=false`
- `primary_selection_authorised=false`
- `runner_up_selection_authorised=false`

The final recommendation remains downstream of RT-001 repair, a new lossless exact Stage D, rerun of this Stage E engine, the final robustness tournament and the explicit Decision Contract inputs.
