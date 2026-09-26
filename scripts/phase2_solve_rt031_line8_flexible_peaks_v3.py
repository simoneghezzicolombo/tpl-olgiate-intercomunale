"""Joint peak-phase and trip search; an explicit comparison, never a selection."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csc_matrix

from scripts.phase2_audit_rt031_line8_dwell_sensitivity_v3 import adjusted_loops
from scripts.phase2_audit_rt031_line8_passenger_peaks_v3 import uncovered_intervals


def interval_covers(opportunities, lo, hi, wait):
    """Exact positive-length cells of the union of ready-time intervals.

    Counts, not a boolean active flag, retain overlapping occurrences per trip.
    """
    changes = defaultdict(Counter)
    changes[lo]; changes[hi]
    for i, time in opportunities:
        left, right = max(lo, time-wait), min(hi, time)
        if left < right:
            changes[left][i] += 1
            changes[right][i] -= 1
    active = Counter()
    result = set()
    points = sorted(changes)
    for j, point in enumerate(points[:-1]):
        active.update(changes[point])
        if points[j+1]-point > 1e-8:
            result.add(tuple(sorted(i for i, count in active.items() if count > 0)))
    return result


def build(wings, step=5, fixed_counts=False, per_wing_count=17, span_start=360, reference_cap=None, wing=None):
    if wings['contract'] != 'RT031_LINE8_INDEPENDENT_WINGS_DIAGNOSTIC_V3':
        raise ValueError('wrong source contract')
    if any(wings[k] for k in ('network_selected', 'primary_selection_authorised', 'runner_up_selection_authorised')):
        raise ValueError('decisional source')
    if step not in (1, 5):
        raise ValueError('unsupported grid')
    if not 360 <= span_start <= 390 or per_wing_count < 1:
        raise ValueError('unsupported service domain')
    loops = adjusted_loops(wings['loops'], 1.1, .5)
    if wing is not None:
        if wing not in ('west', 'east'):
            raise ValueError('unknown wing')
        loops = {k:v for k,v in loops.items() if k.startswith(wing)}
    trips = [{'loop': k, 'departure_min': m} for k in sorted(loops) for m in range(360, 1201, step)]
    opportunities = defaultdict(list)
    for i, t in enumerate(trips):
        for e in loops[t['loop']]['events']:
            opportunities[e['stop_place_id'], 'to_fs'].append((i, t['departure_min']+e['offset_from_wing_origin_min']))
            opportunities[e['stop_place_id'], 'from_fs'].append((i, t['departure_min']))
    phases = [('AM', m) for m in range(390, 421, step)] + [('PM', m) for m in range(990, 1021, step)]
    n = len(trips)
    unique_rows = set()
    for events in opportunities.values():
        for cover in interval_covers(events, span_start, 1140, 60):
            unique_rows.add((cover, -1))
        for phase, (_, start) in enumerate(phases):
            for cover in interval_covers(events, start, start+120, 30):
                unique_rows.add((cover, n+phase))
    rows, cols, values, lower, upper = [], [], [], [], []
    for cover, phase in sorted(unique_rows):
        row = len(lower)
        for i in cover:
            rows.append(row); cols.append(i); values.append(1.)
        if phase != -1:
            rows.append(row); cols.append(phase); values.append(-1.)
        lower.append(1. if phase == -1 else 0.)
        upper.append(np.inf)
    for peak in ('AM', 'PM'):
        row = len(lower)
        for j, (label, _) in enumerate(phases):
            if label == peak:
                rows.append(row); cols.append(n+j); values.append(1.)
        lower.append(1.); upper.append(1.)
    if fixed_counts:
        for tested_wing in sorted({k.split('_')[0] for k in loops}):
            row = len(lower)
            for i, t in enumerate(trips):
                if t['loop'].startswith(tested_wing):
                    rows.append(row); cols.append(i); values.append(1.)
            lower.append(0.); upper.append(float(per_wing_count))
    matrix = csc_matrix((values, (rows, cols)), shape=(len(lower), n+len(phases)))
    costs = np.array([loops[t['loop']]['distance_m']/1000 for t in trips] + [0.]*len(phases))
    constraints = [LinearConstraint(matrix, lower, upper)]
    if reference_cap is not None:
        constraints.append(LinearConstraint(csc_matrix(costs.reshape(1, -1)), -np.inf, reference_cap/260))
    answer = milp(costs, integrality=np.ones(len(costs)), bounds=Bounds(0, 1),
                  constraints=constraints,
                  options={'time_limit': 120, 'mip_rel_gap': 0})
    result = {'contract': 'RT031_LINE8_JOINT_FLEXIBLE_PEAK_COMPARISON_V3',
        'departure_grid_min': step, 'candidate_trip_count': n, 'constraint_count': len(lower),
        'phase_domain': {'AM_start_min': [390, 420], 'PM_start_min': [990, 1020], 'step_min': step, 'duration_min': 120},
        'ready_span_min': [span_start, 1140], 'max_wait_outside_peaks_min': 60,
        'maximum_trip_count_each_wing': per_wing_count if fixed_counts else None, 'solver_status': int(answer.status),
        'wing_relaxation': wing,
        'reference_service_km_cap_if_tested': reference_cap,
        'solver_message': str(answer.message), 'scope': 'All four fixed complete wing patterns, optimistic identity union, 260 assumed days, moving multiplier 1.1 and dwell 0.5 min. Peak phases independent and jointly searched. Not a continuous departure-time or street-path optimum; no train or fleet objective.',
        'network_selected': False, 'primary_selection_authorised': False, 'runner_up_selection_authorised': False,
        'decision_budget_km': None, 'uncertainty_band_min': None}
    if answer.status == 2:
        result['infeasibility_proven_in_declared_finite_domain'] = True
        return result
    result['optimality_proven'] = bool(answer.success)
    if getattr(answer, 'mip_dual_bound', None) is not None:
        result['annual_objective_lower_bound_km'] = float(answer.mip_dual_bound)*260
    if answer.x is None:
        result['infeasibility_proven_in_declared_finite_domain'] = False
        result['optimality_proven'] = False
        return result
    selected = {i for i in range(n) if answer.x[i] > .5}
    selected_phases = [{'peak': label, 'start_min': start, 'end_min': start+120}
                       for j, (label, start) in enumerate(phases) if answer.x[n+j] > .5]
    for events in opportunities.values():
        times = [time for i, time in events if i in selected]
        if uncovered_intervals(times, span_start, 1140, 60):
            raise ValueError('H60 continuous postsolve failure')
        for p in selected_phases:
            if uncovered_intervals(times, p['start_min'], p['end_min'], 30):
                raise ValueError('H30 continuous postsolve failure')
    daily = sum(costs[i] for i in selected)
    result.update(continuous_recheck_passed=True,
        peak_windows=selected_phases, daily_km=round(daily, 9), annual_service_km=round(daily*260, 6),
        trip_counts=dict(Counter(trips[i]['loop'] for i in selected)),
        trips=sorted((trips[i] for i in selected), key=lambda t:(t['departure_min'], t['loop'])))
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--source', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--step', type=int, default=5)
    p.add_argument('--fixed_counts', action='store_true')
    p.add_argument('--per_wing_count', type=int, default=17)
    p.add_argument('--span_start', type=int, default=360)
    p.add_argument('--policy', type=Path)
    p.add_argument('--wing', choices=('west','east'))
    a = p.parse_args()
    cap = None
    if a.policy:
        policy = json.loads(a.policy.read_text(encoding='utf-8'))
        if policy['contract'] != 'PHASE2_HUMAN_APPROVED_FINAL_POLICY_V3':
            raise ValueError('wrong budget source')
        cap = policy['human_policy_decisions']['annual_bus_km_cap']
    result = build(json.loads(a.source.read_text(encoding='utf-8')), a.step, a.fixed_counts, a.per_wing_count, a.span_start, cap, a.wing)
    result['source_sha256'] = hashlib.sha256(a.source.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
    a.output.write_text(json.dumps(result, sort_keys=True, ensure_ascii=False, separators=(',', ':'))+'\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k != 'trips'}, ensure_ascii=False))
