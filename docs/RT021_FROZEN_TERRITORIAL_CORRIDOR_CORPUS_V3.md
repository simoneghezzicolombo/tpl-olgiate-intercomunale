# RT-021 · Frozen territorial corridor corpus V3

## Purpose

RT-021 materialises the complete directed road-corridor query corpus for the 35 frozen `CONVENTIONAL_TPL` stop places on the certified RT-017 border-neutral road graph.

The 35 stop places are technical routing query anchors only. They are not declared service termini or capolinea. The 36th stop place, Casa di Comunità, remains `SPECIAL_SERVICE` graph-attached context and is excluded from the automatic conventional pair universe.

## Frozen dependencies

- RT-017 evidence commit: `c8be50a2dc58a6251ae6622ca1fbd51ffb579d3f`
- RT-017 artifact: `9972204236`
- RT-017 artifact digest: `sha256:e0b71f6fd673345c3bc0bf8e32ecf66b7f620e27802f1eb5b24690a8295c8225`
- RT-017 OSM snapshot: `2026-09-05T13:45:50Z`
- final stop layer: `existing_stop_places_operational_gpt_v5.csv`, read-only
- directed query universe: 35 × 34 = 1,190 pairs

## Production routing contract

The production corridor generator is RT-006 bounded restriction-aware routing. It preserves the exact RT-017 certified shortest path as routing evidence, verifies its edge sequence, metrics and turn legality, and then generates physically loopless technical alternatives with the RT-006 bounded penalty method.

Default RT-006 technical controls:

- max alternatives: 3
- max generation rounds: 10
- penalty increment: 0.20
- max runtime factor: 1.50
- max overlap: 0.90

These are technical exploration controls, not policy weights, passenger utility scores or network-selection criteria.

## Validated-grid fallback

RT-006 Issue #22 established that full edge-state Yen is a correctness oracle but is not production-scalable on the real graph. The same gate certified a deterministic 12-configuration sensitivity grid:

- penalty increment: 0.10, 0.20, 0.35
- max runtime factor: 1.25, 1.50
- max overlap: 0.75, 0.90
- max alternatives: 3
- max generation rounds: 10

No configuration is selected or frequency-weighted. If the default RT-006 pool for a pair is empty, RT-021 evaluates the complete certified grid and retains the exact-edge-sequence union of all admitted physically loopless corridors.

Union semantics:

`UNION_ACROSS_TECHNICAL_EXPLORATION_SETTINGS_NOT_FREQUENCY_WEIGHTED_NOT_RANKED`

If the complete validated grid still yields no physically loopless corridor, the directed pair is preserved with explicit status:

`EXPLICIT_NO_LOOPLESS_CORRIDOR_WITHIN_VALIDATED_RT006_GRID`

and failure reason:

`NO_PHYSICAL_LOOPLESS_CORRIDOR_ADMITTED_WITHIN_VALIDATED_RT006_PARAMETER_GRID`

This status does **not** mean that the road pair is physically unreachable. RT-017 reachability remains valid. It means only that no physically loopless corridor was admitted by the certified RT-006 exploration envelope.

## Completeness rule

Every one of the 1,190 directed pairs must appear exactly once in the pair-execution table and must have either:

1. one or more admitted corridor records, or
2. a non-empty explicit failure reason.

No pair may disappear because routing is expensive or inconvenient.

## Determinism and parallel execution

The manifest is partitioned by complete source-anchor groups. No source group is split and no pair is sampled. Worker outputs are deterministically merged and the complete 1,190-pair manifest is re-audited after merge. The full corpus is built twice independently in CI and the output directories must be byte-identical.

## Claims not authorised

RT-021 does not authorise:

- complete K-shortest enumeration claims
- network recommendation
- topology winner
- service-terminus selection
- figure-eight prescription
- new-stop hypothesis
- timetable/headway choice
- `PRIMARY` or `RUNNER_UP`

## Pre-CI territorial diagnostic

An independent local replay against the pinned RT-017 artifact was used only as a development diagnostic before formal CI. It processed all 1,190 directed pairs and observed:

- 1,177 pairs with at least one loopless corridor under the default RT-006 setting
- 6 additional pairs recovered by the certified sensitivity-grid union
- 7 pairs with no loopless corridor admitted within the validated RT-006 grid
- 3,044 total admitted corridor records after the sensitivity recovery

These values are **not the formal RT-021 PASS evidence until the GitHub Actions workflow independently reproduces them and freezes the corresponding artifact/digests**.
