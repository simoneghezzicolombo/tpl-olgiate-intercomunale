# RT-023 PASS candidate: topology-neutral service-pattern realization bridge V3

## Scope

RT-023 is a downstream compiler only. It consumes the certified RT-022 reciprocal structural-link interface and the exact directed corridor evidence carried by the certified RT-022 workflow artifact. It does not enumerate, rank or select network structures.

For every reciprocal structural link, A→B and B→A are materialized independently from their certified directed pair IDs. The implementation contains no reverse-path fallback.

## Outputs

The compiler emits:

- `link_realization_catalog.csv`: one row per certified directed elementary corridor alternative, with exact path identity and ordered passenger stop sequence;
- `structure_link_manifest.csv`: lazy references from each RT-022 structure to its four structural links, without Cartesian expansion of corridor alternatives;
- `rt014_pattern_fragments.csv`: service-neutral ordered stop-pattern fragments;
- `rt023_service_pattern_realization_audit.json`: counts, deterministic output digests, lineage digests and negative assertions.

The RT-014 adapter requires `pattern_id`, `route_id`, `service_id`, `direction_id`, cumulative stop times and explicit departures from the downstream caller. RT-023 supplies none of those decisions.

## Real-data certification target

The certified RT-022 handoff contains 110 reciprocal structural links and 88 exact minimum backbones. The compiler also fail-closes unless the frozen stop layer is exactly 36 stop places: 35 `CONVENTIONAL_TPL` eligible for automatic materialization plus the single excluded `SPECIAL::CASA_DI_COMUNITA_OLGIATE` `SPECIAL_SERVICE` stop. The RT-023 real-data run must compile:

- 352 structure-to-link references;
- 288 directed link realizations;
- 141 A→B realizations;
- 147 B→A realizations;
- 288 RT-014 pattern fragments.

All negative assertions in the audit must remain false. The controlled suite contains 16 contract tests, including graph-epoch mismatch, unknown link/pair/corridor failures and explicit rejection of a 43-stop input universe.

## Ownership boundary

RT-023 does not modify RT-021 or RT-022, add links, choose a HUB or figure-8, choose terminals as service policy, select PRIMARY/RUNNER-UP, choose frequencies, headways, calendars, departures or timetables, create passenger stops or make territorial recommendations.
