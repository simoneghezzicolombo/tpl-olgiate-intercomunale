# RT-009 PASS · Directional Corridor Reciprocity Contract V3

Verdict: **PASS as semantic interface infrastructure**  
Canonical issue: **#31**  
Branch: `phase2-corridor-reciprocity-contract-v3`

## Validated contract

RT-009 safely converts directional RT-006 corridor evidence into undirected structural-link eligibility for later bidirectional RT-007/008 searches.

The adapter preserves, for each direction, whether it was explicitly tested, whether Gate D found a legal route and whether RT-006 admitted at least one loopless corridor.

## CI evidence

GitHub Actions run: `33965705976`  
Validated head: `340ba9e9441a5f448d52a7edf4c1f30b8d230e5d`  
Job: `101305368449`  
Artifact: `9969350642`  
Artifact digest: `sha256:4afc237b5107336cbedc5d794fee7d5c13fa87c3155fcf33c921537c7ae01bee`

All workflow stages passed: compilation, unit tests, controlled reciprocity audit, evidence validation, anti-geography / anti-stop / anti-winner / anti-random guards, whitespace check and artifact upload.

## Controlled fixture

Four unordered pairs exercise all contract states exactly once:

- `RECIPROCAL_BIDIRECTIONAL_CORRIDOR_AVAILABLE`: 1
- `UNTESTED_DIRECTION`: 1
- `NO_GATE_D_ROUTE_IN_DIRECTION`: 1
- `NO_ADMITTED_CORRIDOR_IN_DIRECTION`: 1

Only the reciprocal pair emits an undirected structural link.

## Key semantic protections

- `NOT_REQUESTED_IS_UNKNOWN_NOT_INFEASIBLE`
- both directions must be explicitly tested and each must have at least one admitted corridor
- multiple corridor variants collapse to one undirected structural link
- row/source-target ordering does not change unordered link identity or status
- directional diagnostics remain separate and are not combined into a score

## Explicit non-claims

This PASS authorizes only eligibility for a future **bidirectional undirected structural search**. It does not authorize directional-only service patterns, one-way circulators, territorial terminal selection, passenger stops, road-corridor choice, topology, timetable, headway, PRIMARY or RUNNER-UP.
