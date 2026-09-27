"""Exact cut-generation timetable comparison for the declared partial pool.

Every partial trip serves only its actual site occurrences. No hidden transfer
or full-wing train credit. Completion requires the independent full verifier.
"""
import argparse
from collections import Counter
import json
import time

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csc_matrix

from scripts.phase2_probe_rt031_line8_partial_services_v3 import OUTPUT as POOL
from scripts.phase2_audit_rt031_line8_robustness_cost_v3 import digest
from scripts.phase2_compare_rt031_line8_evening_reallocation_v3 import BASE, FLAGS, EXPECTED, load_sources, ordered
from scripts.phase2_compare_rt031_line8_shorter_span_v3 import SPANS
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import (
    PHASES, family_inputs, prepare, verify, events_by_site,
)
from scripts.phase2_audit_rt031_line8_passenger_peaks_v3 import uncovered_intervals

OUTPUT = BASE / 'partial_services_timetable.json'


def missing_cuts(problem, selected_trips, phases, candidates, phase_scoped=False):
    """An uncovered ready-time midpoint gives a necessary covering constraint.

    The selected witness is checked continuously, not on a minute sample. A
    candidate at the right endpoint is eligible under the same <= wait rule.
    """
    cuts = set()
    for key, loops in problem['adjusted'].items():
        selected = events_by_site(selected_trips, loops)
        for site_direction, all_events in candidates[key].items():
            times = [t for _, t in selected.get(site_direction, [])]
            windows = [(*problem['ready_span'], problem['offpeak_wait'], -1)]
            windows.extend((p['start_min'], p['end_min'], 30, PHASES.index((p['peak'], p['start_min']))) for p in phases)
            for start, end, wait, phase_index in windows:
                for left, right in uncovered_intervals(times, start, end, wait):
                    midpoint = (left + right) / 2
                    indices = tuple(sorted({i for i, t in all_events if midpoint <= t <= midpoint + wait}))
                    if not indices:
                        raise ValueError('no candidate covers required ready time')
                    cuts.add((indices, phase_index) if phase_scoped else indices)
    return cuts


def solve_lazy(problem, reference_case, time_limit=240, iteration_limit=60, flexible_peaks=False):
    phases = reference_case['comparison_peak_windows']
    # The original full-pattern solution remains an independently verified
    # incumbent. A timeout never loses it or becomes a false infeasibility.
    incumbent = reference_case['trips']
    verify(problem, incumbent, phases, 4)
    incumbent_cost = sum(problem['family']['loops'][t['loop']]['distance_m'] / 1000 for t in incumbent)
    candidate_events = {key: events_by_site(problem['trips'], loops) for key, loops in problem['adjusted'].items()}
    upper = problem['upper'].copy()
    upper[problem['fleet_rows']] = 4
    n = len(problem['trips'])
    variable_upper = np.ones(len(problem['costs']))
    chosen = {(p['peak'], p['start_min']) for p in phases}
    for i, phase in enumerate(PHASES):
        if not flexible_peaks and phase not in chosen:
            variable_upper[n + i] = 0
    constraints = [LinearConstraint(problem['matrix'], problem['lower'], upper),
                   LinearConstraint(csc_matrix(problem['costs'].reshape(1, -1)), -np.inf, incumbent_cost + 1e-7)]
    cuts, history = set(), []
    started, best_bound = time.monotonic(), 0.
    complete = False
    for iteration in range(iteration_limit):
        remaining = time_limit - (time.monotonic() - started)
        if remaining <= 0:
            break
        if cuts:
            rr, cc, values, cut_lower = [], [], [], []
            for row, cover in enumerate(sorted(cuts)):
                indices, phase_index = cover if flexible_peaks else (cover, -1)
                rr.extend([row] * len(indices)); cc.extend(indices); values.extend([1.] * len(indices))
                if phase_index >= 0:
                    rr.append(row); cc.append(n + phase_index); values.append(-1.)
                cut_lower.append(0. if phase_index >= 0 else 1.)
            matrix = csc_matrix((values, (rr, cc)), shape=(len(cuts), n + len(PHASES)))
            active = constraints + [LinearConstraint(matrix, cut_lower, np.full(len(cuts), np.inf))]
        else:
            active = constraints
        answer = milp(problem['costs'], integrality=np.ones(len(problem['costs'])),
                      bounds=Bounds(0, variable_upper), constraints=active,
                      options={'time_limit': min(remaining, 45), 'mip_rel_gap': 0})
        bound = getattr(answer, 'mip_dual_bound', None)
        if bound is not None and np.isfinite(bound):
            best_bound = max(best_bound, float(bound))
        if answer.status == 2 or best_bound > incumbent_cost + 1e-5:
            raise ValueError('relaxation contradicts independently verified incumbent')
        log = {'iteration': iteration, 'solver_status': int(answer.status), 'cuts_before': len(cuts),
               'annual_lower_bound': best_bound * 260}
        if best_bound >= incumbent_cost - 1e-7:
            # The known full-route witness is feasible for every generated and
            # ungenerated constraint. A matching relaxed bound already proves it.
            complete = True
            log['closure_by_bound_matching_verified_incumbent'] = True
            history.append(log)
            print(json.dumps(log), flush=True)
            break
        if answer.x is None:
            history.append(log)
            break
        if max(abs(answer.x - np.rint(answer.x))) > 1e-5:
            raise ValueError('fractional partial-service incumbent')
        trips = ordered([t for i, t in enumerate(problem['trips']) if answer.x[i] > .5])
        selected_phases = [{'peak': label, 'start_min': start, 'end_min': start + 120}
                           for i, (label, start) in enumerate(PHASES) if answer.x[n + i] > .5]
        new_cuts = missing_cuts(problem, trips, selected_phases, candidate_events, phase_scoped=flexible_peaks)
        log['violating_midpoint_cuts'] = len(new_cuts)
        log['relaxation_service_km'] = sum(problem['family']['loops'][t['loop']]['distance_m'] * .26 for t in trips)
        history.append(log)
        print(json.dumps(log), flush=True)
        if not new_cuts:
            verify(problem, trips, selected_phases, 4)
            incumbent = trips
            phases = selected_phases
            complete = bool(answer.success)
            break
        if not new_cuts - cuts:
            raise ValueError('violations persist despite their exact covering cuts')
        cuts.update(new_cuts)
    scenarios = verify(problem, incumbent, phases, 4)
    annual = sum(problem['family']['loops'][t['loop']]['distance_m'] * .26 for t in incumbent)
    complete = complete or abs(best_bound * 260 - annual) <= 1e-5
    return {'trips': incumbent, 'annual_service_km': annual, 'daily_trip_count': len(incumbent),
            'patterns_used': dict(Counter(t['loop'] for t in incumbent)),
            'annual_service_km_lower_bound_in_domain': best_bound * 260,
            'optimality_proven_in_this_domain': complete,
            'witness_found': True, 'continuous_grid_recheck_passed': True,
            'frozen_per_site_rail_anchors_recheck_passed': True,
            'comparison_peak_windows': phases, 'conditional_scenarios': scenarios,
            'worst_grid_vehicle_count_conditional': max(s['minimum_vehicle_count_conditional'] for s in scenarios),
            'reference_annual_service_km': reference_case['annual_service_km'],
            'saved_service_km_vs_reference': reference_case['annual_service_km'] - annual,
            'cut_generation_history': history, 'elapsed_s': time.monotonic() - started,
            'policy_adopted': False, 'candidate_trip_count': len(problem['trips']),
            'flexible_peak_phases': flexible_peaks}


def run(time_limit=240, flexible_peaks=False):
    pool = json.loads(POOL.read_text(encoding='utf-8'))
    if any(pool[k] for k in FLAGS) or pool['source_sha256_normalized_newlines'] != EXPECTED:
        raise ValueError('pool source drift or selection')
    reference_path = BASE / 'shorter_span_comparison.json'
    reference = json.loads(reference_path.read_text(encoding='utf-8'))
    baseline = next(f for f in family_inputs(load_sources()) if f['name'] == 'fast_local_both_directions')
    if any(pool['family']['loops'][p] != loop for p, loop in baseline['loops'].items()):
        raise ValueError('full-pattern reference drift')
    span = SPANS['last_fs_1940']
    kwargs = dict(ready_span=(390, span['end_min']), pm_arrivals=span['pm_arrivals'])
    ref_problem = prepare(baseline, 60, False, **kwargs)
    case = next(c for c in reference['cases'] if c['span_comparison_id'] == 'last_fs_1940' and c['offpeak_wait_comparison_min'] == 60)
    verify(ref_problem, case['trips'], case['comparison_peak_windows'], 4)
    problem = prepare(pool['family'], 60, False, **kwargs,
                      am_wait_ceiling_comparison_min=ref_problem['wait_ceiling'])
    print(json.dumps({'candidate_trip_count': len(problem['trips']), 'pattern_count': len(pool['family']['loops']),
                      'per_site_rail_anchors': len(problem['anchors'])}), flush=True)
    result = solve_lazy(problem, case, time_limit, flexible_peaks=flexible_peaks)
    return {'contract': 'RT031_LINE8_PARTIAL_SERVICE_TIMETABLE_COMPARISON_V3', 'case': result,
            'source_sha256_normalized_newlines': {'pool': digest(POOL), 'reference': digest(reference_path)},
            'semantics': 'Full retention of all 28 site identities; H30/H60 in both passenger directions across all nine timing scenarios, ready span 06:30-19:40. Peak-phase scope explicit in case: fixed reference or all 49 AM/PM combinations on inherited five-minute domain. Four nominal vehicles, 260 identical days and frozen rail only. Every original wing site must have a direct single-trip train opportunity, not just one site per wing. No transfer between partial trips inferred. Necessary constraints generated at uncovered ready-time midpoints, conditional on the tested phase when flexible. An optimum is proven only when a full-verified witness matches the relaxed lower bound. A timeout preserves the verified full-route incumbent and valid lower bound; not an impossibility claim.',
            **{k: False for k in FLAGS}, 'actual_timetable_certified': False,
            'decision_budget_km': None, 'uncertainty_band_min': None,
            'approved_uplift_percent': None, 'total_operating_km': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--time_limit', type=float, default=240)
    parser.add_argument('--flexible_peaks', action='store_true')
    args = parser.parse_args()
    result = run(args.time_limit, args.flexible_peaks)
    output = BASE / 'partial_services_flexible_peaks.json' if args.flexible_peaks else OUTPUT
    output.write_text(json.dumps(result, sort_keys=True, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    print(json.dumps({k: result['case'][k] for k in ('annual_service_km', 'annual_service_km_lower_bound_in_domain',
                                                  'optimality_proven_in_this_domain', 'patterns_used')}), flush=True)
