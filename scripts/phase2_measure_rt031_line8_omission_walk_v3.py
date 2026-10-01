"""Conditional walking coverage for explicit service events, never passenger OD."""
import argparse
import gzip
import hashlib
import json
from fractions import Fraction
from pathlib import Path

import numpy as np

from scripts.phase2_probe_rt031_line8_retention_tradeoffs_v3 import load_access, MUNICIPALITY_NAMES
from scripts.phase2_probe_rt031_line8_local_counterflow_v3 import BASE, FS, NORTH, VIRTUAL, inputs
from scripts.phase2_probe_rt031_unique_line_v3 import build_graph
from scripts.phase2_audit_rt031_unique_line_walk_access_v3 import pedestrian_time
from scripts.phase2_audit_rt031_conditional_new_stop_access_v3 import weighted_ratio
from scripts.phase2_probe_rt031_line8_no_reverse_all_orders_v3 import OUTPUT as ROAD
from scripts.phase2_probe_rt031_line8_calco_through_path_v3 import OUTPUT as CALCO

OUTPUT = BASE/'no_reverse_omission_walking.json'
ARLATE = 'PROXY::RT031_ADDITIONAL::n:534398.29:5063851.64'


def build(graph_dir, walk_dir):
    paths = inputs(graph_dir)
    paths.update(matrix=walk_dir/'output/rt028_population_unit_stop_walk_matrix_v3.csv',
        pedestrian_osm=walk_dir/'input/rt028_osm_pedestrian_snapshot_v3.osm',
        candidates_normalized=paths['candidates_normalized_newlines'],
        road_screen=BASE.parent/'rt031_unique_line_road_screen_v3/screen.json',
        access_reference=BASE/'brivio_existing_sites_walk.json')
    register = json.loads(gzip.decompress((BASE/'stop_plan_and_additions.json.gz').read_bytes()))
    sites = {r['site_id']:{'node':r['graph_node_id']} for r in register['register'] if r['site_id']!=ARLATE}
    _, original_baseline, _, context = load_access(paths, sites, include_context=True)
    _, nodes, _, _ = build_graph(paths)
    road = json.loads(gzip.decompress(ROAD.read_bytes()))
    calco = next(c for c in json.loads(gzip.decompress(CALCO.read_bytes()))['cases'] if c['reachable'])
    graph = context['graph']; units = context['units']; snaps = context['snap_map']
    arlate_node = 'n:534398.29:5063851.64'
    arlate_times, _ = pedestrian_time(graph, snaps, units,
        float(nodes[arlate_node]['lat']), float(nodes[arlate_node]['lon']))
    calco_node = calco['candidate_service_node']
    calco_times, _ = pedestrian_time(graph, snaps, units,
        float(nodes[calco_node]['lat']), float(nodes[calco_node]['lon']))
    substrate = context['substrate']
    comparison_ids = {e['stop_place_id'] for l in road['loops'].values() for e in l['events']}|{FS}

    def access(served_ids):
        matrix_ids = sorted(served_ids-{VIRTUAL,NORTH,ARLATE,'FROZEN::300634'})
        t = substrate.walk_time_matrix[:,[substrate.stop_index[sid] for sid in matrix_ids]].min(axis=1)
        t = np.minimum(t, context['local'])
        if ARLATE in served_ids:
            t = np.minimum(t, arlate_times)
        if 'FROZEN::300634' in served_ids:
            t = np.minimum(t, calco_times)
        return {code:{str(limit):str(weighted_ratio(t<=limit,context['weights'],
                    context['core'] if code=='TOTAL' else context['core'] & (context['codes']==code)))
                for limit in (5,8,10)} for code in ('TOTAL',*MUNICIPALITY_NAMES)}

    baseline = access(comparison_ids)
    cases = []
    for c in road['single_inventory_omission_comparisons_not_adopted']:
        coverage = access(comparison_ids-{c['omitted_stop_identity']})
        losses = {code:{limit:float(Fraction(baseline[code][limit])-Fraction(value))*100
                        for limit,value in row.items()} for code,row in coverage.items()}
        cases.append({'omitted_stop_identity':c['omitted_stop_identity'],'omitted_name':c['omitted_name'],
            'annual_service_km_16_trips_260_days':c['annual_service_km_16_trips_260_days'],
            'potential_walking_access_fraction':coverage,
            'potential_walking_access_loss_percentage_points':losses,
            'boarding_authorised':False,'stop_omission_adopted':False})
    frontier = [c for c in cases if not any(
        other['annual_service_km_16_trips_260_days']<=c['annual_service_km_16_trips_260_days'] and
        all(Fraction(other['potential_walking_access_fraction'][code][limit]) >= Fraction(c['potential_walking_access_fraction'][code][limit])
            for code in MUNICIPALITY_NAMES for limit in ('5','8','10')) and
        (other['annual_service_km_16_trips_260_days']<c['annual_service_km_16_trips_260_days'] or
         any(Fraction(other['potential_walking_access_fraction'][code][limit]) > Fraction(c['potential_walking_access_fraction'][code][limit])
            for code in MUNICIPALITY_NAMES for limit in ('5','8','10')))
        for other in cases)]
    fixed = road['hoe_omission_fixed_event_order_comparison_not_adopted']
    hoe_coverage = next(c for c in cases if c['omitted_stop_identity']==fixed['omitted_stop_identity'])
    return {'contract':'RT031_LINE8_NO_REVERSE_SINGLE_OMISSION_CONDITIONAL_WALK_V3',
        'road_source_sha256':hashlib.sha256(ROAD.read_bytes()).hexdigest(),
        'walking_source_sha256':{k:hashlib.sha256(paths[k].read_bytes()).hexdigest()
                                  for k in ('matrix','pedestrian_osm','candidates_normalized')},
        'original_28_site_reference_reproduced':True,
        'original_28_site_reference_access_fraction':original_baseline,
        'all_29_comparison_sites_access_fraction':baseline,'municipality_names':MUNICIPALITY_NAMES,
        'cases':cases,'unweighted_km_municipal_walk_frontier_omission_ids':[c['omitted_stop_identity'] for c in frontier],
        'hoe_fixed_event_order_comparison_not_adopted':{
            **hoe_coverage,'annual_service_km_16_trips_260_days':fixed['annual_service_km_16_trips_260_days'],
            'same_served_points_coverage_independent_of_event_order':True,
            'retained_nominal_fs_journey_times_preserved':fixed['retained_journey_times_preserved']},
        'km_walk_frontier_is_not_journey_time_or_service_dominance':True,
        'semantics':'Conditional potential walking coverage of pinned population units, using inventory '
            'points plus unapproved Olgiate south, San Zeno, Arlate and Calco 19m hypotheses. Original '
            '28-site reference reproduced first. All five municipalities reported at 5/8/10 minutes. '
            'Only explicit served events counted; incidental road crossings are not stops. Population '
            'weights are geographic coverage counts, not OD/passenger allocation or normative utility '
            'weights. Exact rational fractions; loss is percentage points, not percentage change. '
            'No acceptable loss threshold, boarding approval, empirical demand or route selection.',
        'physical_walking_accessibility_certified':False,'network_selected':False,
        'primary_selection_authorised':False,'runner_up_selection_authorised':False,
        'decision_budget_km':None,'uncertainty_band_min':None}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--graph_dir',type=Path,required=True)
    p.add_argument('--walk_dir',type=Path,required=True)
    a=p.parse_args();r=build(a.graph_dir,a.walk_dir)
    OUTPUT.write_text(json.dumps(r,sort_keys=True,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
