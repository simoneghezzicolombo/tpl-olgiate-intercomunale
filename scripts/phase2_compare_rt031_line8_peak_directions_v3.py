"""Enumerate rail-linked directions, without a weighted or political winner."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
from scipy.sparse import csc_matrix, vstack

from scripts.phase2_compare_rt031_line8_evening_reallocation_v3 import BASE, EXPECTED, FLAGS, load_sources
from scripts.phase2_compare_rt031_line8_shorter_span_v3 import SPANS, validate_rail
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import family_inputs, prepare, solve, verify

PEAKS = {'AM': 410, 'PM': 995}
PAIRS = tuple(itertools.product(('west_A', 'west_B'), ('east_A', 'east_B')))
POLICIES = {f'{am[0][-1]}{am[1][-1]}_{pm[0][-1]}{pm[1][-1]}':
            {'AM': dict(zip(('west', 'east'), am)), 'PM': dict(zip(('west', 'east'), pm))}
            for am, pm in itertools.product(PAIRS, repeat=2)}
OUTPUT = BASE / 'peak_direction_comparison.json'
REFERENCE = BASE / 'shorter_span_comparison.json'


def constrain_anchors(problem, policy):
    """Require a pattern on each train-linked run, not on all daytime runs."""
    if policy not in POLICIES.values():
        raise ValueError('unsupported direction policy')
    anchors, rows, cols = [], [], []
    for row, anchor in enumerate(problem['anchors']):
        phase = 'AM' if anchor['kind'] == 'bus_to_rail' else 'PM'
        pattern = policy[phase][anchor['wing']]
        eligible = tuple(i for i in anchor['eligible'] if problem['trips'][i]['loop'] == pattern)
        if not eligible:
            raise ValueError('empty direction-constrained rail anchor')
        anchors.append({**anchor, 'eligible': eligible, 'required_pattern': pattern})
        rows.extend([row] * len(eligible)); cols.extend(eligible)
    extra = csc_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(anchors), len(problem['costs'])))
    return {**problem, 'anchors': anchors,
            'matrix': vstack((problem['matrix'], extra), format='csc'),
            'lower': np.concatenate((problem['lower'], np.ones(len(anchors)))),
            'upper': np.concatenate((problem['upper'], np.full(len(anchors), np.inf)))}


def ride_profiles(family):
    from scripts.phase2_audit_rt031_line8_dwell_sensitivity_v3 import adjusted_loops
    loops = adjusted_loops(family['loops'], 1.1, .5)
    profiles = {}
    for pattern, loop in loops.items():
        rows = []
        for sid in sorted({e['stop_place_id'] for e in loop['events']}):
            events = [e for e in loop['events'] if e['stop_place_id'] == sid]
            first = min(events, key=lambda e: e['offset_from_wing_origin_min'])
            last = max(events, key=lambda e: e['offset_from_wing_origin_min'])
            rows.append({'stop_place_id': sid, 'name': first['name'],
                         'from_fs_ride_min': first['offset_from_wing_origin_min'] - .5,
                         'to_fs_ride_min': loop['road_minutes'] - last['offset_from_wing_origin_min'],
                         'from_fs_alighting_occurrence_id': first['occurrence_id'],
                         'to_fs_boarding_occurrence_id': last['occurrence_id'],
                         'boarding_authorised': False, 'passenger_continuity_certified': False})
        profiles[pattern] = {'distance_km': loop['distance_m'] / 1000, 'sites': rows}
    return profiles


def vector(profiles, policy):
    """One nominal ride value per site and peak; no passenger weights."""
    result = {}
    for phase, field in (('AM', 'to_fs_ride_min'), ('PM', 'from_fs_ride_min')):
        for pattern in policy[phase].values():
            for row in profiles[pattern]['sites']:
                key = phase + '|' + row['stop_place_id']
                if key in result:
                    raise ValueError('ambiguous multi-wing site')
                result[key] = row[field]
    if len(result) != 54:
        raise ValueError('missing peak/site journey dimensions')
    return result


def bindings(problem, case):
    indices = {(t['loop'], t['departure_min']): i for i, t in enumerate(problem['trips'])}
    selected = {indices[t['loop'], t['departure_min']] for t in case['trips']}
    return [{k: anchor[k] for k in ('wing', 'kind', 'rail_min', 'required_pattern')} |
            {'qualifying_dispatches': [problem['trips'][i] for i in sorted(selected.intersection(anchor['eligible']))]}
            for anchor in problem['anchors']]


def preserve_reference_tie(problem, case):
    """Do not turn a solver tie with more stress vehicles into a new lower bound."""
    raw = REFERENCE.read_bytes().replace(b'\r\n', b'\n')
    reference = json.loads(raw)
    if reference['contract'] != 'RT031_LINE8_SHORTER_SPAN_JOINT_COMPARISON_V3' or any(reference[k] for k in FLAGS):
        raise ValueError('invalid reference comparison')
    old = next(c for c in reference['cases'] if c['span_comparison_id'] == 'last_fs_1940'
               and c['offpeak_wait_comparison_min'] == 90)
    if {p['peak']: p['start_min'] for p in old['comparison_peak_windows']} != PEAKS:
        raise ValueError('reference peaks changed')
    grid = verify(problem, old['trips'], old['comparison_peak_windows'], 4)
    cost = sum(problem['family']['loops'][t['loop']]['distance_m'] for t in old['trips']) * .26
    if abs(cost - case['annual_service_km']) > 1e-5:
        raise ValueError('reference is not a same-cost witness')
    return {'source': REFERENCE.name, 'source_sha256_normalized_newlines': hashlib.sha256(raw).hexdigest(),
            'span_comparison_id': 'last_fs_1940', 'offpeak_wait_comparison_min': 90,
            'annual_service_km': round(cost, 6), 'trips': old['trips'],
            'comparison_peak_windows': old['comparison_peak_windows'],
            'worst_grid_vehicle_count_conditional': max(g['minimum_vehicle_count_conditional'] for g in grid),
            'semantics': 'Independent recheck of existing equal-km witness under the new direction anchors. Solver tie fleet is not a minimum stress-fleet proof.'}


def document(cases, profiles):
    expected = {(h, p) for h in (60, 90) for p in POLICIES}
    keys = {(c['offpeak_wait_comparison_min'], c['direction_policy_id']) for c in cases}
    return {'contract': 'RT031_LINE8_PEAK_DIRECTION_COMPARISON_V3',
            'status': 'FINITE_DIRECTION_COMPARISONS_NOT_SELECTED',
            'all_cases_attempted': keys == expected and len(cases) == len(expected),
            'all_cases_proven_optimal': keys == expected and len(cases) == len(expected) and all(c['optimality_proven_in_this_domain'] for c in cases),
            'source_sha256_normalized_newlines': EXPECTED,
            'policies': POLICIES, 'nominal_ride_profiles': profiles,
            'nominal_peak_site_vectors': {p: vector(profiles, spec) for p, spec in POLICIES.items()},
            'fixed_comparison_peak_starts_min': PEAKS,
            'ready_span_comparison_min': [390, 1180],
            'reference_pm_targets_not_retained_min': [1232],
            'cases': cases, 'annual_service_days_assumption': 260,
            'semantics': {
                'scope': 'All 16 AM/PM west/east direction assignments on the four frozen corrected road patterns. Each retained train anchor must have a qualifying run of the assigned direction; other coverage runs may use either direction. This is not a fixed whole-day direction-switch timetable.',
                'quality': '54 separate nominal on-board ride dimensions: each of 27 nonhub sites to FS on the AM anchored pattern, from FS on the PM anchored pattern. Occurrences remain explicit. Excludes walking, waiting and rail residual wait; no empirical reliability or demand weighting. A direction cannot be chosen for every site independently on the same trip.',
                'service': 'H30 common ready-time windows 06:50-08:50 and 16:35-18:35, all nine timing scenarios. H60 requested and H90 unapproved comparison kept separate. Fast last local boarding occurrences unchanged. All 28 site identities retained, not authorised platforms.',
                'rail': 'Frozen 2026-09-03 targets only: five AM 07:26-09:26 and six PM through 19:32. Compared ready span ends 19:40, excludes original 20:32 target. Not current rail or approved peak phases.',
                'resources': 'Minimum service km conditional on each assignment, four nominal vehicles and five-minute dispatch grid. Stress fleet reported separately. Extra direction constraints cannot lower the unrestricted optimum; lower km are not promised. Timeout is not infeasibility; no global road-network optimum.',
                'policy': 'No selected direction, normative ride threshold, budget uplift or off-peak relaxation. Comparisons do not close the proposal.'},
            **{k: False for k in FLAGS}, 'actual_timetable_certified': False,
            'decision_budget_km': None, 'uncertainty_band_min': None,
            'approved_uplift_percent': None, 'total_operating_km': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--time_limit', type=float, default=15)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    sources = load_sources(); validate_rail(sources)
    family = next(f for f in family_inputs(sources) if f['name'] == 'fast_local_both_directions')
    profiles = ride_profiles(family)
    previous = json.loads(OUTPUT.read_text(encoding='utf-8')) if args.resume else None
    if previous and (previous['source_sha256_normalized_newlines'] != EXPECTED or previous['policies'] != POLICIES
                     or previous['fixed_comparison_peak_starts_min'] != PEAKS or any(previous[k] for k in FLAGS)):
        raise ValueError('resume contract drift')
    cases = []
    for headway in (60, 90):
        base = prepare(family, headway, ready_span=(390, 1180), pm_arrivals=SPANS['last_fs_1940']['pm_arrivals'])
        for policy_id, policy in POLICIES.items():
            problem = constrain_anchors(base, policy)
            old = next((c for c in previous['cases'] if c['direction_policy_id'] == policy_id
                        and c['offpeak_wait_comparison_min'] == headway and c['optimality_proven_in_this_domain']), None) if previous else None
            if old:
                verify(problem, old['trips'], old['comparison_peak_windows'], 4)
                case = old
            else:
                case = solve(problem, 4, args.time_limit, fixed_peak_starts=PEAKS)
                case['direction_policy_id'] = policy_id
                case['rail_anchor_pattern_comparison'] = policy
                if case['witness_found']:
                    case['rail_anchor_dispatch_bindings'] = bindings(problem, case)
            if (headway, policy_id) == (90, 'BA_BA') and case['witness_found']:
                case['same_cost_verified_reference_witness'] = preserve_reference_tie(problem, case)
            cases.append(case)
            OUTPUT.write_text(json.dumps(document(cases, profiles), ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n', encoding='utf-8')
            print(json.dumps({k: case.get(k) for k in ('direction_policy_id', 'offpeak_wait_comparison_min', 'solver_status', 'annual_service_km', 'annual_service_km_lower_bound_in_domain', 'worst_grid_vehicle_count_conditional')}), flush=True)
