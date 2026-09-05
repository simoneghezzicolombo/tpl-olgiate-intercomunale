# RT-014 PASS · Deterministic candidate-GTFS materialization contract V3

RT-014 is PASS as generic GTFS materialization infrastructure.

Validated branch: `phase2-candidate-gtfs-materializer-v3`

Validated run: `33969580866`

Validated computational head: `6108347e7a6fc5bc0643c19c2f72f871ec0cb47b`

Artifact: `9970508859`

Artifact digest: `sha256:18c806bc5b664bbe150f31e7c57ee1e8f59ba1112e17afed97205b898f3bd636`

Controlled feed SHA256: `852eef41ca2e3309acc37a0e85745ebdad9c12c845c880d227480038df439954`

## Controlled result

The abstract fixture materializes six standard GTFS files (`agency`, `calendar`, `routes`, `stop_times`, `stops`, `trips`) from explicit stable boarding-point, route, pattern, calendar and departure inputs. Repeated builds and shuffled input order produce byte-identical files and a byte-identical ZIP.

The gate preserves GTFS times beyond midnight without wrapping, keeps shared boarding-point identities unique, validates exact foreign-key integrity and fails closed on unresolved stop references, duplicate stable IDs, invalid coordinates/calendars, broken stop sequences, decreasing cumulative runtimes and empty explicit departure sets.

No fuzzy matching, nearest-stop substitution, implicit stop creation, implicit headway generation, random search, geography or recommendation logic is present in the materializer core.

## Downstream role

When the parallel stop-inventory work freezes authoritative boarding points, territorial candidate patterns can reference those exact upstream IDs. RT-014 can then produce the same candidate GTFS for both the internal passenger-routing engine and the independent R5 engine, satisfying the candidate-feed identity requirement of RT-013.

## Non-claim

This PASS contains no territorial stop-pattern or timetable evidence and does not select a network topology, service calendar, headway, fleet plan, PRIMARY, RUNNER-UP or recommendation.
