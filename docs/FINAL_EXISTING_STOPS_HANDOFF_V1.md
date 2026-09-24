# Final existing-stop inventory handoff V1

Status: **CLOSED FOR DOWNSTREAM NETWORK DESIGN**

## User-facing semantics

For this project, **one row = one existing stop location / stop place**. Directional A/R records, opposite roadside boarding points and operator-side micro-identities are intentionally ignored.

Canonical downstream file:

`outputs/phase2/network_design_method_audit_v3/master_stop_inventory_gpt_v3/existing_stop_places_operational_gpt_v5.csv`

Companion geometry:

`outputs/phase2/network_design_method_audit_v3/master_stop_inventory_gpt_v3/existing_stop_places_operational_gpt_v5.geojson`

## Final operational count

**36 existing stop locations** in the five-core-municipality layer:

- Brivio: 10
- Calco: 9
- La Valletta Brianza: 4
- Olgiate Molgora: 6
- Santa Maria Hoè: 7

The count deliberately collapses opposite directions and operator aliases into one useful stop location.

## Last apparent gaps resolved as aliases, not new stops

Two Arriva timetable names that looked like missing stops are already represented spatially in the operational layer:

1. **CALCO Località Cornello** is treated as the timetable/locality alias of the existing `FROZEN::300634` Calco Via Nazionale location. This is consistent with the D148 sequence and with the Cornello locality corridor. It is **not counted as an additional stop**.
2. **S. MARIA HOE' Tre Strade** is treated as the timetable/locality alias of the existing SP58 / Via Cenisio stop-area location (`ASF::S_MARIA_HOE_S_P_58_ANG_VIA_CENISIO`). Municipal evidence places the Tre Strade locality on Via Papa Giovanni XXIII in the same stop area. It is **not counted as an additional stop**.

Other current timetable labels such as `S. MARIA HOE centro` and `HOE'` are already represented by the retained D184 reference locations.

## Scope and evidence

The operational layer unions:

- current ASF/C146 stop locations;
- Arriva/LineeLecco stop locations from the certified frozen reference universe, with current timetable cross-checks where available;
- the manually confirmed Scagnello stop;
- the Casa di Comunità special-service stop, explicitly marked as a separate service class.

Known obsolete/misleading frozen locations already excluded from the operational layer remain preserved only in the detailed audit lineage.

## Downstream contract for Alpha

Alpha may now use the 36-row operational file as the **existing-stop location layer** for coverage diagnostics, stop materialization and network-design evaluation.

This file is **not** a routing-terminal list. Stop existence does not imply terminal status.

No downstream stage should reopen A/R directionality or roadside-side identity unless a specific routing geometry problem requires it.

Any future newly discovered stop should be added incrementally and must not invalidate or block the current network-design pipeline.

## Closure decision

The existing-stop discovery/conflation workstream is therefore **closed for the purposes of Phase 2 network design**. Further stop micro-audit is non-blocking.