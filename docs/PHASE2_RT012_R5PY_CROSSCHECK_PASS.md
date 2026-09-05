# RT-012 PASS · Independent r5py passenger-routing smoke V3

RT-012 is PASS as integration infrastructure.

Validated branch: `phase2-r5py-crosscheck-v3`

Validated run: `33966673219`

Validated head: `cd661009b8e23c54d21440c37193d975ed660ce5`

Artifact: `9969668729`

Artifact digest: `sha256:39487fab748a13eb9f35df6042521a9cc9a37aab15b031cd956d0b2745b0fc2c`

## Environment

- Python `3.12.14`
- OpenJDK `21.0.12.1`
- r5py `1.1.7`
- pinned upstream Helsinki sample fixture

## Smoke result

R5 successfully built a `TransportNetwork` from OSM + GTFS. The audit produced four WALK OD rows and four TRANSIT OD rows with finite non-negative travel times. The repeated WALK request was exactly deterministic under the controlled request semantics.

Controlled results:

- WALK min/max: 4 / 19 min
- TRANSIT min/max: 4 / 15 min
- fixture service date selected from GTFS: 2022-02-22

## Role

R5/r5py is now authorized as an independent cross-check engine for later passenger-accessibility work. It does not replace Gate D road routing and this PASS contains no territorial candidate evidence.

The next territorial bridge must feed the same frozen origins, destinations, network inputs and candidate GTFS definitions to both engines and surface disagreements explicitly.
