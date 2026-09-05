# Phase 2 final 36-stop materialization bridge V3

## Status and purpose

RT-018 is a non-decisional integration layer between the closed existing-stop inventory and the topology-neutral V3 network search.

The canonical passenger-stop infrastructure input is the 36-row operational stop-place layer frozen by `FINAL_EXISTING_STOPS_HANDOFF_V1.md` at source commit `ea30fbd18421164abaf2125033292cbe827e024d`.

The bridge does not discover stops, conflate identities, choose a route, choose terminals, impose topology, choose timetable policy or select a winner.

## Frozen user semantics

For this project one stop means one stop place. Directional A/R records, opposite roadside boarding points and operator-side micro-identities remain intentionally collapsed.

The final count is:

| Municipality | Stop places |
| --- | ---: |
| Brivio | 10 |
| Calco | 9 |
| La Valletta Brianza | 4 |
| Olgiate Molgora | 6 |
| Santa Maria Hoè | 7 |
| **Total** | **36** |

The old Alpha evidence bridge that exposed 43 eligible records is historical only and is not an active downstream input after RT-018.

## Canonical files

- `outputs/phase2/network_design_method_audit_v3/master_stop_inventory_gpt_v3/existing_stop_places_operational_gpt_v5.csv`
- `outputs/phase2/network_design_method_audit_v3/master_stop_inventory_gpt_v3/existing_stop_places_operational_gpt_v5.geojson`
- `outputs/phase2/network_design_method_audit_v3/master_stop_inventory_gpt_v3/existing_stop_places_operational_validation_gpt_v5.json`

RT-018 copies these source objects byte-for-byte into the Alpha lineage before downstream work.

## Graph attachment contract

Stop-place identity and graph attachment are separate.

`attach_stop_places_to_graph()` receives the frozen 36 stop places and an explicit supplied road-graph node table. Every stop place is retained exactly once and is bound deterministically to its nearest graph node in EPSG:32632.

Technical attachment tiers inherit the current frozen-graph snap contract:

- `ROUTE_READY_LE_75M`: nearest graph node at most 75 m;
- `REVIEW_75_250M`: greater than 75 m and at most 250 m;
- `OUTSIDE_250M`: greater than 250 m.

These are graph-binding diagnostics, not passenger walking thresholds and not network-design policy weights.

No unresolved stop is silently removed. Review and unresolved rows remain in the 36-row attachment table with explicit status.

### RT-017 dependency

The current Gate-D graph attachment is only a compatibility smoke. Agent A owns RT-017, which may expand or replace the frozen road-routing envelope. Before any final territorial candidate search, the exact same attachment stage must be rerun against the RT-017 frozen graph and its graph epoch must be recorded.

Thus a road-graph refresh never changes stop-place identity implicitly.

## Conventional versus special service

The Casa di Comunità stop remains part of the final 36-stop infrastructure layer with `service_class=SPECIAL_SERVICE`.

RT-018 does not automatically promote special-service infrastructure into a conventional TPL candidate pattern. The default materialization class is `CONVENTIONAL_TPL`. A caller may include another service class only through an explicit upstream service-design decision.

## Corridor materialization contract

`materialize_stop_occurrences()` receives:

1. a stable corridor ID;
2. the exact ordered directed graph-node path;
3. the frozen graph attachment table.

It emits stop occurrences only when the corridor actually encounters the bound graph node.

Ordering is determined exclusively by path occurrence. Names, municipality, current route, service area labels and structural anchors do not decide stop order.

Repeated traversal is preserved. If a loop encounters the same stop place twice, the output contains two stop occurrences with the same `stop_place_id` and different occurrence indices. This is not duplicate infrastructure; it is repeated service occurrence on the directed path.

Multiple distinct stop places bound to the same graph node are emitted in deterministic stable-ID order.

Structural routing anchors are never interpreted as passenger stops.

## Downstream relationship to RT-014

RT-014 remains unchanged. It accepts only explicit stable stop IDs, coordinates and ordered stop calls.

The intended chain after RT-017 PASS is:

`RT-017 frozen road graph -> RT-006 corridor -> RT-018 exact existing-stop occurrences -> explicit service policy -> RT-014 candidate GTFS -> internal + R5 routing -> RT-013 discrepancy audit -> RT-011 / RT-016 territorial evaluation`.

RT-014 must never infer a stop from corridor geometry, a name, a structural anchor or proximity.

## Fail-closed rules

RT-018 rejects or explicitly flags at least:

- final input cardinality other than 36;
- duplicate `stop_place_id`;
- changed municipality counts;
- invalid coordinates;
- duplicate graph node IDs;
- multiple graph epochs in one attachment run;
- missing required fields;
- conventional stop places not route-ready in the compatibility graph when running the production validation.

## Non-claims

RT-018 does not prove that any network topology is good. It does not produce a territorial candidate before RT-017 PASS. It does not introduce Cassina, Circolare Meratese or external interchange logic. It does not select headways, calendars, fleet, PRIMARY or RUNNER-UP.
