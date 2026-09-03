# Gate E method: service math

## Scope
Gate E verifies service arithmetic only. It does not select routes, invent timetables or recommend the figure-8. Route geometry/distance/running time must come from Gate D; service dates, bands, trip counts and timetable semantics must come from Gate C or be explicitly labelled `ASSUMPTION` in `SENSITIVITY` mode.

## Core formulas
For each direction and operating band:

`cycle_minutes = pure_running_minutes + dwell_minutes + recovery_minutes`

`minimum_in_service_vehicles = ceil(cycle_minutes / target_headway_minutes)`

The vehicle result is a **lower bound**, not an exact fleet requirement. It excludes deadhead, interlining, driver reliefs, spare ratio and maintenance. Exact fleet belongs to block scheduling after C/D.

`annual_bus_km = route_km × full_directional_cycles_per_day × service_days_year`

Running, dwell and recovery vehicle-hours are calculated separately and summed into scheduled vehicle-hours.

## Directional and combined headways
`headway_CW` and `headway_CCW` are always separate. A rate-equivalent combined headway is calculated as:

`1 / (1/headway_CW + 1/headway_CCW)`

Gate E emits this combined value only when the CW and CCW rows explicitly state `shared_stop_pattern_status=CONFIRMED`. Even then it is a service-rate equivalent, not proof of the maximum passenger-facing gap. Exact stop-level gaps require phased Gate C timetables.

## Operating bands
V2 supports multiple bands and service-day groups. Peak and off-peak production are therefore not collapsed into one ambiguous average. Each band requires exactly one CW and one CCW row with matching boundaries, analysis mode and service-day count.

## Epistemic guardrails
Every material numeric input has its own status field. `PLACEHOLDER` and `INVALIDATED` are rejected. `ASSUMPTION` is accepted only in sensitivity analysis. A scenario containing any assumption is `SENSITIVITY_ONLY`, even if C and D are PASS.

A claimed upstream `PASS` is rejected unless the corresponding artifact path and commit SHA are supplied. This prevents a stale or untraceable C/D result from being silently promoted.

## PdB benchmark
`data/risorse_tpl_pdb.csv` currently reconstructs D184 = 52,560 and D185 = 58,859 bus-km/year, whose published line totals sum exactly to 111,419. However, D185 peak + off-peak equals 58,858 and the combined peak + off-peak subtotals equal 111,418. Gate E therefore preserves the published line-total benchmark **111,419** and exposes the `-1 km` component discrepancy as `RECONSTRUCTED_COMPONENT_ROUNDING_MISMATCH`; it must not “repair” the source table by hand.

A final Gate E PASS should link this reconstruction to the exact PdB page/table or a machine-readable official source and determine whether the 1 km difference is published rounding or transcription/reconstruction error.

## Final-PASS conditions
Gate E can become eligible for a definitive verdict only when all production rows contain no assumptions, Gate C = PASS with lineage, Gate D = PASS with lineage, shared-stop claims are supported, and the resulting bus-km/vehicle-hour/fleet lower-bound outputs survive the Gate E test suite and substantive inspection.
