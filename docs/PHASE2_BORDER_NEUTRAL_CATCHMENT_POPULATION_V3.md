# Phase 2 V3 — Border-neutral catchment population (RT-016)

## Purpose

RT-016 removes an administrative-border artefact from passenger access evaluation.
The five study municipalities remain the **core policy universe**, but residents just
outside those borders must not disappear when they are genuinely within walking
reach of a passenger stop.

This workstream does **not** add interchange logic, does not create or move stops and
does not alter the stop-source completeness work running in parallel.

## Frozen policy distinction

Two population concepts are intentionally separate:

1. **Core population** — residents of the five study municipalities. This remains the
   denominator for municipal equity, minimum service obligations and core coverage.
2. **External spillover population** — residents outside the five municipalities who
   fall inside the physically relevant passenger walk catchment. This is an additional
   benefit only. It cannot satisfy a missing core municipality obligation.

The five core ISTAT codes remain:

- `097010`
- `097012`
- `097058`
- `097074`
- `097092`

## No hand-picked neighbouring municipalities

The external universe is not defined by a list such as “Merate, Airuno, ...”.
RT-016 derives a metric envelope around the service area and intersects it with the
full official ISTAT municipal geometry layer.

With the current Phase 2 walking contract:

- maximum walk threshold: **12 minutes**;
- walking speed: **4.8 km/h**;
- maximum compatible path length: **960 m**.

Therefore a 960 m geometric buffer is sufficient to avoid municipal-border truncation
for stops located inside the five-municipality core. A network walking path of at
most 960 m cannot originate farther than 960 m in straight-line distance.

If a future candidate introduces a passenger stop outside the five-municipality core,
the same method must be rematerialized from the explicit stop/service geometry. RT-016
does not silently claim that the core buffer covers arbitrarily distant external stops.

## Population source and calibration

RT-016 reuses the validated Gate B population method:

- WorldPop 2020 100 m national raster;
- official ISTAT POSAS 2025 municipality totals;
- official ISTAT 2026 municipality geometries.

The already validated Gate B core cells are preserved rather than recomputed.

For each newly discovered external municipality, calibration is deliberately based on
its **full municipal WorldPop raw sum**:

`calibration_factor = POSAS_2025_total / full_municipality_WorldPop_raw_sum`

Only after deriving that factor is it applied to the WorldPop cells inside the 960 m
analysis envelope.

This order matters. Calibrating the small envelope fragment directly to the full
municipal POSAS total would incorrectly concentrate the whole municipality's
population at the study-area edge.

## Outputs

The real-data materializer is:

`scripts/phase2_build_border_neutral_catchment_population_v3.py`

It produces a combined population universe with explicit `population_scope`:

- `core`
- `external`

and keeps the population metrics separable as:

- `core_covered_population`
- `external_spillover_population`
- `total_catchment_population`

Repeated coverage of the same population unit by several stops is counted only once.

## Decision semantics

External spillover is not currently promoted to a mandatory Pareto dimension. RT-016
first makes the quantity correct and auditable. A later territorial evaluation may use
it as a secondary benefit, provided that core policy constraints and core equity remain
separate and dominant safeguards.

## Fail-closed rules

The contract rejects:

- empty or invalid walk-envelope parameters;
- missing core municipalities from the discovered envelope;
- invalid official population totals or WorldPop sums;
- duplicate population-unit IDs;
- non-finite or negative population weights;
- unknown covered population units.

No synthetic population, manual settlement nuclei or random generation are permitted.
