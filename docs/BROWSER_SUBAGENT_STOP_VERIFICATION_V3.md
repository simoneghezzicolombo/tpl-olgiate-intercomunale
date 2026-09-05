# Browser subagent stop verification V3

## Purpose
Use browser access to Google Maps only for targeted visual/cartographic verification after official-source acquisition. Google Maps is corroborating evidence, not the sole proof of service existence or absence.

## Task A — export all ASF official stops, not only C146
Use the ASF OTP backend at `https://transitpay.asfautolinee.it/otp/routers/default/index/`.

1. Fetch the full `routes` list.
2. For every ASF route, fetch `/routes/{route_id}/stops`.
3. Preserve raw stop fields including at minimum route id/short name, stop id if exposed, code, name, lat, lon.
4. Spatially join every stop against `data/raw/boundaries/comuni_core_istat_2026.geojson` using exact polygon containment.
5. Output all ASF stop records inside the five study municipalities, not just C146.
6. Do not deduplicate directional stop records.
7. Save raw responses or a reproducible cache plus a CSV.

Required outputs:
- `data/raw/asf/asf_otp_routes_snapshot.json`
- `data/raw/asf/asf_otp_stops_all_routes_snapshot.json` or per-route raw snapshots
- `outputs/phase2/network_design_method_audit_v3/asf_all_routes_stops_core_v3.csv`

CSV fields:
`route_id,route_short_name,stop_id,stop_code,stop_name,lat,lon,physical_municipality_exact,source_url,retrieved_at`

## Task B — C146 A/R pair geometry
For the 39 C146 directional records already discovered:

1. Export the exact ASF `lat` and `lon` for every stop code.
2. Pair A/R candidates only when supported by the operator naming/code structure. Never merge them.
3. Compute A↔R geodesic distance in metres.
4. Output whether coordinates are identical, near but distinct, or clearly separated.

Required output:
`outputs/phase2/network_design_method_audit_v3/asf_c146_directional_pair_geometry_v3.csv`

Fields:
`stop_place_name,code_a,lat_a,lon_a,code_r,lat_r,lon_r,distance_m,pair_status`

`pair_status` must be descriptive only, e.g. `SAME_COORDINATE_RECORDS`, `DISTINCT_NEARBY_BOARDING_POINTS`, `DISTINCT_SEPARATED_POINTS`, `UNPAIRED_RECORD`. Do not infer that nearby points are the same physical boarding point.

## Task C — targeted Google Maps checks
Do not rescan the whole territory. Check only the following cases and record the exact Google Maps pin(s), canonical visible name(s), coordinates from the pin URL if available, and whether one or two distinct transit pins are shown.

### C1. Santa Maria Hoè / Tremonte conflict — highest priority
Resolve these as distinct candidate locations unless Maps proves otherwise:
- `Santa Maria Hoè - Via Giovanni XXIII`, known Maps coordinate from manual verification: approximately `45.7412097, 9.3803030`, ASF codes `SAMAHA04 / SAMAHR04`.
- `S.Maria Hoe' - tremonte/via leopardi`, Arriva GTFS `300903`, approximately `45.74118, 9.38096`.
- `S.Maria Hoe' - tremonte`, Arriva GTFS `300805`, approximately `45.74280, 9.37837`.
- claimed `Tremonte / Via Trento`, approximately `45.74259, 9.37831`.

The previous browser report incorrectly stated that Via Leopardi coincides with ASF `SAMAHA04 / Via Giovanni XXIII`; the known coordinates are about 47 m apart. Determine which Google Maps pins actually exist and keep them distinct if distinct.

### C2. Scagnello
`Calco - Via Statale / Via Scagnello (Esselunga)`.
The previous report says there are two opposite-side pins but supplied only one coordinate. Return both exact pin coordinates and names if two are visible.

### C3. Alduno
`Rovagnate - Frazione Alduno` / Arriva `S.Maria Hoe' - alduno`.
The previous report says there are two specular points but supplied only one coordinate. Return both exact Google Maps pins if two exist. Do not resolve the municipality/name disagreement by name; use exact ISTAT polygon containment after coordinates are obtained.

### C4. Arlate Bivio Brivio / Madonnina
Verify whether `CALCOA09` has a visible opposite-side Google Maps boarding point. The ASF route list currently showed an A-code without an obvious R-code in the user-provided extract. Record whether Maps shows one or two pins and their coordinates.

### C5. No-stop localities
For San Zeno, Mondonico borgo and Calco Alta / Piazza San Vigilio, do not state `no TPL` solely from Maps absence. Record:
- whether a transit pin is visible at high zoom;
- exact nearest visible Google Maps bus-stop pin and approximate map distance;
- a screenshot or canonical Google Maps URL if practical.

Final interpretation must be `NO_GOOGLE_MAPS_TRANSIT_PIN_OBSERVED` unless official operator/GTFS evidence independently proves absence of ordinary service.

## Epistemic rules
- Google Maps presence can corroborate a physical boarding point.
- Google Maps absence cannot by itself prove no real-world stop exists.
- Official ASF OTP / operator GTFS outrank Google Maps for service attribution.
- Never merge two stops based only on distance.
- Preserve directional boarding points independently from stop-place grouping.
