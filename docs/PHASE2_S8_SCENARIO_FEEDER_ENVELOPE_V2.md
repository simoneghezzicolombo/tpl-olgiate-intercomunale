# Phase 2 S8 Scenario Feeder Envelope V2

## Purpose

This checkpoint lifts the certified route-level S8 transfer-gap envelope into the 100,000 structural scenarios without manufacturing route-level passenger demand.

The empirical S8 work reference remains exactly 1,882 ISTAT 2021 workers across 50 municipal OD relations. It is used only to weight Milano versus Lecco transfer directions inside the route-level transfer-gap metric. It is not an observed S8 modal share and is never assigned to a bus route, stop or scenario.

## What the artifact reports

For each structural scenario and each of the eight certified headway/span timing archetypes, the artifact reports:

- public-route and optional-extension counts;
- the number and share of routes with at least one retained integer clock phase that gives complete matching against all required S8 events;
- separate summaries for routes with full round-trip passenger support and routes that support only `RAIL_TO_BUS` from the Olgiate hub;
- route-unweighted minima and maxima of the route-level best and worst complete-match transfer gaps.

The round-trip and `RAIL_TO_BUS`-only classes are never pooled into one mean because their passenger-service semantics differ.

## What the artifact does not do

It does not:

- allocate any of the 1,882 workers to routes or stops;
- treat S8-addressable work destinations as observed S8 ridership;
- calculate a route-weighted or demand-weighted scenario mean;
- select a bus clock phase;
- assert that individually feasible route phases form a jointly feasible vehicle-block timetable;
- combine fine walking accessibility with municipal OD demand;
- calculate full Passenger GJT;
- rank topologies;
- select a service policy.

Those restrictions are deliberate. The available ISTAT 2021 section evidence supplies `POP21` and `EDI21`, not a section-level worker OD distribution, so a sub-municipal allocation of the 1,882 workers would be an unsupported imputation.

## Decision role

This artifact is one input to the future **S8 feeder-function block** of the tournament. It must remain distinct from:

1. the broader territorial-demand block, which must represent local and non-rail movements relevant to the intermunicipal network;
2. the Access/Equity block, which measures population reached on foot.

No final network recommendation is authorised by this checkpoint alone.
