"""Group only equivalent protected-local timing traces; retain every edit."""
import copy
import hashlib
import json

from scripts.phase2_bound_rt031_line8_combined_edits_v3 import (
    BASE, SCREEN, RETENTION, VIRTUAL, NORTH, FLAGS, load_sources, family_inputs,
    prepare, SPANS, PEAKS, sha, solve_bound, adjusted_loops,
)
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import GRID

OUTPUT = BASE / 'combined_edits_timing_bounds.json'


def choices(screen, retention):
    result = {'west': [], 'east': []}
    for wing in result:
        zero = retention['variants'][wing][0]
        result[wing].append({'choice_id': wing + '_00__baseline', 'variant_id': zero['variant_id'],
                             'new_road_node': None, 'loops': zero['loops']})
    lookup = {v['variant_id']: v for vs in retention['variants'].values() for v in vs}
    for c in screen['cases']:
        loops = copy.deepcopy(lookup[c['variant_id']]['loops'])
        for p, loop in loops.items():
            loop['events'] = sorted(loop['events'] + c['new_site_occurrences'][p], key=lambda e: (e['path_node_index'], e['stop_place_id']))
        result[c['wing']].append({'choice_id': c['case_id'], 'variant_id': c['variant_id'],
                                 'new_road_node': c['new_road_node'], 'loops': loops})
    for wing, local, other in (('west', VIRTUAL, 'east'), ('east', NORTH, 'west')):
        if any(local in {e['stop_place_id'] for loop in c['loops'].values() for e in loop['events']} for c in result[other]):
            raise ValueError('protected local site shared across wings; additive bound invalid')
    return result


def signature(choice, wing):
    local = VIRTUAL if wing == 'west' else NORTH
    traces = []
    for m, d in GRID:
        loops = adjusted_loops(choice['loops'], m, d)
        for p, loop in sorted(loops.items()):
            events = [e for e in loop['events'] if e['stop_place_id'] == local]
            if not events:
                raise ValueError('mandatory local site missing')
            traces.append([m, d, p, loop['distance_m'], loop['road_minutes'],
                           max(e['offset_from_wing_origin_min'] for e in events)])
    return hashlib.sha256(json.dumps(traces, separators=(',', ':')).encode()).hexdigest()


def groups(pool):
    result = {}
    for wing, options in pool.items():
        for choice in options:
            sig = signature(choice, wing)
            if sig not in result:
                result[sig] = {'group_id': sig, 'wing': wing, 'representative_choice': choice, 'choice_ids': []}
            result[sig]['choice_ids'].append(choice['choice_id'])
    return result


def document(results, screen, retention, ceiling):
    pool = choices(screen, retention)
    expected = groups(pool)
    by_id = {r['group_id']: r for r in results}
    complete = len(results) == len(expected) and set(by_id) == set(expected) and all('annual_service_km_lower_bound' in r for r in results)
    minima = {w: min((r['annual_service_km_lower_bound'] for r in results if r['wing'] == w and 'annual_service_km_lower_bound' in r), default=None) for w in pool}
    minimum = sum(minima.values()) if all(v is not None for v in minima.values()) else None
    return {'contract': 'RT031_LINE8_COMBINED_EDIT_TIMING_BOUNDS_V3',
            'status': 'NINE_SCENARIO_LOCAL_AND_RAIL_RELAXATION_NOT_SERVICE_TIMETABLE',
            'source_sha256_normalized_newlines': {'screen': sha(SCREEN), 'retention': sha(RETENTION)},
            'wing_choice_counts': {w: len(p) for w, p in pool.items()},
            'combination_count': len(pool['west']) * len(pool['east']),
            'timing_group_count': len(expected), 'groups': results,
            'all_choices_bounded': complete, 'minimum_annual_service_km_lower_bound': minimum,
            'all_reference_cap_excluded': bool(complete and minimum > 111419 + 1e-5),
            'minimum_lower_bound_by_wing': minima,
            'fixed_comparison_peak_starts_min': PEAKS, 'ready_span_comparison_min': [390, 1180],
            'frozen_reference_am_wait_ceiling_comparison_min': ceiling,
            'reference_cap_unchanged': 111419,
            'semantics': 'All baseline plus single-wing bypass/relocation choices combined independently. Grouping requires exactly equal per-pattern distance, runtime and last protected-local boarding offsets in all nine moving/dwell scenarios; no spatial-access or other-site journey equivalence inferred. Require only protected-local H30/H60 and original frozen rail targets through 19:32 across those scenarios. Drop all other site frequency and all fleet/recovery constraints. Summed independent-wing MILP lower bounds apply to every grouped pair, including up to two added stops, not to other paths, peak phases, calendars or service spans. All source choices retained. No probabilistic reliability or selected network.',
            **{k: False for k in FLAGS}, 'decision_budget_km': None, 'uncertainty_band_min': None,
            'total_operating_km': None}


if __name__ == '__main__':
    screen = json.loads(SCREEN.read_text(encoding='utf-8'))
    retention = json.loads(RETENTION.read_text(encoding='utf-8'))
    if screen['source_sha256_normalized_retention'] != sha(RETENTION) or any(screen[k] for k in FLAGS):
        raise ValueError('source drift or selection')
    reference = next(f for f in family_inputs(load_sources()) if f['name'] == 'fast_local_both_directions')
    ceiling = prepare(reference, 60, False, ready_span=(390, 1180), pm_arrivals=SPANS['last_fs_1940']['pm_arrivals'])['wait_ceiling']
    pool = choices(screen, retention)
    grouped = groups(pool)
    results = []
    for index, group in enumerate(grouped.values()):
        result = solve_bound(group['representative_choice'], group['wing'], ceiling, GRID)
        result.update(group_id=group['group_id'], choice_ids=group['choice_ids'],
                      representative_choice_id=group['representative_choice']['choice_id'])
        results.append(result)
        print(json.dumps({'group': index + 1, 'total': len(grouped), 'wing': group['wing'],
                          'bound_km': result.get('annual_service_km_lower_bound'), 'solver_status': result['solver_status']}), flush=True)
    OUTPUT.write_text(json.dumps(document(results, screen, retention, ceiling), sort_keys=True, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
