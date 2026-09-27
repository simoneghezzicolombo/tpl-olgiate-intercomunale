"""Exact cut-generation timetable comparison for the declared partial pool.

Every partial trip serves only its actual site occurrences. No hidden transfer
or full-wing train credit. Completion requires the independent full verifier.
"""
import argparse
from collections import Counter
import json
import time
import hashlib
from pathlib import Path

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csc_matrix

from scripts.phase2_probe_rt031_line8_partial_services_v3 import OUTPUT as POOL
from scripts.phase2_audit_rt031_line8_robustness_cost_v3 import digest
from scripts.phase2_compare_rt031_line8_evening_reallocation_v3 import BASE, FLAGS, EXPECTED, load_sources, ordered
from scripts.phase2_compare_rt031_line8_shorter_span_v3 import SPANS
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import (
    PHASES, family_inputs, prepare, verify, events_by_site, service_windows,
)
from scripts.phase2_audit_rt031_line8_passenger_peaks_v3 import uncovered_intervals
from scripts.phase2_solve_rt031_line8_flexible_peaks_v3 import interval_covers

OUTPUT = BASE / 'partial_services_timetable.json'


def missing_cuts(problem, selected_trips, phases, candidates, phase_scoped=False, lift_phases=False):
    """An uncovered ready-time midpoint gives a necessary covering constraint.

    The selected witness is checked continuously, not on a minute sample. A
    candidate at the right endpoint is eligible under the same <= wait rule.
    """
    cuts = set()
    for key, loops in problem['adjusted'].items():
        selected = events_by_site(selected_trips, loops)
        for site_direction, all_events in candidates[key].items():
            times = [t for _, t in selected.get(site_direction, [])]
            windows = [(*window, -1) for window in service_windows(problem)]
            windows.extend((p['start_min'], p['end_min'], 30, PHASES.index((p['peak'], p['start_min']))) for p in phases)
            for start, end, wait, phase_index in windows:
                for left, right in uncovered_intervals(times, start, end, wait):
                    midpoint = (left + right) / 2
                    indices = tuple(sorted({i for i, t in all_events if midpoint <= t <= midpoint + wait}))
                    if not indices:
                        raise ValueError('no candidate covers required ready time')
                    if phase_scoped and lift_phases and phase_index >= 0:
                        # This ready time must be covered under EVERY phase
                        # containing it, not just the phase of this incumbent.
                        cuts.update((indices, j) for j, (_, phase_start) in enumerate(PHASES)
                                    if phase_start <= midpoint < phase_start + 120)
                    else:
                        cuts.add((indices, phase_index) if phase_scoped else indices)
    return cuts


def cut_matrix(cuts, n, phase_scoped):
    """Merge identical covers only across mutually exclusive peak choices."""
    grouped = {}
    for cover in cuts:
        indices, phase = cover if phase_scoped else (cover, -1)
        grouped.setdefault(indices, set()).add(phase)
    rr, cc, values, lower = [], [], [], []
    for indices, phases in sorted(grouped.items()):
        groups = [()] if -1 in phases else [tuple(p for p in sorted(phases) if PHASES[p][0] == label)
                                           for label in ('AM', 'PM') if any(PHASES[p][0] == label for p in phases)]
        for active_phases in groups:
            row = len(lower)
            rr.extend([row] * len(indices)); cc.extend(indices); values.extend([1.] * len(indices))
            rr.extend([row] * len(active_phases)); cc.extend(n + p for p in active_phases)
            values.extend([-1.] * len(active_phases))
            lower.append(0. if active_phases else 1.)
    return csc_matrix((values, (rr, cc)), shape=(len(lower), n + len(PHASES))), np.array(lower)


def checkpoint_signature(problem, flexible_peaks, reference_phases):
    domain = {'family': problem['family'], 'trips': problem['trips'], 'grid': list(problem['adjusted']),
              'span': problem['ready_span'], 'offpeak': problem['offpeak_wait'], 'anchors': problem['anchors'],
              'wait_ceiling': problem['wait_ceiling'], 'fleet': 4, 'flexible': flexible_peaks,
              'phase_domain': PHASES if flexible_peaks else reference_phases}
    if service_windows(problem) != [(*problem['ready_span'], problem['offpeak_wait'])]:
        domain['offpeak_windows'] = service_windows(problem)
    return hashlib.sha256(json.dumps(domain, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def solve_lazy(problem, reference_case, time_limit=240, iteration_limit=60, flexible_peaks=False,
               checkpoint_path=None, strengthen=False):
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
    traces = []
    started, best_bound = time.monotonic(), 0.
    complete = False
    solver_slice = 45
    signature = checkpoint_signature(problem, flexible_peaks, phases)
    if checkpoint_path is not None and checkpoint_path.exists():
        saved = json.loads(checkpoint_path.read_text(encoding='utf-8'))
        if saved['domain_sha256'] != signature:
            raise ValueError('checkpoint domain mismatch')
        # Do not trust stored coefficient arrays: rebuild necessary cuts from
        # actual event opportunities and the saved diagnostic trip witnesses.
        traces = saved['relaxation_witnesses']
        for trace in traces:
            trace_phases = trace['phases']
            if (len(trace_phases) != 2 or {p['peak'] for p in trace_phases} != {'AM', 'PM'}
                    or any((p['peak'], p['start_min']) not in PHASES or p['end_min'] != p['start_min'] + 120
                           for p in trace_phases)):
                raise ValueError('checkpoint phase domain mismatch')
            if not flexible_peaks and {(p['peak'], p['start_min']) for p in trace_phases} != chosen:
                raise ValueError('checkpoint changes fixed peak phases')
            cuts.update(missing_cuts(problem, trace['trips'], trace['phases'], candidate_events,
                                     phase_scoped=flexible_peaks, lift_phases=strengthen))
            trace_cost = sum(problem['family']['loops'][t['loop']]['distance_m'] / 1000 for t in trace['trips'])
            if trace_cost < incumbent_cost - 1e-7:
                try:
                    verify(problem, trace['trips'], trace['phases'], 4)
                except ValueError:
                    pass  # A diagnostic relaxation is not an operating witness.
                else:
                    incumbent, phases, incumbent_cost = trace['trips'], trace['phases'], trace_cost
        print(json.dumps({'resumed_diagnostic_witnesses': len(traces), 'rebuilt_necessary_cuts': len(cuts)}), flush=True)
    if strengthen:
        # FS departures do not depend on running/dwell scenarios. Seed their
        # exact continuous cover for all sites and allowed phases once.
        first_events = next(iter(candidate_events.values()))
        for (sid, direction), events in first_events.items():
            if direction != 'from_fs':
                continue
            for start, end, wait in service_windows(problem):
                for cover in interval_covers(events, start, end, wait):
                    cuts.add((cover, -1) if flexible_peaks else cover)
            allowed = PHASES if flexible_peaks else [(p['peak'], p['start_min']) for p in phases]
            for phase in allowed:
                for cover in interval_covers(events, phase[1], phase[1] + 120, 30):
                    cuts.add((cover, PHASES.index(phase)) if flexible_peaks else cover)
    constraints[-1] = LinearConstraint(csc_matrix(problem['costs'].reshape(1, -1)), -np.inf, incumbent_cost + 1e-7)
    for iteration in range(iteration_limit):
        remaining = time_limit - (time.monotonic() - started)
        if remaining <= 0:
            break
        if cuts:
            matrix, cut_lower = cut_matrix(cuts, n, flexible_peaks)
            active = constraints + [LinearConstraint(matrix, cut_lower, np.full(len(cut_lower), np.inf))]
        else:
            active = constraints
        answer = milp(problem['costs'], integrality=np.ones(len(problem['costs'])),
                      bounds=Bounds(0, variable_upper), constraints=active,
                      options={'time_limit': min(remaining, solver_slice), 'mip_rel_gap': 0})
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
        new_cuts = missing_cuts(problem, trips, selected_phases, candidate_events,
                                phase_scoped=flexible_peaks, lift_phases=strengthen)
        traces.append({'trips': trips, 'phases': selected_phases})
        if checkpoint_path is not None:
            checkpoint_path.write_text(json.dumps({'domain_sha256': signature,
                                                   'relaxation_witnesses': traces}, separators=(',', ':')) + '\n', encoding='utf-8')
        log['violating_midpoint_cuts'] = len(new_cuts)
        log['relaxation_service_km'] = sum(problem['family']['loops'][t['loop']]['distance_m'] * .26 for t in trips)
        history.append(log)
        print(json.dumps(log), flush=True)
        if not new_cuts:
            verify(problem, trips, selected_phases, 4)
            incumbent = trips
            phases = selected_phases
            incumbent_cost = sum(problem['family']['loops'][t['loop']]['distance_m'] / 1000 for t in trips)
            constraints[-1] = LinearConstraint(csc_matrix(problem['costs'].reshape(1, -1)), -np.inf, incumbent_cost + 1e-7)
            complete = bool(answer.success)
            if complete:
                break
            # Once the witness is fully feasible, give the same MILP more time
            # to close its gap rather than repeatedly restarting a 45s search.
            solver_slice *= 2
            continue
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


def run(time_limit=240, flexible_peaks=False, checkpoint_path=None, strengthen=False):
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
    result = solve_lazy(problem, case, time_limit, flexible_peaks=flexible_peaks,
                        checkpoint_path=checkpoint_path, strengthen=strengthen)
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
    parser.add_argument('--strengthen', action='store_true')
    parser.add_argument('--checkpoint', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = run(args.time_limit, args.flexible_peaks, args.checkpoint, args.strengthen)
    output = args.output or (BASE / 'partial_services_flexible_peaks.json' if args.flexible_peaks else OUTPUT)
    output.write_text(json.dumps(result, sort_keys=True, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    print(json.dumps({k: result['case'][k] for k in ('annual_service_km', 'annual_service_km_lower_bound_in_domain',
                                                  'optimality_proven_in_this_domain', 'patterns_used')}), flush=True)
