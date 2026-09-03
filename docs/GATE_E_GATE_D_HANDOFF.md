# Gate D to Gate E handoff

## Purpose

Gate E must receive route metrics without losing the epistemic status of the route definition that generated them. A precise distance computed over an assumed candidate geometry is still assumption-dependent for downstream service claims.

The preferred handoff is `schemas/gate_d_to_e_v2.csv`, normalized by `scripts/gate_e_normalize_gate_d.py` before the existing C+D builder is run.

## Epistemic taxonomy

Use the project-wide epistemic statuses exactly: `FACT`, `DERIVED`, `ESTIMATE`, `ASSUMPTION`, `RECONSTRUCTED`, `MODEL OUTPUT`. Do not create statuses such as `DERIVED_OSM`; encode the epistemic class as `DERIVED` and put the method in `route_km_method`, for example `OSM_ROUTED_GEOMETRY_EPSG32632`.

`PLACEHOLDER` and `INVALIDATED` are forbidden.

## Route definition and distance are separate claims

Gate D v2 separates:

- `candidate_geometry_id`: stable identifier for the candidate/geometry;
- `route_definition_status`: epistemic status of why that candidate exists;
- `route_definition_basis`: traceable description/artifact basis for the route definition;
- `route_km`: measured routed distance;
- `route_km_status`: epistemic status of the distance measurement;
- `route_km_method`: measurement/routing method.

If `route_definition_status=ASSUMPTION`, the Gate E normalizer propagates `route_km_status=ASSUMPTION` even if the distance itself was deterministically derived from OSM. Such rows may be used only in `SENSITIVITY`, never production.

## Running-time evidence

`pure_running_min` must remain separate from dwell and recovery. A speed-model result is `MODEL OUTPUT`, not FACT.

Gate D must additionally provide `running_time_calibration_status`, using one of:

- `CALIBRATED`
- `VALIDATED_AGAINST_SCHEDULE`
- `UNCALIBRATED`
- `NOT_APPLICABLE`

A `MODEL OUTPUT` running time from a formally passed Gate D cannot feed Gate E production while marked `UNCALIBRATED`.

Gate E now provides `scripts/gate_e_gtfs_runtime_benchmark.py`, which derives endpoint-to-endpoint scheduled runtime distributions for D184/D185 directly from the official historical GTFS validated in Gate C. These are `DERIVED` scheduled-time calibration references, explicitly **not observed traffic running times**. Gate D can use them as one calibration check without reverting to legacy hardcoded runtime constants.

## Physical road uncertainty

Gate D v2 carries `uncertain_road_km` plus `road_uncertainty_status` (`RESOLVED`, `QUANTIFIED`, `UNKNOWN`). Gate E validates that uncertainty cannot exceed route length. These fields do not alter service arithmetic by themselves, but unresolved physical uncertainty must not be converted into a definitive feasibility claim.

## Pre-verdict screening

Once Gate D has provisional or passed route metrics, `scripts/gate_e_screen_gate_d.py` can cross them against explicit Gate E operating envelopes. It reports runtime and route-km margins against assumed frequency/fleet/budget thresholds.

Every such screen remains `SENSITIVITY_ONLY_NOT_GATE_E_VERDICT` because the operating policy inputs are assumptions. “Within envelope” means only that the mathematical thresholds are not exceeded under that explicit assumption set. It is not a route recommendation, physical-feasibility verdict or Gate F conclusion.

## Exact minimum delivery from Gate D

For each serious candidate and direction Gate E needs:

1. stable geometry/candidate ID;
2. standard epistemic status of the route definition and its basis;
3. route km, standard status and measurement method;
4. pure running minutes, standard status and calibration status;
5. quantified unresolved road kilometres/status;
6. Gate D formal status;
7. artifact path and exact commit SHA;
8. unique `scenario_id + service_day_group + band_id + direction` mapping, or a deterministic adapter that produces it.

No Gate E production result will fall back to `outputs/route_variants.csv`, `outputs/service_simulation_scenarios.csv`, `data/scenario0_tempi_percorsi.csv` or other invalidated legacy outputs.
