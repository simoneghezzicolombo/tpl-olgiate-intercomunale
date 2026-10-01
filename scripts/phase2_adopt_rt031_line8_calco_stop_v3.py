"""Insert the caller's one Calco design event, never approve a physical stop."""
import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from scripts.phase2_probe_rt031_line8_local_counterflow_v3 import BASE, FS, inputs
from scripts.phase2_probe_rt031_unique_line_v3 import build_graph
from scripts.phase2_probe_rt031_line8_manoeuvre_cycles_v3 import split_only_edges
from scripts.phase2_probe_rt031_line8_calco_through_path_v3 import refresh_events

AUTH = ROOT / 'config/rt031_calco_centre_stop_authority_v3.json'
SOURCE = BASE / 'santa_calco_exchange.json'
OUTPUT = BASE / 'calco_centre_adopted_design.json'


def insert_event(loops, candidate, authority, edges):
    loops = copy.deepcopy(loops)
    if authority['design_position_adopted'] is not True:
        raise ValueError('Caller design authority required')
    if candidate['candidate_id'] != authority['site_id'] or candidate['coordinates'] != authority['coordinates']:
        raise ValueError('Selected upstream position drift')
    wing = authority['wing']; loop = loops[wing]
    index = authority['path_node_index']; path = loop['edge_ids']
    visits = [i for i, eid in enumerate(path, 1) if edges[eid]['v_node_id'] == authority['node_id']]
    if visits != candidate['path_node_indices'] or visits != [index]:
        raise ValueError('Unrepresented or multiple Calco occurrences')
    if not 0 < index < len(path) or edges[path[index]]['u_node_id'] != authority['node_id']:
        raise ValueError('Calco not an internal connected route vertex')
    existing = {e['stop_place_id'] for l in loops.values() for e in l['events']}
    if authority['site_id'] in existing or authority['removed_site_id'] in existing:
        raise ValueError('Duplicate addition or omitted Alpino still served')
    if authority['retained_santa_maria_site_id'] not in existing:
        raise ValueError('Santa Maria centre lost')
    loop['events'].append(dict(stop_place_id=authority['site_id'], name=authority['name'],
        path_node_index=index, occurrence_id=f"{wing}:{index}:{authority['site_id']}",
        direction=wing, service_node_hypothesis=authority['node_id'],
        site_status='CALLER_ADOPTED_DESIGN_POINT_FIELD_CHECK_PENDING',
        boarding_authorised=False, physical_boarding_authorised=False,
        passenger_continuity_certified=False))
    loop['events'].sort(key=lambda e: (e['path_node_index'], e['stop_place_id']))
    for key, item in loops.items():
        refresh_events(item, edges, key)
    return loops


def build(graph_dir):
    source = json.loads(SOURCE.read_text(encoding='utf-8'))
    authority = json.loads(AUTH.read_text(encoding='utf-8'))
    candidate = next(r for r in source['candidates'] if r['candidate_id'] == authority['site_id'])
    raw, _, _, _ = build_graph(inputs(graph_dir)); edges = split_only_edges(raw)
    loops = insert_event(source['loops_without_new_calco_event'], candidate, authority, edges)
    sites = {FS} | {e['stop_place_id'] for l in loops.values() for e in l['events']}
    if len(sites) != 27:
        raise ValueError('Expected 27 distinct design sites including FS')
    geo = json.loads(SOURCE.with_suffix('.geojson').read_text(encoding='utf-8'))
    features = [f for f in geo['features'] if f['properties'].get('role') != 'CALCO_SITING_CANDIDATE']
    event = next(e for e in loops[authority['wing']]['events'] if e['stop_place_id'] == authority['site_id'])
    features.append(dict(type='Feature', properties=dict(role='DESIGN_SITE',
        site_id=authority['site_id'], name=authority['name'], kind='PROPOSED_CALCO_SITE',
        boarding_authorised=False, physical_platform_count=None,
        design_position_adopted=True, ordered_occurrences=[dict(wing=authority['wing'],
            **{k: event[k] for k in ('occurrence_id', 'path_node_index', 'incoming_edge', 'outgoing_edge')})]),
        geometry=dict(type='Point', coordinates=authority['coordinates'])))
    result = dict(contract='RT031_LINE8_CALLER_ADOPTED_CALCO_DESIGN_V3', public_route_name='Linea 8',
        wing_sequence=['east_A', 'west_B'], loops=loops, selected_design_stop=authority,
        served_design_site_count_including_fs=len(sites),
        nonhub_ordered_occurrence_count_per_trip=sum(len(l['events']) for l in loops.values()),
        complete_path_distance_m=sum(l['distance_m'] for l in loops.values()),
        coverage_fraction=candidate['coverage_fraction'],
        change_percentage_points=candidate['change_percentage_points'],
        gross_previously_covered_fraction_lost=candidate['gross_previously_covered_fraction_lost'],
        source_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (AUTH, SOURCE)},
        road_graph_inputs_sha256={k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in inputs(graph_dir).items() if k in ('edges','nodes','rules','attachments')},
        adopted_development_street_exclusions=source['street_exclusions_adopted_for_development'],
        piazza_san_zenone_retained=True, timetable_recalculated=False,
        previous_timetable_transplanted=False, full_history_legality_certified=False,
        physical_boarding_authorised=False, physical_passenger_continuity_certified=False,
        bidirectional_h30_action_deferred=True, network_selected=False,
        primary_selection_authorised=False, runner_up_selection_authorised=False,
        decision_budget_km=None, uncertainty_band_min=None,
        semantics='One caller-adopted design location and one explicitly ordered Calco event on the exact corrected path. Coverage inherited from the hash-pinned joint exchange audit, not inferred from stop counts. Raw moving times exclude dwell. No physical platform/boarding, through-passenger continuity, public timetable, annual calendar or route selection certification.')
    return result, dict(type='FeatureCollection', features=features)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--graph_dir', type=Path, required=True)
    args = parser.parse_args(); result, geo = build(args.graph_dir)
    for path, data in ((OUTPUT, result), (OUTPUT.with_suffix('.geojson'), geo)):
        path.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':'))+'\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('complete_path_distance_m','served_design_site_count_including_fs','nonhub_ordered_occurrence_count_per_trip')}))
