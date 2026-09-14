# RT-031 current-target resource symmetry

## Outcome

The corrected bounded search found one promotable physical candidate family: two
closed movements, both serving `FROZEN::L00407` (Olgiate FS), which together
retain all 11 current exact-ID targets used by the common RT-028 substrate.
This overturns the earlier pool-scoped negative interpretation; it does not
select a network.

| Item | Corrected two-movement witness |
|---|---:|
| Movement distances | 10.783106 km + 10.614172 km |
| Total traversal distance | 21.397278 km |
| H30, 16 h, 260 days | 178,025.354 km/year — over cap |
| H60, 16 h, 260 days | 89,012.677 km/year — within cap |
| Residual below 111,419 km cap | 22,406.323 km/year |

The same-substrate static walking-access shares improve from 21.7376%, 38.7287%
and 48.7696% to 31.2419%, 50.8247% and 60.2037% at 5/8/10 minutes. The three
worst-municipality safeguards remain exactly equal at 7.0608%, 20.9192% and
34.4032%. There is no weighted score.

## Superseded diagnostic witnesses

The unconstrained 15.450 km two-movement and 11.930 km three-movement witnesses
remain useful diagnostics but are not promoted. The former included a western
component that did not serve Olgiate FS; the latter additionally exploited a
265 m micro-loop. Static stop-identity coverage alone therefore produced false
passenger-network positives. The corrected portfolio invariant requires every
movement to serve Olgiate FS.

## Typed service and operational screen

The corrected H60 witness has been bound to directional occurrences and ordered
service events. Route/component/movement identity and passenger/vehicle
continuity are separate. No cross-component transfer, cycle-seam passenger
continuity, vehicle turn or interlining is inferred.

The source model gives running times of 23.834 and 23.482 minutes per circuit,
excluding dwell. Independently operating both H60 circuits gives a fleet lower
bound of two vehicles for 5, 10 and 15 minutes of recovery. This is a source-model
screen, not observed running time or a certified vehicle-block plan.

Both circuits are hourly. A combined 30-minute pattern at Olgiate FS would
require an explicit timetable phase; it is not inferred or certified.

## Epistemic boundary and remaining gates

The physical search stopped at 2,000,000 expanded states with 1,286,499 heap
entries pending (`RESOURCE_LIMIT_INCOMPLETE`). The witnesses pass full-history
physical replay, but their distances are minimum found, not global optima.

Before operational promotion the candidate still needs:

- dwell-inclusive running-time validation;
- explicit timetable phasing and S8 deterministic retention testing;
- recovery and vehicle-block feasibility;
- confirmation of any intended interchange semantics;
- comparison with the actual current-service timetable, not only its exact-ID
  static access subset.

No empirical missed-connection probability or demand-weighted GJT is claimed.
Municipal OD has not been spatially downscaled.

## Reproducibility

Hub-constrained search run `34869733360` succeeded at commit
`7e436b615170a509cd0270f20dc173388998766a`, artifact `10358581671`, ZIP digest
`sha256:9c7f95d7766914341a609f3a18cf734afedc0954302012c309dde932bd6f93fb`.
The full search JSON SHA256 is
`57f2079dd69decfe24571dbcaa032765496e5715410c440b2f964b5225e15f5f`; the
committed audit SHA256 is
`c164e047326c26a318851af86cf091c83aae345bcc39303d2ee46d92490fd0f1`.

Typed-service run `34892996081` succeeded at commit
`15e72c730026ce8bdbc936216b13b9667b5eb40b`, artifact `10368011342`, ZIP digest
`sha256:ceb3f307a0fbc04f6d06035c54f10a59e3715068cc6805c771ee13aa490ff9f5`.
The committed typed audit SHA256 is
`9fdb8f49ab1e59bbbe0a090396c5ac4fa98294e33474cb94adfe6ec331694ee6`.

`network_selected=false`

`primary_selection_authorised=false`

`runner_up_selection_authorised=false`
