# Phase 2 functional catchment scope V1

**Date:** 2026-09-05

## Decision

Keep the five municipalities as the **core project territory**:

- Olgiate Molgora
- Calco
- Brivio
- La Valletta Brianza
- Santa Maria Hoè

Do not treat every surrounding municipality as an equal core-design unit.

Add a separate **extended functional catchment** for external interchange nodes and demand that materially affect the usefulness of the proposed intermunicipal line.

## Why

A hard five-municipality cut can wrongly exclude useful interchange opportunities immediately outside the administrative boundary. The C146 Scagnello case already demonstrates this: an operationally relevant stop can lie only a few metres outside the exact core polygon.

The same logic applies to possible interchange with the Merate local circular service around Sartirana / Cassina, as well as rail or bus interchange opportunities in nearby municipalities.

## Three spatial roles

Every stop, grid cell, population record and demand point should carry a role independent of municipality name:

1. `CORE`
   - inside one of the five project municipalities;
   - used for primary coverage, equity and service-gap objectives.

2. `FUNCTIONAL_INTERCHANGE_CONTEXT`
   - outside the five core municipalities;
   - included because it provides a realistic interchange, terminal, major attractor or network connection for the core population.

3. `ROUTING_BUFFER`
   - external geography needed only so routing/corridor generation is not artificially clipped;
   - not automatically counted in demand or project-benefit totals.

## Candidate functional-context nodes to test

Initial candidates should be evidence-driven rather than municipality-wide by default. High-value examples include:

- Merate-side interchange with the Circolare Meratese, including Sartirana / Cassina-area opportunities if stop geometry and schedules support useful transfers;
- Merate as a wider TPL interchange context where relevant to candidate routing;
- Airuno rail/bus interchange where it improves access from the Brivio side;
- Imbersago / Arlate boundary stops used by current services and possible transfer paths;
- other immediately adjacent nodes only when they improve a candidate route or transfer chain.

This list is a test queue, not a commitment to serve every named locality.

## Population and demand data contract

Do **not** rebuild the whole demand model around all surrounding municipalities immediately.

Instead maintain two analytical layers:

### Core demand layer

Full population, demographics, origins/destinations, service-gap metrics and coverage KPIs for the five core municipalities.

### Extended context demand layer

Population and attractor data only for the defined functional catchment / routing envelope, used for:

- interchange demand;
- through-demand;
- terminal selection;
- avoiding artificial edge effects;
- comparing external connection options.

Core policy KPIs must remain separately reportable so external population does not dilute or inflate the benefit measured for the five municipalities.

## Recommended implementation

1. Expand the spatial extraction envelope beyond the five municipalities before clipping population and network layers.
2. Keep exact ISTAT municipality fields for every point/cell.
3. Add `analysis_context_role` with values `CORE`, `FUNCTIONAL_INTERCHANGE_CONTEXT`, `ROUTING_BUFFER`.
4. Build candidate interchange nodes first.
5. Only expand detailed population/demand processing to the external areas that survive the interchange screening.
6. Re-run candidate routing with and without external interchange nodes to quantify whether they materially improve travel time, coverage or connectivity.

## Practical implication

The project remains an Olgiate-Calco-Brivio / Valletta / Santa Maria Hoè intermunicipal service design, but it is no longer artificially constrained to terminate or interchange exactly at the administrative boundary.
