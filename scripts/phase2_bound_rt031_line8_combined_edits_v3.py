"""Independent-wing optimistic lower bounds for all combined relocation edits.

Zero dwell makes an added stop's position irrelevant to this relaxation. Only
the two protected local journeys and declared rail anchors are required here;
all other service and all fleet constraints are dropped, never strengthened.
"""
import json
from pathlib import Path

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csc_matrix

from scripts.phase2_probe_rt031_line8_stop_relocation_v3 import BASE, OUTPUT as SCREEN, RETENTION, FS, VIRTUAL, NORTH
from scripts.phase2_check_rt031_line8_relocation_timetable_v3 import sha, PEAKS
from scripts.phase2_compare_rt031_line8_evening_reallocation_v3 import FLAGS, load_sources
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import family_inputs, prepare, events_by_site
from scripts.phase2_solve_rt031_line8_flexible_peaks_v3 import interval_covers
from scripts.phase2_audit_rt031_line8_dwell_sensitivity_v3 import adjusted_loops
from scripts.phase2_audit_rt031_line8_passenger_peaks_v3 import uncovered_intervals
from scripts.phase2_compare_rt031_line8_shorter_span_v3 import SPANS

OUTPUT = BASE / 'combined_edits_lower_bounds.json'


def relaxed_problem(variant, wing, wait_ceiling, grid=((.9, 0.),)):
    local = VIRTUAL if wing == 'west' else NORTH
    raw = variant['loops']
    if set(raw) != {wing + '_A', wing + '_B'}:
        raise ValueError('wrong wing patterns')
    if any(local not in {e['stop_place_id'] for e in loop['events']} for loop in raw.values()):
        raise ValueError('required local anchor absent')
    adjusted = {key: adjusted_loops(raw, *key) for key in grid}
    loops = next(iter(adjusted.values()))
    trips = [{'loop': p, 'departure_min': t} for p in sorted(raw) for t in range(360, 1181, 5)]
    covers = set()
    for scenario in adjusted.values():
        for (sid, direction), events in events_by_site(trips, scenario).items():
            if sid != local:
                continue
            covers.update(interval_covers(events, 390, 1180, 60))
            for start in PEAKS.values():
                covers.update(interval_covers(events, start, start + 120, 30))
    anchors = []
    for rail in (446, 476, 506, 536, 566):
        anchors.append(tuple(i for i, t in enumerate(trips)
                             if all(-1e-8 <= rail - t['departure_min'] - scenario[t['loop']]['road_minutes'] - 3 <= wait_ceiling + 1e-8 for scenario in adjusted.values())))
    for rail in SPANS['last_fs_1940']['pm_arrivals']:
        anchors.append(tuple(i for i, t in enumerate(trips) if 3 <= t['departure_min'] - rail <= 8))
    if any(not a for a in anchors):
        raise ValueError('empty anchor in relaxed domain')
    covers.update(anchors)
    rows, cols = [], []
    for r, cover in enumerate(sorted(covers)):
        rows.extend([r] * len(cover)); cols.extend(cover)
    matrix = csc_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(covers), len(trips)))
    return {'trips': trips, 'loops': loops, 'adjusted': adjusted, 'anchors': anchors, 'local': local, 'matrix': matrix,
            'costs': np.array([raw[t['loop']]['distance_m'] / 1000 for t in trips])}


def verify_relaxed(problem, trips):
    index = {(t['loop'], t['departure_min']): i for i, t in enumerate(problem['trips'])}
    used = {index[t['loop'], t['departure_min']] for t in trips}
    if len(used) != len(trips) or any(not used.intersection(a) for a in problem['anchors']):
        raise ValueError('relaxed anchor verification failed')
    for scenario in problem['adjusted'].values():
        for (sid, direction), events in events_by_site(trips, scenario).items():
            if sid != problem['local']:
                continue
            times = [t for _, t in events]
            if uncovered_intervals(times, 390, 1180, 60) or any(uncovered_intervals(times, s, s + 120, 30) for s in PEAKS.values()):
                raise ValueError('relaxed frequency verification failed')


def solve_bound(variant, wing, ceiling, grid=((.9, 0.),)):
    p = relaxed_problem(variant, wing, ceiling, grid)
    a = milp(p['costs'], integrality=np.ones(len(p['trips'])), bounds=Bounds(0, 1),
             constraints=LinearConstraint(p['matrix'], 1, np.inf), options={'time_limit': 20, 'mip_rel_gap': 0})
    result = {'variant_id': variant['variant_id'], 'wing': wing, 'solver_status': int(a.status),
              'optimality_proven_in_relaxed_domain': bool(a.success), 'operating_timetable': False}
    bound = getattr(a, 'mip_dual_bound', None)
    if bound is not None and np.isfinite(bound):
        result['annual_service_km_lower_bound'] = round(float(bound) * 260, 6)
    if a.x is not None:
        if max(abs(a.x - np.rint(a.x))) > 1e-5:
            raise ValueError('fractional relaxed incumbent')
        trips = [t for i, t in enumerate(p['trips']) if a.x[i] > .5]
        verify_relaxed(p, trips)
        result['relaxed_dispatches_not_timetable'] = trips
        result['relaxed_trip_count'] = len(trips)
        result['relaxed_incumbent_annual_service_km'] = round(sum(p['loops'][t['loop']]['distance_m'] for t in trips) * .26, 6)
    return result


def summarize(cases, retention, screen, ceiling):
    lookup = {c['variant_id']: c for c in cases}
    pairs = []
    for west in retention['variants']['west']:
        for east in retention['variants']['east']:
            a, b = lookup.get(west['variant_id']), lookup.get(east['variant_id'])
            if not a or not b or 'annual_service_km_lower_bound' not in a or 'annual_service_km_lower_bound' not in b:
                continue
            value = a['annual_service_km_lower_bound'] + b['annual_service_km_lower_bound']
            pairs.append({'west_variant_id': west['variant_id'], 'east_variant_id': east['variant_id'],
                          'annual_service_km_lower_bound': round(value, 6),
                          'reference_cap_excluded_in_this_pair_domain': value > 111419 + 1e-5})
    complete = len(pairs) == 616
    return {'contract': 'RT031_LINE8_COMBINED_EDIT_OPTIMISTIC_BOUNDS_V3',
            'status': 'OPTIMISTIC_LOWER_BOUNDS_NOT_OPERATING_TIMETABLES',
            'source_sha256_normalized_newlines': {'screen': sha(SCREEN), 'retention': sha(RETENTION)},
            'wing_relaxations': cases, 'road_variant_pairs': pairs,
            'road_variant_pair_count': len(pairs),
            'relocation_choice_pair_count': (1 + sum(c['wing'] == 'west' for c in screen['cases'])) * (1 + sum(c['wing'] == 'east' for c in screen['cases'])),
            'all_road_pairs_bounded': complete,
            'all_reference_cap_excluded': complete and all(p['reference_cap_excluded_in_this_pair_domain'] for p in pairs),
            'minimum_lower_bound': min((p['annual_service_km_lower_bound'] for p in pairs), default=None),
            'fixed_comparison_peak_starts_min': PEAKS, 'ready_span_comparison_min': [390, 1180],
            'frozen_reference_am_wait_ceiling_comparison_min': ceiling,
            'reference_cap_unchanged': 111419,
            'semantics': 'Every road-variant pair, including no edit, is covered by the sum of independent wing lower bounds. Each wing requires only its unique protected local site H30 in the common peaks/H60 elsewhere and frozen AM/PM rail anchors in the mandatory .9 moving/zero-dwell scenario. Other sites, eight timing scenarios, recovery and all fleet limits are dropped. Added bypass stops have zero dwell in this scenario, hence their positions cannot invalidate the lower bound. Not a feasible bus service, not empirical reliability, not a global road network or different-calendar impossibility proof. No coverage losses or budget uplift accepted.',
            **{k: False for k in FLAGS}, 'decision_budget_km': None, 'uncertainty_band_min': None,
            'total_operating_km': None}


if __name__ == '__main__':
    retention = json.loads(RETENTION.read_text(encoding='utf-8'))
    screen = json.loads(SCREEN.read_text(encoding='utf-8'))
    if screen['source_sha256_normalized_retention'] != sha(RETENTION) or any(screen[k] for k in FLAGS):
        raise ValueError('source provenance drift')
    reference = next(f for f in family_inputs(load_sources()) if f['name'] == 'fast_local_both_directions')
    ceiling = prepare(reference, 60, False, ready_span=(390, 1180), pm_arrivals=SPANS['last_fs_1940']['pm_arrivals'])['wait_ceiling']
    for wing, local, other in (('west', VIRTUAL, 'east'), ('east', NORTH, 'west')):
        if any(local in {e['stop_place_id'] for l in v['loops'].values() for e in l['events']} for v in retention['variants'][other]):
            raise ValueError('local anchor not unique to wing; independent lower bound invalid')
    cases = []
    for wing, variants in retention['variants'].items():
        for variant in variants:
            result = solve_bound(variant, wing, ceiling)
            cases.append(result)
            OUTPUT.write_text(json.dumps(summarize(cases, retention, screen, ceiling), sort_keys=True, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
            print(json.dumps({k: result.get(k) for k in ('variant_id', 'solver_status', 'annual_service_km_lower_bound', 'relaxed_trip_count')}), flush=True)
