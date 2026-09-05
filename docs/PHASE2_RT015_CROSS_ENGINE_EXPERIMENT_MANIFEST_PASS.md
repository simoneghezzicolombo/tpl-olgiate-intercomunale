# RT-015 PASS · Frozen cross-engine experiment manifest V3

RT-015 is PASS as generic cross-engine experiment-identity infrastructure.

Validated branch: `phase2-cross-engine-experiment-manifest-v3`

Validated run: `33969776194`

Validated computational head: `a47663b9b252d0573a7a6bc5bc49c91ca05a6a12`

Artifact: `9970563959`

Artifact digest: `sha256:9ac8a08885bf11b4aea02c785ce7e9d74b999e61570d43df65976abdf9074943`

Controlled experiment manifest SHA256: `57edd49f936763fcf99b884b663844c667bfdec72e05e400c876f4247ce6a268`

## Controlled result

The abstract fixture freezes candidate identity, candidate-GTFS SHA256, street-network SHA256, service date, IANA timezone, departure window, mode semantics and the exact unique OD universe into canonical JSON with a deterministic SHA256 identity.

Repeated freezing and shuffled OD/mode input order produce byte-identical canonical JSON and the same manifest hash. Material changes to candidate GTFS, street network, date, departure window, mode set or OD universe change the experiment identity.

The contract fails closed on malformed hashes, duplicate or empty OD universes, invalid date/timezone values, empty mode semantics and negative or reversed departure windows.

Cross-engine comparison is authorized only when exactly two distinct engine labels bind to the exact same frozen manifest SHA256. A mismatch is `EXPERIMENT_IDENTITY_MISMATCH` and is rejected before routing discrepancies can be interpreted.

## Downstream role

RT-014 materializes a deterministic candidate GTFS. RT-015 freezes the complete shared experiment identity. The internal passenger-routing engine and R5 must both bind to that identity. RT-013 may compare their OD outputs only after the RT-015 identity check succeeds.

## Non-claim

This PASS contains no territorial OD, service-pattern, timetable or routing-result evidence. It does not select a topology, service policy, PRIMARY, RUNNER-UP or recommendation.
