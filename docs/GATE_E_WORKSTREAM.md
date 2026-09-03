# Gate E workstream: service math audit

## Verdict

**PROVISIONAL / BLOCKED_BY_GATE_C_AND_GATE_D**

Gate E can be developed and tested independently, but it cannot receive a definitive PASS until the service calendar/timetable inputs from Gate C and the route distances/running times from Gate D are independently validated. This document therefore separates verified arithmetic from upstream-dependent scenario results.

## Baseline and protocol

This workstream was started from `antigravity-real-data` and fast-forwarded before its first commit to commit `5b832db35c0d67d4866ff95c960ab1658ac8b301` because the upstream branch advanced during the audit.

`AGENT_PROTOCOL.md` is not present at this baseline. The operative repository protocol is `COLLABORATION_PROTOCOL.md`, together with `AGENT_STATUS.md` and Issue #1, **Agent Coordination Bus**.

At the inspected baseline:

- Gate A is formally PASS according to `AGENT_STATUS.md` and `docs/GATE_A_PASS.md`.
- Gate B is still the active checkpoint and is not treated as PASS merely because implementation commits exist.
- Gate C and Gate D have no formal PASS available to this workstream.
- Consequently every scenario-level Gate E result is provisional until C and D are both PASS.

## What was invalidated

The previous Gate E implementation cannot be treated as evidence because it violates the project's anti-synthetic and anti-hardcoding rules.

### `scripts/10_service_simulation.py`

The previous version embedded complete scenario outcomes directly in Python literals, including route kilometres, cycle times and recovery, number of buses, cycles per day, annual bus-km, annual vehicle-hours, frequencies, sustainability labels and a preselected “recommended” and “optimal” scenario.

Those values were written directly to `outputs/service_simulation_scenarios.csv`. They were not recomputed from validated Gate C/D outputs. For Gate E purposes, that legacy scenario table is therefore **INVALIDATED**.

### `tests/test_cycle_times.py`

The previous test asserted that a particular legacy variant had exactly 55 minutes of runtime and exactly 60 minutes of programmed cycle time. Because the source CSV itself was produced from hardcoded values, the test could remain green while the real route or timetable was wrong. The test is replaced with regression checks on the service-math formulas and input guardrails.

### Legacy Gate D feed-through

`outputs/route_variants.csv` and the corresponding generator `scripts/08_candidate_routes.py` contain manually entered route distances, runtimes, population, OD and judgments. Those values must not feed Gate E. The new Gate E script accepts only a dedicated integrated input contract and refuses to fall back to legacy route outputs.

## Mathematical errors found

### 1. CW, CCW and combined headway were conflated

For a 60-minute cycle:

- 1 bus CW gives `headway_CW = 60 min`;
- 1 bus CCW gives `headway_CCW = 60 min`;
- if the two directions are evenly phased, their service-rate equivalent is `headway_combined = 30 min`.

The legacy output labelled the two-bus CW+CCW configuration simply as 30-minute core frequency. That is only valid as a **combined** frequency, not as a 30-minute frequency in each direction.

Conversely, a genuine 30-minute headway in each direction on a 60-minute cycle requires 2 buses CW, 2 buses CCW and 4 buses total. The combined service-rate equivalent is 15 minutes if evenly phased. The new tests enforce this distinction.

### 2. “Saldo zero esatto” was numerically false

The legacy scenario 4 reported 112,261.5 bus-km/year against the 111,419 bus-km/year benchmark, a delta of +842.5 km/year, about +0.76%. It simultaneously described this as “neutralità economica esatta” and “saldo zero esatto”. A positive delta is not exact zero. Gate E now reports the absolute and percentage delta without qualitative relabelling.

### 3. Directional cycles were ambiguous

A field such as “13 cycles/day” is not sufficient for a bidirectional system unless it states whether it means 13 vehicle loops total, 13 CW plus 13 CCW, or 13 paired departures. Bus-km can differ by a factor of two under those interpretations. The new input contract has one row per direction and `daily_cycles` is explicitly a count of full vehicle cycles in that direction.

### 4. Service days were embedded as a constant

The legacy calculation used 303 service days/year as an unexplained production constant. Gate E no longer embeds this value. `service_days_year` must arrive through the integrated Gate C/D input, where Gate C can derive it from validated service calendars or it can be explicitly marked `ASSUMPTION` for sensitivity analysis only.

### 5. Cycle components were not sufficiently protected

The protocol requires separation of pure running, dwell and recovery/layover. The new engine computes `cycle_minutes = pure_running_minutes + dwell_minutes + recovery_minutes`. Negative recovery is rejected rather than being used to make an infeasible route appear feasible.

## New Gate E input contract

Default input: `outputs/gate_e_inputs.csv`.

Each scenario must have exactly one CW row and one CCW row with:

- `scenario_id`
- `direction` (`CW` or `CCW`)
- `epistemic_status`
- `analysis_mode`
- `upstream_gate_c_status`
- `upstream_gate_d_status`
- `route_km`
- `pure_running_min`
- `dwell_min`
- `recovery_min`
- `target_headway_min`
- `daily_cycles`
- `service_days_year`

`PLACEHOLDER` and `INVALIDATED` inputs are rejected. `ASSUMPTION` is accepted only when `analysis_mode=SENSITIVITY`.

A scenario cannot become eligible for a Gate E verdict unless both upstream gate-status fields are `PASS` for both directions. Otherwise the output is automatically marked `PROVISIONAL/BLOCKED_BY_...`.

## Deterministic outputs

For each direction the engine computes cycle minutes, vehicles required for the target directional headway, annual bus-km and annual scheduled vehicle-hours.

For each bidirectional scenario it computes `headway_CW_min`, `headway_CCW_min`, `headway_combined_rate_equiv_min`, vehicles required CW/CCW/total, annual bus-km, annual scheduled vehicle-hours and absolute/percentage delta against the D184+D185 benchmark.

The combined headway is deliberately labelled **rate equivalent**. Without actual phased departure times it is not a guarantee of the maximum passenger-facing gap at every stop. Exact stop-level combined headways belong to timetable validation using Gate C data.

## PdB benchmark

`data/risorse_tpl_pdb.csv` reconstructs D184 = 52,560 bus-km/year, D185 = 58,859 bus-km/year and D184 + D185 = **111,419 bus-km/year**.

The new loader independently checks the arithmetic `52,560 + 58,859 = 111,419` and fails if the table is internally inconsistent. The scenario engine does not embed 111,419 as a Python constant.

Because this workstream did not re-extract the table directly from the binary PdB PDF, the two line values are conservatively labelled **RECONSTRUCTED** in the Gate E benchmark output, while their sum is **DERIVED**. Gate A separately records the official PdB PDFs as FACT sources. A definitive Gate E PASS should retain the link between this reconstruction and the exact PdB table/page used.

## Sensitivity arithmetic that is safe to state now

These are formula checks, not route recommendations.

For a 60-minute cycle, 60-minute headway in each direction requires 1 vehicle per direction, 2 total, and the combined rate-equivalent headway is 30 minutes. A 30-minute headway in each direction requires 2 vehicles per direction, 4 total, and the combined rate-equivalent headway is 15 minutes.

If, purely as sensitivity, a scenario ran 13 full cycles/day **in each direction** for 303 days/year, there would be 7,878 directional vehicle cycles/year. Under the 111,419 bus-km benchmark, the mean distance affordable per directional cycle would be about 14.143 km. This is not a project result because both 13 cycles/day and 303 days/year require Gate C validation or explicit ASSUMPTION status.

## Conditions to close Gate E

1. Gate C PASS, with validated service dates/calendars and timetable semantics relevant to daily cycles and phasing.
2. Gate D PASS, with validated route kilometres and pure running times for every candidate actually tested.
3. Produce `outputs/gate_e_inputs.csv` from those upstream outputs without manual transcription of results.
4. Run `scripts/10_service_simulation.py` and inspect both direction-level and scenario-level outputs.
5. Verify dwell and recovery policy and its epistemic status. If they are assumptions, keep them in sensitivity analysis rather than presenting them as observed facts.
6. Validate exact combined stop-level gaps from phased timetables if `headway_combined` is used as a passenger-facing frequency claim.
7. Retain absolute and percentage bus-km deltas. Do not relabel a non-zero delta as exact neutrality.

Until these conditions are met, the correct Gate E verdict is **PROVISIONAL / BLOCKED_BY_GATE_C_AND_GATE_D**.
