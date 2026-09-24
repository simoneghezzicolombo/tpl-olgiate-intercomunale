# Phase 2 stop-source completeness audit V3

**Author:** GPT reviewer/co-developer  
**Date:** 2026-09-05  
**Branch:** `gpt-stop-source-completeness-v3`  
**Baseline branch:** `phase2-network-design-method-audit-v3` @ `afcc4813217339cba10f621e9ad2a5a3730faafe`

## Verdict

`BLOCKED_COMPLETE_STOP_INVENTORY_PENDING_MULTI_OPERATOR_AND_CURRENT_SOURCE_INTEGRATION`

This verdict **does not invalidate** the deterministic GTFS↔OSM conflation implemented on `phase2-network-design-method-audit-v3`. The conflation correctly treats OSM as corroborating evidence and refuses geographically implausible identifier/name matches.

The blocker is upstream: the official-stop universe currently used by the V3 conflation is not yet source-complete enough to be called a master inventory of existing physical stops in the five core municipalities.

## Why the V3 conflation remains useful

`phase2_build_stop_universe_v2.py` loads the reference-period stop universe from exactly two frozen GTFS feeds:

- `arriva_addabus_2025_2026.zip` (`ARRIVA_ADDABUS`)
- `lineelecco_2025_2026.zip` (`LINEELECCO`)

and explicitly labels those records `FACT_OFFICIAL_GTFS_REFERENCE_PERIOD_NOT_CURRENT_SERVICE`.

`phase2_audit_existing_stop_conflation_v3.py` then compares that universe against the frozen OSM stop extract. Its identity rules are methodologically appropriate: geography can veto an identifier/name match and distance-only evidence cannot confirm identity.

Therefore the correct fix is **not** to weaken or replace the matcher. The fix is to broaden the source universe feeding it.

## Blocking finding 1: ASF C146 is an official core-area service missing from the frozen source set

The 2026 Lecco Mobility Charter lists line D146/C146 as an official service operated by **ASF Autolinee**. The current ASF timetable page confirms that C146 is active in the current summer period through 13 September 2026 and that winter 2026/27 begins on 14 September 2026.

ASF's official C146 line schema lists, in the study area, at least the following stop names:

- Perego - Via Statale 79
- Rovagnate - S.S. - Ang. V. Lombardia
- Rovagnate - Strada Statale - AGIP
- Rovagnate - Frazione Alduno
- Olgiate Molgora - Scarpone
- Olgiate Molgora - Via Statale
- Calco - Via Garibaldi
- Calco - Largo Pomea
- Calco - Via Statale - Ang. Scagnello
- Beverate - Cartello Paese
- Vaccarezza - Cartello Paese
- Brivio - Bar Cristallo
- Brivio - Via Como - Pensilina

The current C146 timetable also explicitly contains `Santa Maria Hoè - Via Como` on selected trips.

Primary sources:

- https://www.asfautolinee.it/wp-content/uploads/schema/C146.pdf
- https://www.asfautolinee.it/orari-in-pdf/
- https://www.asfautolinee.it/2026/04/15/brivio-chiusura-del-ponte-sul-fiume-adda-e-relative-modifiche-al-servizio/
- https://www.leccotrasporti.it/wp-content/uploads/2026/04/LECCO_Carta-della-mobilita-2026_web.pdf

### Consequence

Some C146 physical stops are already represented under Arriva/LineeLecco names, but route attribution and alias evidence are incomplete. Other C146 stop names have no obvious cluster in the current V3 master audit and therefore require spatial verification rather than name-only guessing.

Examples of likely already represented clusters:

- `Olgiate Molgora - Scarpone` → `EX_023`
- `Olgiate Molgora - Via Statale` → `EX_018`
- `S. Maria Hoè - Via Como` likely corresponds to the D184 `Alpino Via Como` / V3 `EX_032`, but this still needs stop-code or coordinate confirmation
- `Vaccarezza - Cartello Paese` likely corresponds to `EX_004`
- `Beverate - Cartello Paese` likely corresponds to `EX_008`

Potentially missing or unresolved official physical stops include at least:

- `Calco - Via Garibaldi`
- `Calco - Largo Pomea`
- `Calco - Via Statale - Ang. Scagnello`
- `Brivio - Bar Cristallo`
- `Rovagnate - Strada Statale - AGIP`

No missing-stop claim above should be promoted from `POTENTIAL_*` to `FACT` until ASF stop codes/coordinates are obtained and spatially conflated.

## Blocking finding 2: the frozen 2025/26 reference period is already temporally stale for a physical-stop audit

Arriva has published the 2026/27 timetables valid from 14 September 2026. They contain stop evidence that is not cleanly represented by exact names in the frozen V3 universe.

### D184 2026/27

The published D184 timetable confirms:

- Olgiate Molgora FS
- Olgiate Molgora Scarpone
- S. Maria Hoè Alduno
- Rovagnate SS342/Via Lombardia
- Perego SS342/Via S. Caterina
- S. Maria Hoè Alpino Via Como
- S. Maria Hoè Tremonte incrocio Via Leopardi
- S. Maria Hoè centro
- Hoè

Source: https://arriva.it/app/uploads/sites/7/2026/08/D184-Olgiate-Molgora-F.S.%E2%80%93Ravellino-inv27.pdf

Most are already represented in V3 under close aliases, which is reassuring. The important point is that the physical-stop inventory should use the current/published service evidence as a corroborating layer rather than freezing route attribution at 2025/26.

### D148 2026/27

The published D148 timetable contains, among others:

- S. Maria Hoè (Alpino)
- S. Maria Hoè Tre Strade
- Olgiate Molgora Via Statale
- Calco Località Cornello
- Brivio Via Como (Vaccarezza)
- Brivio
- Brivio - Via Provinciale Beverate (Elettroadda)
- Olgiate (Via Nazionale)
- Calco Largo Pomeo (gelateria)

Source: https://arriva.it/app/uploads/sites/7/2026/08/D148-S.Maria-Hoe-Airuno-Besana-inv27.pdf

`S. MARIA HOE' Tre Strade`, `CALCO Località Cornello` and `CALCO Largo Pomeo` require explicit current-source conflation because they do not have obvious one-to-one V3 cluster names.

## Blocking finding 3: core inventory and analysis-context stops must be separated

`existing_official_stops.csv` currently includes records selected in the Gate-B core context rather than a strict five-municipality physical inventory. The file contains examples whose names are clearly external to the core but whose `PRO_COM_T` is assigned to a core municipality, including:

- `Monte Marenzo - levata (smalti riva)` assigned to Brivio
- `Airuno - elettroadda` assigned to Brivio
- `Imbersago - arlate (fiorista)` assigned to Calco

This is acceptable for a **routing context envelope**, but not for answering "how many physical stops are inside municipality X".

The master inventory therefore needs two separate fields/contracts:

1. `physical_municipality_exact`: polygon containment using official ISTAT 2026 boundaries
2. `analysis_context_role`: core / buffer / external-tail / interchange context

Counts by municipality must use the first field only.

## Blocking finding 4: OSM remains a corroboration layer, not a census

The frozen OSM stop acquisition is useful but cannot establish completeness. The current acquisition lineage was built from a node-only Overpass query for `highway=bus_stop` and `public_transport=platform`; it can miss PTv2 `stop_position`-only objects and platform ways/areas, and OSM coverage in Santa Maria Hoè is visibly incomplete compared with official service evidence.

The V3 matcher already respects the correct source hierarchy. The next acquisition revision should broaden OSM element coverage without promoting OSM to official service truth.

## Secondary evidence requiring primary verification

A current secondary service aggregator updated at the end of August 2026 lists additional C146 stop names that are not present in the main ASF line schema viewed above:

- `S. Maria Hoè - Via Giovanni XXIII`
- `S. Maria Hoè - Paese`
- `Olgiate Molgora - Via Della Salute`

It also lists the primary-source stops `S. Maria Hoè - Via Como`, `Olgiate Molgora - Scarpone`, `Olgiate Molgora - Via Statale`, `Calco - Via Garibaldi` and `Calco - L.go Pomea`.

These extra names **must not be promoted to FACT from the aggregator alone**. They are a targeted queue for verification against the ASF stop database / stop codes and, secondarily, map imagery or field evidence. `Via Della Salute` is reported only metres from `Via Statale`, so it may be an opposite-side/directional alias rather than a distinct physical stop cluster.

Secondary source used only for discovery/review queue:

- https://moovitapp.com/index/it/mezzi_pubblici-line-c146-Milano_e_Lombardia-223-3758539-300934180-9

## Required next implementation

The other V3 workstream should continue unchanged on corridor generation and deterministic GTFS↔OSM conflation. In parallel, this source-completeness workstream should add a new input stage before the conflation result is called a master inventory:

1. acquire or export the authoritative ASF stop list for C146, ideally with stable stop codes and coordinates;
2. ingest published 2026/27 Arriva stop evidence as a current/future corroborating layer, without overwriting reference-period facts;
3. spatially assign every physical stop to exact ISTAT 2026 municipality polygons;
4. keep context/buffer stops in a separate role, not in strict municipality counts;
5. conflate all official operator sources first, then use OSM as physical corroboration;
6. preserve unresolved aliases and side-specific stops rather than forcing merges;
7. only after this stage recompute current-stop walking coverage and any existing-stop-first pruning.

## Machine-readable evidence

See:

`outputs/phase2/network_design_method_audit_v3/current_stop_source_completeness_gpt_v3.csv`

The CSV intentionally uses conservative statuses such as `POTENTIAL_MISSING_CLUSTER`, `LIKELY_EXISTING_ALIAS_REVIEW` and `SECONDARY_REVIEW_REQUIRED`. It is an audit queue, not a replacement stop dataset.

## Epistemic status

- official operator timetables / line schema: `FACT_PRIMARY_WEB_OBSERVATION`
- crosswalk to V3 cluster names without coordinates: `DERIVED_REVIEW_CANDIDATE`
- secondary aggregator-only names: `SECONDARY_REVIEW_REQUIRED`
- completeness verdict: `DERIVED_AUDIT_BLOCKER`

No candidate route, stop ranking or recommendation is produced by this audit.
