# RT-013 PASS · Cross-engine OD discrepancy contract V3

RT-013 is PASS as comparison infrastructure.

Validated branch: `phase2-cross-engine-discrepancy-v3`

Validated run: `33967001778`

Validated head: `a2a0f3e50636c4cdfdb783d03f41f630920e7b30`

Artifact: `9969744043`

Artifact digest: `sha256:354d20c80450a575dd82493c7e7dd4b502a8ad2f760552fc0bbdd10ab2d91ce9`

## Controlled result

The controlled fixture contains five aligned OD pairs. A deliberately large 20-minute disagreement remains visible as both the maximum and P95 absolute discrepancy. Mean absolute discrepancy is 4.8 minutes and mean signed `B - A` discrepancy is 4.4 minutes.

The contract fails closed on missing, extra or duplicate OD identities, preserves signed differences, leaves relative difference undefined when the engine-A denominator is zero, and never averages engine outputs.

Reporting bands are descriptive only and create no automatic equivalence claim.

## Non-claim

This PASS contains no territorial routing evidence. A territorial cross-engine comparison is valid only after both engines receive identical frozen OD identities, network vintages, candidate GTFS definitions and time/mode semantics.
