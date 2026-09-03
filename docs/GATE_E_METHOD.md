# Gate E method: service math

## Scope
Gate E verifies service arithmetic only. It does not select routes, invent timetables or recommend the figure-8. Route geometry/distance/running time must come from Gate D; service dates, bands, trip counts and timetable semantics must come from Gate C or be explicitly labelled `ASSUMPTION` in `SENSITIVITY` mode.

## Core formulas
For each direction and operating band:

`cycle_minutes = pure_running_minutes + dwell_minutes + recovery_minutes`

`minimum_in_service_vehicles = ceil(cycle_minutes / target_headway_minutes)`

This formula is a planning lower bound. It does not silently include deadhead, driver reliefs, spare ratio or maintenance.

`annual_bus_km = route_km × full_directional_cycles_per_day × service_days_year`

Running, dwell and recovery vehicle-hours are calculated separately and summed into scheduled vehicle-hours.

## Directional, rate-equivalent and observed combined headways
`headway_CW` and `headway_CCW` are always separate. A rate-equivalent combined headway can be calculated as:

`1 / (1/headway_CW + 1/headway_CCW)`

Gate E emits this rate-equivalent value only when the CW and CCW rows explicitly state `shared_stop_pattern_status=CONFIRMED`. It is never treated as proof of the actual passenger-facing gap.

For exact phasing, Gate E also provides `scripts/gate_e_headway_audit.py`, fed by `schemas/gate_c_departures_to_e_v1.csv`. It measures interior observed inter-departure gaps at each stop. A perfect 60-minute CW + 60-minute CCW offset may therefore show actual 30-minute combined gaps, while two simultaneous 60-minute directions correctly show a 60-minute maximum gap despite the same 30-minute rate equivalent. Boundary-to-first and last-to-boundary gaps are explicitly excluded unless adjacent bands or a full-day timetable are supplied.

## Scheduled fleet from actual departures
After Gate C provides actual cycle-origin departures and Gate D provides validated cycle durations, `scripts/gate_e_fleet_audit.py` calculates theoretical in-service fleet from interval concurrency. It reports both:

- direction-locked fleet: CW and CCW vehicles cannot switch direction;
- hub-interlined fleet: a vehicle completing a cycle at the common hub may operate either direction next.

Intervals are half-open `[start, end)`, so a bus completing a cycle exactly at a departure time can operate that departure. This remains a **scheduled in-service fleet** measure, not total operator fleet. Depot deadhead, driver reliefs, maintenance and spare ratio remain outside scope and must not be silently added or omitted.

The fleet audit also requires the number of observed hub cycle-origin departures in each band/direction to equal `daily_cycles`; a mismatch is a hard failure rather than a hidden interpretation difference.

## Operating bands
V2 supports multiple bands and service-day groups. Peak and off-peak production are therefore not collapsed into one ambiguous average. Each band requires exactly one CW and one CCW row with matching boundaries, analysis mode and service-day count.

## Epistemic guardrails
Every material numeric input has its own status field. `PLACEHOLDER` and `INVALIDATED` are rejected. `ASSUMPTION` is accepted only in sensitivity analysis. A scenario containing any assumption is `SENSITIVITY_ONLY`, even if C and D are PASS.

A claimed upstream `PASS` is rejected unless the corresponding artifact path and commit SHA are supplied. The same rule applies to observed departure evidence from Gate C. This prevents a stale or untraceable C/D result from being silently promoted.

## PdB benchmark
`data/risorse_tpl_pdb.csv` currently reconstructs D184 = 52,560 and D185 = 58,859 bus-km/year, whose published line totals sum exactly to 111,419. However, D185 peak + off-peak equals 58,858 and the combined peak + off-peak subtotals equal 111,418. Gate E therefore preserves the published line-total benchmark **111,419** and exposes the `-1 km` component discrepancy as `RECONSTRUCTED_COMPONENT_ROUNDING_MISMATCH`; it must not “repair” the source table by hand.

A final Gate E PASS should link this reconstruction to the exact PdB page/table or a machine-readable official source and determine whether the 1 km difference is published rounding or transcription/reconstruction error.

## Final-PASS conditions
Gate E can become eligible for a definitive verdict only when all production rows contain no assumptions, Gate C = PASS with lineage, Gate D = PASS with lineage, shared-stop claims are supported, observed phasing is audited where a passenger-facing combined headway is claimed, and bus-km/vehicle-hour/scheduled-fleet outputs survive the Gate E test suite and substantive inspection.
