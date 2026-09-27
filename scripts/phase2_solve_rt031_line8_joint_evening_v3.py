"""Joint dispatch/peak/fleet comparisons on frozen road patterns; no selection.

Fleet occupation is exact ONLY with all represented FS joins compatible.
Coverage is checked continuously across nine deterministic timing scenarios.
"""
import argparse
from collections import Counter, defaultdict
import itertools
import json
from pathlib import Path
import time

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csc_matrix

from scripts.phase2_compare_rt031_line8_evening_reallocation_v3 import BASE, EXPECTED, FLAGS, load_sources, ordered
from scripts.phase2_audit_rt031_line8_dwell_sensitivity_v3 import adjusted_loops
from scripts.phase2_audit_rt031_line8_independent_wings_v3 import minimum_blocks
from scripts.phase2_audit_rt031_line8_passenger_peaks_v3 import uncovered_intervals
from scripts.phase2_solve_rt031_line8_flexible_peaks_v3 import interval_covers

GRID = tuple(itertools.product((.9, 1., 1.1), (0., .5, 1.)))
PHASES = [('AM', t) for t in range(390, 421, 5)] + [('PM', t) for t in range(990, 1021, 5)]
LOCAL_SITES = ('RT031::P2V2S_0031_PROJECTED_ROAD_POINT', 'PROXY::SAN_ZENO_VIA_CANTU_ROAD_NODE')
DEFAULT_PM_ARRIVALS = (992, 1022, 1052, 1082, 1112, 1172, 1232)


def family_inputs(sources):
    w, t, c = (sources[k] for k in ('wings', 'timetable', 'counterflow'))
    if any(any(item[k] is not False for k in FLAGS) for item in (w, t, c)):
        raise ValueError('decisional evidence')
    return [dict(name='original_priority_direction', loops=w['loops'], source_trips=t['trips'],
                 joins=w['represented_via_node_joins'], all_patterns_fast_local=False),
            dict(name='fast_local_both_directions', loops=c['candidate_loops'],
                 source_trips=c['full_correction_one_minute_retiming']['trips'],
                 joins=next(x for x in c['cases'] if x['case_id'] == 'both')['represented_via_node_joins'],
                 all_patterns_fast_local=True)]


def occupied_sets(trips, loops, recovery):
    """Half-open [departure, next-ready) sets at every departure instant."""
    return sorted({tuple(i for i, t in enumerate(trips)
                         if t['departure_min'] <= instant < t['departure_min'] + loops[t['loop']]['road_minutes'] + recovery - 1e-9)
                   for instant in sorted({t['departure_min'] for t in trips})})


def events_by_site(trips, loops):
    result = defaultdict(list)
    for i, trip in enumerate(trips):
        for event in loops[trip['loop']]['events']:
            if event['stop_place_id'] in LOCAL_SITES:
                same = [e for e in loops[trip['loop']]['events'] if e['stop_place_id'] == event['stop_place_id']]
                # Do not let an early local pass followed by the long loop satisfy
                # a frequency promise intended for the short journey to FS.
                if event['offset_from_wing_origin_min'] < max(e['offset_from_wing_origin_min'] for e in same):
                    continue
            result[event['stop_place_id'], 'to_fs'].append((i, trip['departure_min'] + event['offset_from_wing_origin_min']))
            result[event['stop_place_id'], 'from_fs'].append((i, trip['departure_min']))
    return result


def prepare(family, offpeak_wait, compile_constraints=True, ready_span=(390, 1240),
            pm_arrivals=DEFAULT_PM_ARRIVALS, am_wait_ceiling_comparison_min=None,
            timing_grid=None):
    # Explicit diagnostic subsets only; never silently reduce the default grid.
    grid = GRID if timing_grid is None else tuple(tuple(pair) for pair in timing_grid)
    if (not grid or len(set(grid)) != len(grid) or not set(grid) <= set(GRID)
            or (1.1, .5) not in grid):
        raise ValueError('invalid timing comparison grid; nominal fleet case required')
    if set(grid) != set(GRID) and am_wait_ceiling_comparison_min is None:
        raise ValueError('reduced timing grid requires explicit unchanged AM comparison ceiling')
    if offpeak_wait not in (60, 90, 120):
        raise ValueError('unsupported off-peak comparison')
    if ready_span[0] != 390 or ready_span[1] not in (1180, 1210, 1240):
        raise ValueError('unsupported service span comparison')
    if not pm_arrivals or len(set(pm_arrivals)) != len(pm_arrivals):
        raise ValueError('missing or duplicate declared PM anchors')
    raw, joins = family['loops'], family['joins']
    core_patterns = {'west_A', 'west_B', 'east_A', 'east_B'}
    extended = set(raw) != core_patterns
    if extended and (not core_patterns <= set(raw)
                     or any(not p.startswith(('west_', 'east_')) for p in raw)
                     or family.get('rail_anchor_scope') != 'each_declared_site'
                     or not family['all_patterns_fast_local']):
        raise ValueError('extended patterns require explicit per-site rail anchors and fast locals')
    if not core_patterns <= set(raw) or any(
            joins.get(a + '>' + b) is not True for a in raw for b in raw):
        raise ValueError('occupation formulation requires every represented FS join')
    actual_sites = {e['stop_place_id'] for loop in raw.values() for e in loop['events']}
    declared_sites = family.get('comparison_nonhub_site_ids')
    if declared_sites is None:
        if len(actual_sites) != 27:
            raise ValueError('site domain drift')
    elif (len(declared_sites) != len(set(declared_sites)) or set(declared_sites) != actual_sites
          or not set(LOCAL_SITES) <= actual_sites):
        raise ValueError('declared comparison site domain drift')
    trips = [{'loop': pattern, 'departure_min': minute} for pattern in sorted(raw)
             for minute in range(360, ready_span[1] + 1, 5)]
    adjusted = {(m, d): adjusted_loops(raw, m, d) for m, d in grid}
    n = len(trips)
    covers = set()
    if compile_constraints:
        for loops in adjusted.values():
            for events in events_by_site(trips, loops).values():
                covers.update((cover, -1) for cover in interval_covers(events, *ready_span, offpeak_wait))
                for phase_index, (_, start) in enumerate(PHASES):
                    covers.update((cover, phase_index) for cover in interval_covers(events, start, start + 120, 30))
    # Inherited engineering comparison ceiling, NOT a caller-approved preference:
    # worst transfer residual among the original ten AM runs and all grid cases.
    original_am = {p: sorted(t['departure_min'] for t in family['source_trips'] if t['loop'] == p)
                   for p in ('west_A', 'east_B')}
    if any(len(v) != 5 for v in original_am.values()):
        raise ValueError('AM target inventory drift')
    targets = [446, 476, 506, 536, 566]
    wait_ceiling = max(target - departure - loops[p]['road_minutes'] - 3
                       for p, times in original_am.items() for departure, target in zip(times, targets)
                       for loops in adjusted.values())
    if am_wait_ceiling_comparison_min is not None:
        if not np.isfinite(am_wait_ceiling_comparison_min) or am_wait_ceiling_comparison_min < 0:
            raise ValueError('invalid explicit AM wait comparison ceiling')
        wait_ceiling = float(am_wait_ceiling_comparison_min)
    anchors = []
    for wing, am, rest in (('west', 'west_A', 'west_B'), ('east', 'east_B', 'east_A')):
        for target in targets:
            eligible = tuple(i for i, trip in enumerate(trips)
                             if trip['loop'].startswith(wing)
                             and (family['all_patterns_fast_local'] or trip['loop'] == am)
                             and all(-1e-8 <= target - trip['departure_min'] - loops[trip['loop']]['road_minutes'] - 3 <= wait_ceiling + 1e-8
                                     for loops in adjusted.values()))
            anchors.append({'wing': wing, 'kind': 'bus_to_rail', 'rail_min': target, 'eligible': eligible})
        # Frozen PM train arrivals already represented by the 16:40..18:40 bank
        # plus the two evening arrivals. Retain the original eight-minute wait.
        for arrival in pm_arrivals:
            eligible = tuple(i for i, trip in enumerate(trips)
                             if trip['loop'].startswith(wing)
                             and (family['all_patterns_fast_local'] or trip['loop'] == rest)
                             and 3 <= trip['departure_min'] - arrival <= 8)
            anchors.append({'wing': wing, 'kind': 'rail_to_bus', 'rail_min': arrival, 'eligible': eligible})
    if family.get('rail_anchor_scope') == 'each_declared_site':
        pattern_sites = {p: {e['stop_place_id'] for e in loop['events']} for p, loop in raw.items()}
        site_anchors = []
        for anchor in anchors:
            wing_sites = set.union(*(s for p, s in pattern_sites.items()
                                    if p in core_patterns and p.startswith(anchor['wing'])))
            for sid in sorted(wing_sites):
                site_anchors.append({**anchor, 'stop_place_id': sid,
                                     'eligible': tuple(i for i in anchor['eligible'] if sid in pattern_sites[trips[i]['loop']])})
        anchors = site_anchors
    if any(not a['eligible'] for a in anchors):
        raise ValueError('empty rail anchor domain; do not relax silently')
    rows, cols, data, lower, upper = [], [], [], [], []

    def add(indices, lo, hi, phase=None):
        row = len(lower)
        for i in indices:
            rows.append(row); cols.append(i); data.append(1.)
        if phase is not None:
            rows.append(row); cols.append(n + phase); data.append(-1.)
        lower.append(lo); upper.append(hi)

    for indices, phase in sorted(covers):
        add(indices, 1. if phase == -1 else 0., np.inf, None if phase == -1 else phase)
    for peak in ('AM', 'PM'):
        add([n + i for i, (label, _) in enumerate(PHASES) if label == peak], 1., 1.)
    for anchor in anchors:
        add(anchor['eligible'], 1., np.inf)
    fleet_rows = []
    for indices in occupied_sets(trips, adjusted[1.1, .5], 10):
        fleet_rows.append(len(lower))
        add(indices, -np.inf, np.inf)
    matrix = csc_matrix((data, (rows, cols)), shape=(len(lower), n + len(PHASES)))
    costs = np.array([raw[t['loop']]['distance_m'] / 1000 for t in trips] + [0.] * len(PHASES))
    return dict(family=family, offpeak_wait=offpeak_wait, trips=trips, adjusted=adjusted,
                ready_span=tuple(ready_span), pm_arrivals=tuple(pm_arrivals),
                constraints_compiled=compile_constraints, timing_grid=grid,
                anchors=anchors, wait_ceiling=wait_ceiling, matrix=matrix, costs=costs,
                lower=np.array(lower), upper=np.array(upper), fleet_rows=fleet_rows)


def verify(problem, trips, phases, fleet_bound):
    if len(phases) != 2 or {p['peak'] for p in phases} != {'AM', 'PM'}:
        raise ValueError('invalid phase selection')
    if any((p['peak'], p['start_min']) not in PHASES or p['end_min'] != p['start_min'] + 120 for p in phases):
        raise ValueError('phase outside declared domain')
    candidate_indices = {(t['loop'], t['departure_min']): i for i, t in enumerate(problem['trips'])}
    selected = {candidate_indices[t['loop'], t['departure_min']] for t in trips}
    if len(selected) != len(trips):
        raise ValueError('duplicate dispatch')
    for anchor in problem['anchors']:
        if not selected.intersection(anchor['eligible']):
            raise ValueError('rail anchor verification failure')
    grid = []
    for (m, d), loops in problem['adjusted'].items():
        available = events_by_site(trips, loops)
        expected_sites = {e['stop_place_id'] for loop in loops.values() for e in loop['events']}
        if {sid for sid, direction in available} != expected_sites:
            raise ValueError('selected trips omit declared service sites')
        for opportunities in available.values():
            times = [t for _, t in opportunities]
            if uncovered_intervals(times, *problem['ready_span'], problem['offpeak_wait']):
                raise ValueError('off-peak continuous verification failure')
            for phase in phases:
                if uncovered_intervals(times, phase['start_min'], phase['end_min'], 30):
                    raise ValueError('peak continuous verification failure')
        for recovery in (5, 10, 15):
            blocks = minimum_blocks(trips, loops, problem['family']['joins'], recovery)
            occupation = max(len(indices) for indices in occupied_sets(trips, loops, recovery))
            if occupation != blocks['minimum_vehicle_count_conditional']:
                raise ValueError('occupation/path-cover disagreement')
            if (m, d, recovery) == (1.1, .5, 10) and occupation > fleet_bound:
                raise ValueError('nominal fleet bound violated')
            grid.append({'moving_multiplier': m, 'dwell_min': d, 'recovery_min': recovery, **blocks})
    return grid


def solve(problem, fleet_bound, time_limit=30, fixed_peak_starts=None):
    if not problem['constraints_compiled']:
        raise ValueError('coverage constraints not compiled')
    if fleet_bound not in (4, 5, 6):
        raise ValueError('unsupported comparison fleet bound')
    upper = problem['upper'].copy()
    upper[problem['fleet_rows']] = fleet_bound
    variable_upper = np.ones(len(problem['costs']))
    if fixed_peak_starts is not None:
        if set(fixed_peak_starts) != {'AM', 'PM'} or any((label, start) not in PHASES for label, start in fixed_peak_starts.items()):
            raise ValueError('fixed peaks outside declared phase domain')
        for i, (label, start) in enumerate(PHASES):
            if start != fixed_peak_starts[label]:
                variable_upper[len(problem['trips']) + i] = 0
    started = time.monotonic()
    answer = milp(problem['costs'], integrality=np.ones(len(problem['costs'])),
                  bounds=Bounds(0, variable_upper), constraints=LinearConstraint(problem['matrix'], problem['lower'], upper),
                  options={'time_limit': time_limit, 'mip_rel_gap': 0})
    result = {'family_id': problem['family']['name'], 'offpeak_wait_comparison_min': problem['offpeak_wait'],
              'ready_span_comparison_min': list(problem['ready_span']),
              'timing_grid_comparison': [list(pair) for pair in problem['timing_grid']],
              'declared_pm_rail_arrival_targets_min': list(problem['pm_arrivals']),
              'nominal_fleet_bound_comparison': fleet_bound, 'candidate_trip_count': len(problem['trips']),
              'constraint_count': problem['matrix'].shape[0], 'solver_status': int(answer.status),
              'solver_message': str(answer.message), 'solver_time_limit_s': time_limit,
              'solve_elapsed_s': round(time.monotonic() - started, 3),
              'infeasibility_proven_in_this_domain': answer.status == 2,
              'optimality_proven_in_this_domain': bool(answer.success),
              'am_residual_wait_ceiling_inherited_comparison_min': problem['wait_ceiling'],
              'witness_found': False, 'policy_adopted': False}
    if fixed_peak_starts is not None:
        result['fixed_comparison_peak_starts_min'] = dict(fixed_peak_starts)
    bound = getattr(answer, 'mip_dual_bound', None)
    if bound is not None and np.isfinite(bound):
        result['annual_service_km_lower_bound_in_domain'] = round(float(bound) * 260, 6)
    if answer.x is None:
        return result
    if max(abs(answer.x - np.rint(answer.x))) > 1e-5:
        raise ValueError('fractional incumbent')
    n = len(problem['trips'])
    trips = ordered([t for i, t in enumerate(problem['trips']) if answer.x[i] > .5])
    phases = [{'peak': peak, 'start_min': start, 'end_min': start + 120}
              for i, (peak, start) in enumerate(PHASES) if answer.x[n + i] > .5]
    grid = verify(problem, trips, phases, fleet_bound)
    annual = sum(problem['family']['loops'][t['loop']]['distance_m'] for t in trips) * .26
    result.update(witness_found=True, trips=trips, comparison_peak_windows=phases,
                  daily_trip_count=len(trips), annual_service_km=round(annual, 6),
                  service_km_excess_vs_111419_reference=round(annual - 111419, 6),
                  continuous_grid_recheck_passed=True, nominal_fleet_recheck_passed=True,
                  frozen_rail_anchors_recheck_passed=True,
                  conditional_scenarios=grid,
                  worst_grid_vehicle_count_conditional=max(g['minimum_vehicle_count_conditional'] for g in grid))
    nominal = problem['adjusted'][1.1, .5]
    result['local_event_bindings_nominal'] = []
    for pattern, loop in nominal.items():
        for sid in LOCAL_SITES:
            events = [e for e in loop['events'] if e['stop_place_id'] == sid]
            if not events:
                continue
            first = min(events, key=lambda e: e['offset_from_wing_origin_min'])
            last = max(events, key=lambda e: e['offset_from_wing_origin_min'])
            result['local_event_bindings_nominal'].append({
                'pattern': pattern, 'stop_place_id': sid,
                'from_fs_alighting_occurrence_id': first['occurrence_id'],
                'to_fs_boarding_occurrence_id': last['occurrence_id'],
                'from_fs_ride_min': first['offset_from_wing_origin_min'] - .5,
                'to_fs_ride_min': loop['road_minutes'] - last['offset_from_wing_origin_min'],
                'boarding_authorised': False})
    return result


def document(cases):
    expected = {(f, h, k) for f in ('original_priority_direction', 'fast_local_both_directions')
                for h in (60, 90) for k in (4, 5)}
    return {'contract': 'RT031_LINE8_JOINT_EVENING_TIMETABLE_FLEET_COMPARISON_V3',
            'status': 'BOUNDED_JOINT_SEARCH_NOT_SELECTED', 'cases': cases,
            'all_requested_comparisons_completed': {
                (c['family_id'], c['offpeak_wait_comparison_min'], c['nominal_fleet_bound_comparison']) for c in cases} == expected,
            'expected_case_count': len(expected),
            'source_sha256_normalized_newlines': EXPECTED.copy(),
            'annual_service_days_assumption': 260, 'reference_cap_unchanged': 111419,
            'semantics': {
                'domain': 'Four frozen complete wing patterns; every five-minute departure from 06:00 to 20:40 eligible, no prescribed trip count or single direction switch. Positive-length continuous ready-time coverage 06:30-20:40. Full common 120-minute peaks chosen jointly on AM starts 06:30-07:00 and PM starts 16:30-17:00, five-minute grid.',
                'frequency': 'H60 and H90 are distinct comparisons, neither relaxation adopted. For Olgiate sud and San Zeno, to-FS coverage uses ONLY the last local occurrence before FS, not earlier passes followed by a long loop; from-FS riders use the earliest local alighting occurrence. Other sites use the optimistic union of occurrences. Not authorised boarding or guaranteed passenger-service continuity. All nine moving/dwell cases must satisfy the same windows.',
                'fleet': 'Fleet caps are comparisons, not operator commitments. Nominal +10% moving, 0.5 minute dwell and 10 minute recovery. All represented FS joins must be true; interval occupation is then verified with exact path cover. Other 26 timing/recovery cases reported, not constrained to the nominal fleet cap. Full-history and driver/depot certification absent.',
                'rail': 'Frozen 2026-09-03 only. Five AM targets 07:26..09:26 per wing must have a quick-local-direction arrival across the timing grid with >=3 minute transfer. Residual waiting ceiling is inherited from the worst baseline AM residual across wings/scenarios, an explicit engineering comparison not a normative approval. Seven PM/evening train arrivals retain a quick-local-direction bus 3-8 minutes later. Corrected loops allow either orientation because both have short local rides.',
                'objective': 'Minimum service km conditional on each declared nominal fleet bound and frequency comparison. No blended weights or selected winner. A time limit without a witness is NOT infeasibility; incumbents are checked independently. Finite-grid/domain bounds are NOT global road-network or continuous timetable bounds.',
                'cost': '260 assumed days, service km only. Longer span, wages, deadheading and depot costs unknown. Neither 111419 reference nor a numeric approved uplift is modified.'},
            **{k: False for k in FLAGS}, 'actual_timetable_certified': False,
            'decision_budget_km': None, 'uncertainty_band_min': None,
            'approved_uplift_percent': None, 'total_operating_km': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--time_limit', type=float, default=30)
    parser.add_argument('--output', type=Path, default=BASE / 'joint_evening_timetable.json')
    parser.add_argument('--families', nargs='+', choices=('original_priority_direction', 'fast_local_both_directions'))
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    sources = load_sources()
    # Evidence anchor check before solving; never infer trains from clock labels.
    rail = sources['rail']
    if not {446, 476, 506, 536, 566} <= {float(r['departure_min']) for r in rail if r['direction'] == 'MILANO'}:
        raise ValueError('missing AM rail anchors')
    if not {992, 1022, 1052, 1082, 1112, 1172, 1232} <= {float(r['arrival_min']) for r in rail if r['direction'] == 'LECCO'}:
        raise ValueError('missing PM rail anchors')
    families = family_inputs(sources)
    selected_families = args.families or [f['name'] for f in families]
    cases = []
    if args.resume:
        previous = json.loads(args.output.read_text(encoding='utf-8'))
        if previous['source_sha256_normalized_newlines'] != EXPECTED:
            raise ValueError('cannot resume different source evidence')
        for case in previous['cases']:
            if case['family_id'] in selected_families:
                continue
            family = next(f for f in families if f['name'] == case['family_id'])
            if case['witness_found']:
                verify(prepare(family, case['offpeak_wait_comparison_min'], False), case['trips'],
                       case['comparison_peak_windows'], case['nominal_fleet_bound_comparison'])
            cases.append(case)
    for family in families:
        if family['name'] not in selected_families:
            continue
        for offpeak in (90, 60):
            problem = prepare(family, offpeak)
            for fleet in (4, 5):
                case = solve(problem, fleet, args.time_limit)
                cases.append(case)
                args.output.write_text(json.dumps(document(cases), sort_keys=True, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
                print(json.dumps({k: v for k, v in case.items() if k not in ('trips', 'conditional_scenarios')}, ensure_ascii=False), flush=True)
