# Phase 2 special-service stop evidence V3

**Author:** GPT reviewer/co-developer  
**Date:** 2026-09-05  
**Branch:** `gpt-stop-source-completeness-v3`

## Scope

The five-municipality physical-stop inventory must not be restricted to conventional scheduled bus stops discoverable through the frozen Arriva/LineeLecco GTFS and OSM layers. Service-specific boarding points can be operationally real even when they are absent from both datasets.

These points must be retained in a separate class so that they are visible for accessibility and service-context analysis without being misrepresented as ordinary signed TPL infrastructure.

## Confirmed case: Casa di Comunità Olgiate Molgora

A local coordinate observation identifies the shuttle boarding point at:

- latitude: `45.72213132103248`
- longitude: `9.397973585897839`
- municipality: Olgiate Molgora
- place: Casa di Comunità Olgiate Molgora

The service existence and stop name are independently confirmed by official public information.

### Official service evidence

The Comune di Olginate notice dated 2026-03-13 states that the Mandic Merate - Manzoni Lecco hospital shuttle was reactivated from 2026-03-16 and explicitly lists the following stops:

- Rotonda Via Piave Robbiate
- Ospedale Mandic Merate
- **Casa di Comunità Olgiate Molgora**
- Rotonda incrocio Statale/Via Kennedy Airuno
- Presidio ASST Olginate
- Ospedale Manzoni Lecco

Source:

https://www.comune.olginate.lc.it/novita/avvisi/novita_187.html

ASST Lecco subsequently confirmed on 2026-07-10 that the Mandic-Manzoni shuttle remained active and that users could access it without prior booking, with onboard POS payment available.

Source:

https://www.asst-lecco.it/novita-pagamenti-servizio-navetta-ospedale-mandic-di-merate-e-ospedale-manzoni-di-lecco/

## Classification contract

This point is classified as:

- `stop_class = SPECIAL_SERVICE_BOARDING_POINT`
- `inventory_status = INCLUDE_SEPARATE_FROM_CONVENTIONAL_GTFS_OSM`
- service existence/name: `FACT_PRIMARY_PUBLIC_SERVICE_EVIDENCE`
- coordinate: `LOCAL_COORDINATE_USER_SUPPLIED`

The coordinate is retained because it is a precise local observation supplied for the project. It is not silently promoted to an official surveyed coordinate.

The point must **not** automatically inherit conventional-stop attributes such as shelter, pole, timetable board, kerb design or standard route-stop status. Those require separate physical/map evidence.

## Downstream use

This boarding point may be included when asking questions such as:

- whether a public or public-accessible mobility service reaches a health facility;
- whether candidate local service designs duplicate or complement an existing health-transport connection;
- walking access to mobility services in the wider sense.

It must be excluded or separately reported when a metric is specifically defined as:

- conventional scheduled TPL stop count;
- GTFS stop coverage;
- signed/sheltered bus-stop infrastructure count.

## Machine-readable evidence

See:

`outputs/phase2/network_design_method_audit_v3/special_service_stop_evidence_gpt_v3.csv`
