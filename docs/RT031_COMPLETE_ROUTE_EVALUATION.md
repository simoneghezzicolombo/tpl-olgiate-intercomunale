# Complete-route physical evaluation

Continuation of PR #80 at 4d87d92677859923c4e3c29bbd2ff3544c98b311.

The next integration step evaluates complete declared ordered routes on the real
288-atom carrier domain. Dynamic programming finds the exact minimum additive
carrier distance and counts compatible realizations without expanding their
Cartesian product. The first realization remains a state for cyclic routes, so
final-to-first legality cannot be dropped. Every repeated traversal is charged.
Unknown transitions, missing pair records or uncertified atomic/history scope
prevent an exact result. Ties use the ordered realization IDs deterministically.

The runner rebuilds the existing deterministic Hamiltonian path/cycle witnesses
from the pinned reciprocal atom endpoints (35 vertices, 110 links, 220 slots).
Six scenarios are declared before evaluation: path forward, path reverse, path
out-and-return, repeating out-and-return, cycle forward and cycle reverse.
These are stress scenarios, not a new candidate frontier, an all-stop target,
a complete territorial search, or a recommended route. Zero feasibility applies
only to that ordered sequence within the frozen atom domain.

Inputs are pinned RT017/022/030 files and the previously certified scoped
successor-via-way artifact 10023387513, ZIP SHA256
1603606d02a170567c1d423b7689b7044933fff6490caeaf848ae0ca0f2d77d0.
Atomic internal legality is replayed before DP. Every selected optimum is then
independently checked with the full-history composer, including cycle closure;
the appended first atom verifies the seam but is not double-charged.

Independent tests exhaust all 256 open / 4096 closed three-layer compatibility
graphs and compare counts and shortest witnesses against brute-force products.
CI rebuilds the real six-scenario outputs twice and requires byte identity.

Carrier distance is the resource substrate for an explicitly assigned movement,
not a service cost. Public events, passenger continuity, frequency, travel time,
depot/repositioning, annual vehicle-km and euros remain unassigned. In particular,
forward plus reverse distances do not prove feasible turning at a terminus; the
out-and-return scenarios check those boundaries explicitly. Existing production
review/calibration and search-domain requirements remain open.

Reproduce with PYTHONPATH=.:

```
python scripts/phase2_evaluate_rt031_complete_routes_v3.py --inputs INPUTS --via-way-evidence CERTIFICATE.json --out OUTPUTS
```

Artifact: rt031-complete-real-route-evaluation-v3. It contains full ordered
vertices, slots, selected realization IDs, exact counts, distances, source hashes,
unknown operational fields and a human-readable comparison. GitHub handoff
records the exact implementation head, run and result after execution.
