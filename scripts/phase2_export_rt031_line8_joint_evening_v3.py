"""Explain one labelled comparison witness; never mark it as selected."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from scripts.phase2_compare_rt031_line8_evening_reallocation_v3 import BASE, FLAGS, load_sources
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import family_inputs, prepare, verify
from scripts.phase2_export_rt031_line8_109k_ledger_v3 import clock

GEOMETRY_SHA256 = 'ce745af520647b242dca31b5ccfa34615cd46d5b00ce0730c430fa0004e635ba'


def build(result, sources, shape):
    if result['contract'] != 'RT031_LINE8_JOINT_EVENING_TIMETABLE_FLEET_COMPARISON_V3' or any(result[k] for k in FLAGS):
        raise ValueError('unsupported or selected comparison')
    case = next(c for c in result['cases'] if c['family_id'] == 'fast_local_both_directions'
                and c['offpeak_wait_comparison_min'] == 90 and c['nominal_fleet_bound_comparison'] == 4)
    if not case['witness_found']:
        raise ValueError('no witness to export')
    family = next(f for f in family_inputs(sources) if f['name'] == case['family_id'])
    problem = prepare(family, 90, False)
    grid = verify(problem, case['trips'], case['comparison_peak_windows'], 4)
    nominal = next(g for g in grid if (g['moving_multiplier'], g['dwell_min'], g['recovery_min']) == (1.1, .5, 10))
    blocks = {i: block + 1 for block, indices in enumerate(nominal['trip_index_blocks']) for i in indices}
    loops = problem['adjusted'][1.1, .5]
    counts = Counter(t['loop'] for t in case['trips'])
    if counts != {'west_B': 18, 'east_A': 18}:
        raise ValueError('labelled witness changed; update explanation rather than silently substituting')
    trips, events, sites = [], [], {}
    for i, trip in enumerate(case['trips']):
        loop = loops[trip['loop']]
        arrival = trip['departure_min'] + loop['road_minutes']
        trips.append({'trip_id': f'T{i+1:02}', 'pattern': trip['loop'],
                      'fs_departure': clock(trip['departure_min']), 'fs_departure_min': trip['departure_min'],
                      'fs_return_nominal': clock(arrival), 'fs_return_nominal_min': arrival,
                      'service_km': loop['distance_m'] / 1000, 'conditional_vehicle_block': blocks[i]})
        for event in loop['events']:
            sid = event['stop_place_id']
            sites[sid] = {'stop_place_id': sid, 'name': event['name'], 'site_status': event['site_status'], 'boarding_authorised': False}
            events.append({'trip_id': f'T{i+1:02}', 'pattern': trip['loop'],
                           'occurrence_id': event['occurrence_id'], 'stop_place_id': sid,
                           'arrival_nominal': clock(trip['departure_min'] + event['offset_from_wing_origin_min'] - .5),
                           'departure_nominal': clock(trip['departure_min'] + event['offset_from_wing_origin_min']),
                           'boarding_authorised': False, 'passenger_continuity_certified': False})
    features = [f for f in shape['features'] if f['geometry']['type'] == 'Point'
                or (f['geometry']['type'] == 'LineString' and f['properties'].get('case') == 'both'
                    and f['properties'].get('pattern') in counts)]
    lines = [f for f in features if f['geometry']['type'] == 'LineString']
    points = [f for f in features if f['geometry']['type'] == 'Point']
    if len(lines) != 2 or len(points) != 28 or len(sites) != 27:
        raise ValueError('shape/site count drift')
    for line in lines:
        pattern = line['properties']['pattern']
        if abs(line['properties']['distance_m'] - family['loops'][pattern]['distance_m']) > 1e-6:
            raise ValueError('geometry distance mismatch')
    daily = sum(t['service_km'] for t in trips)
    if abs(daily * 260 - case['annual_service_km']) > 1e-5:
        raise ValueError('km ledger mismatch')
    payload = {'contract': 'RT031_LINE8_JOINT_EVENING_LABELLED_WITNESS_LEDGER_V3',
               'status': 'ILLUSTRATIVE_COMPARISON_NOT_SELECTED',
               'witness_key': ['fast_local_both_directions', 90, 4],
               'trips': trips, 'nominal_stop_occurrence_events': events,
               'nonhub_sites': sorted(sites.values(), key=lambda s: s['stop_place_id']),
               'site_count_including_fs': 28, 'daily_service_km': daily,
               'annual_service_days_assumption': 260, 'annual_service_km': case['annual_service_km'],
               'comparison_peak_windows': case['comparison_peak_windows'],
               'worst_grid_vehicle_count_conditional': case['worst_grid_vehicle_count_conditional'],
               'local_event_bindings_nominal': case['local_event_bindings_nominal'],
               'semantics': 'One labelled comparison for inspection, not a recommended winner. Seconds show model precision, not measured accuracy. Vehicle blocks do not imply passenger through-service, driver duties or depot validation. Site identities and directional occurrences are not authorised platforms.',
               **{k: False for k in FLAGS}, 'actual_timetable_certified': False,
               'decision_budget_km': None, 'uncertainty_band_min': None, 'total_operating_km': None}
    return payload, {'type': 'FeatureCollection', 'properties': {k: False for k in FLAGS}, 'features': features}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--graph_dir', type=Path)
    args = parser.parse_args()
    joint_path, shape_path = BASE / 'joint_evening_timetable.json', BASE / 'local_counterflow.geojson'
    if hashlib.sha256(shape_path.read_bytes().replace(b'\r\n', b'\n')).hexdigest() != GEOMETRY_SHA256:
        raise ValueError('frozen geometry drift')
    payload, shape = build(json.loads(joint_path.read_text(encoding='utf-8')), load_sources(),
                           json.loads(shape_path.read_text(encoding='utf-8')))
    payload['source_sha256_normalized_newlines'] = {k: hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
                                                   for k, p in (('joint_search', joint_path), ('geometry', shape_path))}
    for name, value in (('joint_evening_witness.json', payload), ('joint_evening_witness.geojson', shape)):
        (BASE / name).write_text(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    if args.graph_dir:
        from scripts.phase2_render_rt031_line8_counterflow_v3 import render
        render(args.graph_dir, BASE / 'joint_evening_witness.png', patterns=('west_B', 'east_A'),
               title='Linea 8 — due ali senza inversione durante la giornata\n129.536 km/anno: confronto H30 in punta / H90 nel resto, non adottato',
               show_baseline=False)
    print(json.dumps({'trips': len(payload['trips']), 'sites': payload['site_count_including_fs'], 'annual_service_km': payload['annual_service_km']}))
