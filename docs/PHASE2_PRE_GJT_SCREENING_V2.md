# Phase 2 Pre-GJT Screening V2

## Purpose

This workstream creates a topology-neutral, non-decisional decision surface after Access/Equity V2, Service Policy Search V2 and Passenger GJT's audited S8 support/timing layers.

It exists because full Passenger GJT is not yet empirically identifiable at route level from the available 2021 work OD matrix. The municipal OD data identify municipality-to-municipality worker flows, but do not identify which building, stop or candidate bus route each worker would use.

The screening therefore does **not** fabricate that missing allocation.

## Unit of analysis

The output `pre_gjt_scenario_timing_screening_v2.csv.gz` has one row for every structural scenario and every retained headway/span timing archetype:

- 100,000 structural scenarios;
- 8 timing archetypes;
- 800,000 scenario × timing rows.

No clock phase is selected. Calendar, recovery and extension-share policy variants remain represented through the lossless Service Policy Search V2 feasibility mask.

## Layers kept separate

### Territorial access and equity

The surface carries exact 5, 8 and 10 minute building-population walking coverage for the public route stop set, plus worst-municipality coverage. These are dasymetric resident-population accessibility metrics, not passenger demand.

For scenarios with optional extensions, the full `public_plus_extensions` 10-minute coverage is also retained. It is explicitly a **service-presence** measure and is not adjusted for the share of departures operating the extension.

### Operational evidence

The surface carries public route distance/runtime, field-check-pending stop count and the operationally unresolved distance share. These remain lower-bound/uncertainty evidence from Operational Screening V2.

### Reference-budget service-policy feasibility

The certified reference budget remains 111,419 annual bus-km. For each scenario × timing row, the Service Policy Search V2 bitmask is decoded to count:

- all feasible policies at that headway/span;
- feasible policies with `extension_share=0`;
- feasible policies with a positive extension share.

This is feasibility, not policy selection.

### S8 passenger support and transfer opportunity

Public routes and optional extension routes are kept separate. The surface records round-trip-supported versus RAIL_TO_BUS-only route counts and, for each headway/span, how many routes have at least one complete integer-minute phase match.

Gap ranges remain route-level opportunity envelopes. They do not construct an interlined vehicle timetable and do not choose a phase.

The 1,882-worker ISTAT subset is used only in the upstream transfer-gap envelope as a Milano-versus-Lecco directional weight. It is not assigned to routes and is not interpreted as observed S8 ridership or modal share.

## Explicit non-claims

This workstream does not:

- allocate municipal OD to buildings, stops or routes;
- calculate full passenger GJT;
- combine the layers into a weighted score;
- calculate a final Pareto frontier;
- rank topology families;
- select a clock phase, service policy, extension share or stop set;
- select a primary or runner-up design.

Its purpose is to make the next screening stage possible without silently converting incomplete passenger evidence into a recommendation.
