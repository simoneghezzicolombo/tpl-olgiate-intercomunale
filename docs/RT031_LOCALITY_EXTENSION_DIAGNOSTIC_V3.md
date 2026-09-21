# RT031 — Brivio, Arlate, Pianezzo, Sartirana: extension diagnostic

This is a locality-preference and source-scope audit, not a route choice. The
machine-readable [scope audit](../outputs/phase2/rt031_locality_extension_scope_v3/locality_extension_scope_audit_v3.json)
pins the source files and keeps PRIMARY/RUNNER-UP unauthorised.

## What the existing two lines already do

The two one-line, all-five-municipality non-regressive candidates both include
Brivio capolinea (`FROZEN::300063`) and Bar Cristallo; one also includes Via
Como. They also include `ASF::ARLATE_B_VIO_BRIVIO_MADONNINA`, but that named
stop is **not** the village stop `Arlate - Bivio per il Paese` or `Arlate -
Cantina Pirovano`. Treating these three stop identities as interchangeable
would overstate coverage. Neither line includes Pianezzo or Sartirana.

There is no inherent Brivio-versus-Santa Maria coverage sacrifice in the
expanded evidence: both lines are non-regressive against the same current
exact-ID structural subset on total and every one of the five municipal
potential-walking axes at 5/8/10 minutes. The earlier 21 Brivio-improving
alternatives that lost Santa Maria were a narrower, resource-incomplete search
pool. The remaining tradeoff is with route length, stop retention, timetable,
transfer quality and operating uncertainty—not an established need to choose
one municipality over the other.

## Arlate: possible physically, not yet a good-line extension

The exact target-distance probe on the pinned 288-leg physical domain finds a
closed walk through Olgiate FS, exact Brivio `300063`, an exact Santa Maria
stop, and `Arlate - Cantina Pirovano` at **18.523 km/cycle**. Requiring instead
`Arlate - Bivio per il Paese` gives **19.587 km/cycle**. Both are below the
conditional 21.427 km/cycle reference envelope at 20 cycles/day and 260
days/year. The reproducible [Arlate audit](../outputs/phase2/rt031_arlate_extension_distance_v3/arlate_individual_distance_audit_v3.json)
records the separate witnesses and their scope.

These are *shortest physical co-presence* results, not alternatives proven to
retain the walking gains of the two stronger lines. The latter have only
35.965 m and 16.783 m of per-cycle slack at the 20×260 reference production.
Therefore simply appending a positive-length detour to either exact path
cannot stay inside that reference envelope. A replacement of existing segments,
an explicit change in daily cycle count/span, or a different resource context
would need to be evaluated; none is selected here. One additional kilometre
per cycle would add 5,200 km/year under the illustrative 20×260 context.

## Pianezzo and Sartirana: source-domain expansion needed

Pianezzo is an OSM settlement anchor in Olgiate Molgora. Four nearby proposed
stop candidates (`P2S_0002/0004/0006/0008`) relate to its walking-access gap,
but they remain `FIELD_CHECK_PENDING`; none is an attached stop in the pinned
RT022 physical domain. Road eligibility is a derived screening result, not
permission to claim a usable bus stop or passenger service.

The reference Arriva GTFS contains Sartirana stop IDs `300746/300747/300748/300887`
in Merate. They are not in the pinned RT022 stop attachments or the existing
five-municipality core walking comparison; the historical reference feed is
not a current-service guarantee. To evaluate Sartirana fairly, a new attached
stop/road/ordered-event domain and an explicit Merate reporting scope are
needed. Its potential benefit must not be hidden inside the current five-
municipality denominator.

Named localities remain **preferences**, not mandatory admission criteria.
No `decision_budget_km`, `uncertainty_band_min`, final line, span or phase has
been chosen.
