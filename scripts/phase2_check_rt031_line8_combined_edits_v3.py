"""Four explicit minimum-bound diagnostics: joint service and joint coverage."""
import argparse
import copy
from fractions import Fraction
import itertools
import json
from pathlib import Path

import numpy as np

from scripts.phase2_bound_rt031_line8_combined_timing_v3 import OUTPUT as BOUNDS, choices
from scripts.phase2_probe_rt031_line8_stop_relocation_v3 import (
    BASE, OUTPUT as SCREEN, RETENTION, load_access, inventory_times, ratios, lost_ratios,
    pedestrian_time, build_graph, inputs, FS, VIRTUAL, NORTH, digest,
)
from scripts.phase2_check_rt031_line8_relocation_timetable_v3 import sha, PEAKS
from scripts.phase2_compare_rt031_line8_evening_reallocation_v3 import FLAGS, load_sources
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import family_inputs, prepare, solve
from scripts.phase2_compare_rt031_line8_shorter_span_v3 import SPANS

OUTPUT = BASE / 'combined_edits_joint_diagnostics.json'


def diagnostic_pairs(bounds, pool):
    if not bounds['all_choices_bounded']:
        raise ValueError('incomplete lower-bound evidence')
    selected = {}
    for wing in ('west', 'east'):
        selected[wing] = [g['representative_choice_id'] for g in bounds['groups']
                          if g['wing'] == wing and abs(g['annual_service_km_lower_bound'] - bounds['minimum_lower_bound_by_wing'][wing]) < 1e-5]
        if not selected[wing] or any(cid not in {c['choice_id'] for c in pool[wing]} for cid in selected[wing]):
            raise ValueError('missing diagnostic representative')
    return list(itertools.product(selected['west'], selected['east']))


def combine_family(reference, west, east):
    loops = copy.deepcopy({**west['loops'], **east['loops']})
    for p, loop in loops.items():
        if (loop['edge_ids'][0], loop['edge_ids'][-1]) != (reference['loops'][p]['edge_ids'][0], reference['loops'][p]['edge_ids'][-1]):
            raise ValueError('cannot inherit FS joins across changed boundary edges')
    for wing in ('west', 'east'):
        if {e['stop_place_id'] for e in loops[wing + '_A']['events']} != {e['stop_place_id'] for e in loops[wing + '_B']['events']}:
            raise ValueError('directional site domains differ')
    return {**reference, 'name': west['choice_id'] + '+' + east['choice_id'], 'loops': loops,
            'comparison_nonhub_site_ids': sorted({e['stop_place_id'] for loop in loops.values() for e in loop['events']})}


def combined_access(family, context, node_times, baseline_times):
    sites = {e['stop_place_id'] for loop in family['loops'].values() for e in loop['events']} | {FS}
    new_ids = {sid for sid in sites if sid.startswith('PROXY::RELOCATION_NODE_')}
    times = inventory_times(sites - new_ids, context)
    for sid in new_ids:
        node = sid.removeprefix('PROXY::RELOCATION_NODE_')
        if node not in node_times:
            raise ValueError('new site missing pedestrian vector')
        times = np.minimum(times, node_times[node])
    return {'potential_access_fraction': ratios(times, context),
            'previously_covered_population_fraction_lost': lost_ratios(baseline_times, times, context),
            'no_previously_covered_units_lost': all(not np.any(context['core'] & (baseline_times <= t) & (times > t)) for t in (5, 8, 10))}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--graph_dir', type=Path, required=True)
    parser.add_argument('--walk_dir', type=Path, required=True)
    args = parser.parse_args()
    screen = json.loads(SCREEN.read_text(encoding='utf-8'))
    retention = json.loads(RETENTION.read_text(encoding='utf-8'))
    bounds = json.loads(BOUNDS.read_text(encoding='utf-8'))
    if bounds['source_sha256_normalized_newlines'] != {'screen': sha(SCREEN), 'retention': sha(RETENTION)} or any(bounds[k] for k in FLAGS):
        raise ValueError('lower bound source drift or selection')
    paths = inputs(args.graph_dir)
    paths.update(counterflow=BASE / 'local_counterflow.json',
                 matrix=args.walk_dir / 'output/rt028_population_unit_stop_walk_matrix_v3.csv',
                 pedestrian_osm=args.walk_dir / 'input/rt028_osm_pedestrian_snapshot_v3.osm',
                 candidates_normalized=paths['candidates_normalized_newlines'],
                 road_screen=BASE.parent / 'rt031_unique_line_road_screen_v3/screen.json',
                 access_reference=BASE / 'brivio_existing_sites_walk.json')
    for key, path in paths.items():
        normalized = key not in ('edges', 'nodes', 'rules', 'attachments', 'successor', 'matrix', 'pedestrian_osm')
        if digest(path, normalized) != retention['source_sha256'][key]:
            raise ValueError('road or access source drift: ' + key)
    edges, nodes, _, attachments = build_graph(paths)
    reference = next(f for f in family_inputs(load_sources()) if f['name'] == 'fast_local_both_directions')
    sites = {FS: {'node': attachments[FS]['graph_node_id'], 'name': 'Olgiate FS'}}
    for loop in reference['loops'].values():
        for e in loop['events']:
            sites[e['stop_place_id']] = {'node': edges[e['incoming_edge']]['v_node_id'], 'name': e['name']}
    _, baseline, _, context = load_access(paths, sites, include_context=True)
    baseline_times = inventory_times(sites, context)
    pool = choices(screen, retention)
    lookup = {c['choice_id']: c for cs in pool.values() for c in cs}
    pairs = diagnostic_pairs(bounds, pool)
    new_nodes = {lookup[cid]['new_road_node'] for pair in pairs for cid in pair} - {None}
    node_times = {}
    for node in new_nodes:
        coords = screen['candidate_nodes'][node]
        node_times[node], snap = pedestrian_time(context['graph'], context['snap_map'], context['units'], coords['lat'], coords['lon'])
        if snap != coords['pedestrian_snap']:
            raise ValueError('new-site pedestrian attachment drift')
    result = {'contract': 'RT031_LINE8_COMBINED_EDITS_JOINT_DIAGNOSTICS_V3',
              'status': 'EXPLICIT_EXTREME_DIAGNOSTICS_NOT_RECOMMENDATIONS',
              'source_sha256_normalized_newlines': {'screen': sha(SCREEN), 'retention': sha(RETENTION), 'bounds': sha(BOUNDS)},
              'baseline_potential_access_fraction': baseline, 'municipality_names': screen['municipality_names'],
              'cases': [], 'reference_cap_unchanged': 111419,
              'semantics': 'One representative from each minimum protected-local/rail timing lower-bound group, combined across wings. Four diagnostics only, not all 121410 full operating timetables or a global winner. Actual union of served sites and new-point pedestrian vectors recomputed: single-wing percentage deltas never added. Full declared site domain checked across nine timing scenarios, frozen rail/peaks, H60 outside peaks and four nominal vehicles. Path-boundary joins inherited only if exact edges unchanged. The least-resource extreme sacrifices territorial service; no acceptable loss or budget uplift approved.',
              **{k: False for k in FLAGS}, 'actual_timetable_certified': False,
              'decision_budget_km': None, 'uncertainty_band_min': None, 'total_operating_km': None}
    for west_id, east_id in pairs:
        family = combine_family(reference, lookup[west_id], lookup[east_id])
        access = combined_access(family, context, node_times, baseline_times)
        changes = {m: {t: 100 * float(Fraction(value) - Fraction(baseline[m][t])) for t, value in row.items()}
                   for m, row in access['potential_access_fraction'].items()}
        p = prepare(family, 60, ready_span=(390, 1180), pm_arrivals=SPANS['last_fs_1940']['pm_arrivals'],
                    am_wait_ceiling_comparison_min=bounds['frozen_reference_am_wait_ceiling_comparison_min'])
        answer = solve(p, 4, 30, fixed_peak_starts=PEAKS)
        answer.update(west_choice_id=west_id, east_choice_id=east_id,
                      site_count_including_fs=len(family['comparison_nonhub_site_ids']) + 1,
                      served_nonhub_site_ids=family['comparison_nonhub_site_ids'],
                      lost_original_site_ids=sorted(set(sites) - set(family['comparison_nonhub_site_ids']) - {FS}),
                      potential_access_change_pp=changes, **access)
        result['cases'].append(answer)
        OUTPUT.write_text(json.dumps(result, sort_keys=True, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
        print(json.dumps({k: answer.get(k) for k in ('west_choice_id', 'east_choice_id', 'annual_service_km', 'solver_status', 'site_count_including_fs', 'worst_grid_vehicle_count_conditional')}), flush=True)
