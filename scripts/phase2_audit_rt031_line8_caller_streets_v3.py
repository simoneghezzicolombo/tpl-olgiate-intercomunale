"""Bounded caller street exclusions, not bus certification or a new timetable."""
import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from scripts.phase2_probe_rt031_line8_local_counterflow_v3 import BASE, FS, inputs
from scripts.phase2_probe_rt031_unique_line_v3 import build_graph
from scripts.phase2_probe_rt031_line8_manoeuvre_cycles_v3 import split_only_edges
from scripts.phase2_probe_rt031_line8_no_reverse_all_orders_v3 import NoReverseAdapter
from scripts.phase2_probe_rt031_line8_order_neighbourhood_v3 import reconstruct
from src.phase2_rt031_rt017_transition_adapter_v3 import FrozenRT017ViaNodeAdapter

AUTH = ROOT/'config/rt031_caller_street_and_rail_revision_v3.json'
SOURCE = BASE/'conditional_proposal_17_trips.json'
OUTPUT = BASE/'caller_street_exclusions.json'


def excluded_ways(elements, names):
    found = {str(w['id']) for w in elements if w['type']=='way'
             and w.get('tags', {}).get('name') in names}
    actual = {w.get('tags', {}).get('name') for w in elements
              if w['type']=='way' and str(w['id']) in found}
    if actual != set(names):
        raise ValueError('Street names not completely resolved in frozen OSM')
    return found


def build(graph_dir):
    authority = json.loads(AUTH.read_text(encoding='utf-8'))
    source = json.loads(SOURCE.read_text(encoding='utf-8'))
    if source['network_selected'] or source['served_design_site_count_including_fs'] != 27:
        raise ValueError('Unexpected conditional baseline')
    paths = inputs(graph_dir)
    raw, nodes, rules, attachments = build_graph(paths)
    edges = split_only_edges(raw)
    snapshot = graph_dir/'rt017/frozen_osm_snapshot.json.gz'
    osm = json.loads(gzip.decompress(snapshot.read_bytes()))
    names_by_way = {str(w['id']): w.get('tags', {}).get('name', '')
                    for w in osm['elements'] if w['type']=='way'}
    fs = attachments[FS]['graph_node_id']
    comparisons = authority['street_comparisons']
    comparisons = comparisons + [{'id':'all_three_exclusions', 'avoid_exact_osm_names':
        sorted({n for c in comparisons for n in c['avoid_exact_osm_names']})}]
    comparisons += [{**c, 'id':c['id']+'_free_local_arrival',
        'protect_local_incoming_edges':False} for c in comparisons
        if c['id'] in ('north_without_square','all_three_exclusions')]
    comparisons += [{'id':'caller_adopted_mirasole_cartiglio_tessitura',
        'avoid_exact_osm_names':authority['caller_update_2026_10_01']['adopted_development_street_exclusions'],
        'street_exclusions_adopted_for_development':True, 'piazza_san_zenone_retained':True}]
    baseline_distance = sum(l['distance_m'] for l in source['loops'].values())
    cases, features = [], []
    for comparison in comparisons:
        forbidden = excluded_ways(osm['elements'], comparison['avoid_exact_osm_names'])
        usable = {eid:e for eid,e in edges.items() if e['osm_way_id'] not in forbidden}
        adapter = NoReverseAdapter(usable, FrozenRT017ViaNodeAdapter(
            usable.values(), rules, unresolved_external_via_way_count=2))
        loops = {}
        for wing, old in source['loops'].items():
            ordered = sorted(old['events'], key=lambda e:(e['path_node_index'],e['stop_place_id']))
            required = [old['edge_ids'][0], old['edge_ids'][-1]] + [e['incoming_edge'] for e in ordered]
            if any(eid not in usable for eid in required):
                loops[wing] = None
                continue
            loops[wing] = reconstruct(old, ordered, usable, adapter, fs, None,
                comparison.get('protect_local_incoming_edges',True), wing)
            if loops[wing]:
                for eid in loops[wing]['edge_ids']:
                    if usable[eid]['osm_way_id'] in forbidden:
                        raise ValueError('Excluded street leaked into reconstructed path')
        reachable = all(l is not None for l in loops.values())
        row = {**comparison, 'excluded_osm_way_ids':sorted(forbidden),
            'reachable_with_same_ordered_events_and_boundaries':reachable,
            'all_requested_main_corridors_verified':False,
            'bus_suitability_certified':False, 'retimed':False,
            'annual_service_km_certified':False, 'full_history_legality_certified':False}
        if reachable:
            distance = sum(l['distance_m'] for l in loops.values())
            row.update(loops=loops, complete_path_distance_m=distance,
                distance_delta_m=distance-baseline_distance,
                site_count_including_fs=27,
                annual_distance_arithmetic_17_trips_260_days_not_retimed=distance*17*260/1000,
                actual_named_streets={wing:list(dict.fromkeys(names_by_way.get(usable[e]['osm_way_id'],'')
                    for e in loop['edge_ids'])) for wing,loop in loops.items()})
            for wing, loop in loops.items():
                vertex = [usable[loop['edge_ids'][0]]['u_node_id']]+[usable[e]['v_node_id'] for e in loop['edge_ids']]
                coords = {n:[float(r['lon']),float(r['lat'])] for n,r in nodes.items()}
                for feature in json.loads(SOURCE.with_suffix('.geojson').read_text(encoding='utf-8'))['features']:
                    if feature['geometry']['type']=='Point':
                        # The projected south node is absent from the original node CSV.
                        if feature['properties'].get('site_id')=='RT031::P2V2S_0031_PROJECTED_ROAD_POINT':
                            coords['RT031::P2V2S_0031_PROJECTED_ROAD_POINT']=feature['geometry']['coordinates']
                features.append({'type':'Feature','properties':{'case_id':row['id'],'wing':wing,
                    'retimed':False,'bus_suitability_certified':False},
                    'geometry':{'type':'LineString','coordinates':[coords[n] for n in vertex]}})
        cases.append(row)
        print(json.dumps({k:row[k] for k in ('id','reachable_with_same_ordered_events_and_boundaries',
            'distance_delta_m') if k in row}),flush=True)
    return {'contract':'RT031_CALLER_STREET_EXCLUSIONS_DIAGNOSTIC_V3', 'cases':cases,
        'source_sha256':{k:hashlib.sha256(p.read_bytes()).hexdigest()
            for k,p in dict(authority=AUTH,proposal=SOURCE,osm=snapshot,**{k:paths[k] for k in ('edges','nodes','rules')}).items()},
        'semantics':'Distance-minimum within fixed event order, FS boundary edges and local incoming edges, excluding only the exact caller-identified street ways. Other narrow streets may remain. No immediate reversals and represented via-node restrictions only; not full-history legality or bus approval. Same sites are not certified platforms. Distance arithmetic is not an executable annual timetable.',
        'network_selected':False,'primary_selection_authorised':False,'runner_up_selection_authorised':False,
        'decision_budget_km':None,'uncertainty_band_min':None}, {'type':'FeatureCollection','features':features}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--graph_dir',type=Path,required=True)
    args=parser.parse_args()
    result, shape = build(args.graph_dir)
    OUTPUT.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n',encoding='utf-8')
    OUTPUT.with_suffix('.geojson').write_text(json.dumps(shape,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n',encoding='utf-8')
