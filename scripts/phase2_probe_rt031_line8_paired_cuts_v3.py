"""Exhaust zero/one/two inventory omissions with the reference event order.

No policy threshold for territorial loss, route selection or H70 adoption.
The kilometer reference is a comparison against the specific accepted witness,
not a caller-declared Decision Contract budget or a calendar authorization.
"""
import argparse
import gzip
import hashlib
import itertools
import json
from fractions import Fraction
from pathlib import Path

from scripts.phase2_probe_rt031_line8_calco_through_path_v3 import OUTPUT as CALCO
from scripts.phase2_probe_rt031_line8_local_counterflow_v3 import BASE, FS, inputs
from scripts.phase2_probe_rt031_unique_line_v3 import build_graph
from scripts.phase2_probe_rt031_line8_manoeuvre_cycles_v3 import split_only_edges
from scripts.phase2_probe_rt031_line8_no_reverse_all_orders_v3 import LOCAL, NoReverseAdapter
from scripts.phase2_probe_rt031_line8_order_neighbourhood_v3 import reconstruct, access_vector
from scripts.phase2_measure_rt031_line8_omission_walk_v3 import (
    ARLATE, walking_context, MUNICIPALITY_NAMES)
from scripts.phase2_probe_rt031_line8_variable_fs_hold_v3 import solve, wing_offsets
from scripts.phase2_rebuild_rt031_uniform_complete_line_v3 import (
    inputs as service_inputs, source_fingerprints)
from scripts.phase2_close_rt031_line8_16_full_trips_v3 import AUTH
from src.phase2_rt031_rt017_transition_adapter_v3 import FrozenRT017ViaNodeAdapter

OUTPUT = BASE/'paired_cuts_fixed_order.json.gz'
SHAPE = BASE/'paired_cuts_fixed_order.geojson'
MAP = BASE/'paired_cuts_fixed_order.png'
SPECIFIC_ACCEPTED_COMPARISON_KM = 115143.26681282124


def removal_domain(ids):
    ids = sorted(set(ids))
    return [tuple()] + [(s,) for s in ids] + list(itertools.combinations(ids, 2))


def losses(reference, coverage):
    return {code:{limit:float(Fraction(reference[code][limit])-Fraction(value))*100
                  for limit,value in row.items()} for code,row in coverage.items()}


def km_walk_dominates(a, b):
    """Only these named metrics, never passenger/service dominance."""
    av = [a['distance_m']] + [-Fraction(a['potential_walking_access_fraction'][c][t])
                             for c in MUNICIPALITY_NAMES for t in ('5','8','10')]
    bv = [b['distance_m']] + [-Fraction(b['potential_walking_access_fraction'][c][t])
                             for c in MUNICIPALITY_NAMES for t in ('5','8','10')]
    return all(x <= y for x,y in zip(av,bv)) and any(x < y for x,y in zip(av,bv))


def build(graph_dir, walk_dir):
    parent_bytes = CALCO.read_bytes()
    parent = json.loads(gzip.decompress(parent_bytes))
    calco = next(c for c in parent['cases'] if c['reachable'])
    reference = calco['whole_wing_fixed_order_without_reversals']['loops']
    reference_access = access_vector(reference)
    paths = inputs(graph_dir)
    raw, nodes, rules, attachments = build_graph(paths)
    edges = split_only_edges(raw)
    adapter = NoReverseAdapter(edges, FrozenRT017ViaNodeAdapter(
        edges.values(), rules, unresolved_external_via_way_count=2))
    fs = attachments[FS]['graph_node_id']
    ids = {e['stop_place_id'] for l in reference.values() for e in l['events']} | {FS}
    protected = {FS, ARLATE, *LOCAL.values()}
    domain = removal_domain(ids-protected)
    # Cache every wing/subset once; inter-wing pairs reuse these exact paths.
    cache = {}
    event_by_id = {e['stop_place_id']:e for l in reference.values() for e in l['events']}
    for wing, old in reference.items():
        wing_ids = {e['stop_place_id'] for e in old['events']}
        for removed in sorted({tuple(s for s in omission if s in wing_ids) for omission in domain}):
            if not removed:
                loop = old
            else:
                ordered = sorted([e for e in old['events'] if e['stop_place_id'] not in removed],
                                 key=lambda e:(e['path_node_index'],e['stop_place_id']))
                loop = reconstruct(old, ordered, edges, adapter, fs,
                                   calco['candidate_service_node'], True, wing)
            cache[wing,removed] = loop
        print('wing paths',wing,len([k for k in cache if k[0]==wing]),flush=True)
    access, original_baseline, walk_paths = walking_context(graph_dir, walk_dir)
    baseline_walk = access(ids)
    cases = []
    for omission in domain:
        loops = {wing:cache[wing,tuple(s for s in omission if s in {
                 e['stop_place_id'] for e in old['events']})] for wing,old in reference.items()}
        c = {'case_id':'retain_all' if not omission else '|'.join(omission),
             'omitted_stop_ids':list(omission),
             'omitted_names':[event_by_id[s]['name'] for s in omission],
             'reachable':all(l is not None for l in loops.values()),
             'stop_omission_adopted':False}
        if c['reachable']:
            nominal = access_vector(loops)
            distance = sum(l['distance_m'] for l in loops.values())
            walk = access(ids-set(omission))
            c.update(loops=loops,distance_m=distance,site_count_including_fs=len(ids)-len(omission),
                annual_service_km_16_trips_260_days=distance*16*260/1000,
                potential_walking_access_fraction=walk,
                potential_walking_access_loss_percentage_points=losses(baseline_walk,walk),
                retained_access_nominal_by_site=nominal,
                retained_access_delta_min={s:{d:nominal[s][d]-reference_access[s][d]
                    for d in nominal[s]} for s in nominal},
                retained_nominal_fs_journeys_no_worse=all(nominal[s][d]<=reference_access[s][d]+1e-8
                    for s in nominal for d in nominal[s]),
                calco_19m_hypothesis_required='FROZEN::300634' not in omission)
        cases.append(c)
    reachable = [c for c in cases if c['reachable']]
    frontier = [c['case_id'] for c in reachable if not any(km_walk_dominates(o,c) for o in reachable)]
    result = dict(contract='RT031_LINE8_ZERO_ONE_TWO_FIXED_ORDER_CUTS_DIAGNOSTIC_V3',
        parent_source_sha256=hashlib.sha256(parent_bytes).hexdigest(),
        graph_source_sha256={k:hashlib.sha256(paths[k].read_bytes()).hexdigest()
                            for k in ('edges','nodes','rules','attachments')},
        walking_source_sha256={k:hashlib.sha256(walk_paths[k].read_bytes()).hexdigest()
                              for k in ('matrix','pedestrian_osm','candidates_normalized')},
        original_28_site_reference_reproduced=True,
        original_28_site_reference_access_fraction=original_baseline,
        reference_access_fraction=baseline_walk,municipality_names=MUNICIPALITY_NAMES,
        protected_ids=sorted(protected),removable_inventory_ids=sorted(ids-protected),
        declared_domain_count=len(domain),cases=cases,
        unweighted_km_municipal_walk_frontier_case_ids=frontier,
        km_walk_frontier_is_not_journey_or_service_dominance=True,
        timetable_pruning_by_km_walk_dominance=False,
        specific_accepted_comparison_km_not_general_budget=SPECIFIC_ACCEPTED_COMPARISON_KM,
        semantics='All zero/one/two omissions of the 25 inventory identities; same inherited '
          'ordered retained events, fixed FS boundary edges and local incoming edges. Distance '
          'minimum within each such ordered edge-state domain, not all orders/street networks. '
          'No immediate reversal inside wings; represented via-node rules only. All remaining '
          'events explicit; geometric crossings never counted as service. Conditional walking '
          'fractions reproduce the historic reference before including unapproved local/Arlate/Calco '
          'hypotheses. Joint omission coverage recomputed, not added single-site losses. '
          'No invented loss threshold, passengers, OD downscaling, utility weights or miss probability. '
          '16 trips and 260 days are kilometer comparisons; calendar not adopted.',
        decision_budget_km=None,uncertainty_band_min=None,network_selected=False,
        primary_selection_authorised=False,runner_up_selection_authorised=False,
        candidate_domain_complete=False,physical_boarding_authorised=False,
        full_history_legality_certified=False)
    # Publish every reachable road shape, not an arbitrarily selected winner.
    coords = {n:[float(v['lon']),float(v['lat'])] for n,v in nodes.items()}
    ms = json.loads(gzip.decompress((BASE/'stop_plan_and_additions.json.gz').read_bytes()))
    coords.update({m['node_id']:m['coordinates'] for m in ms['manoeuvres']})
    features = []
    for c in reachable:
        for wing,loop in c['loops'].items():
            path = loop['edge_ids']
            xy = [coords[edges[path[0]]['u_node_id']]]+[coords[edges[e]['v_node_id']] for e in path]
            features.append(dict(type='Feature',properties=dict(case_id=c['case_id'],wing=wing,
                omitted_names=c['omitted_names'],adopted=False),
                geometry=dict(type='LineString',coordinates=xy)))
    return result, dict(type='FeatureCollection',features=features)


def timetable(result, time_limit):
    _,policy,_,_,_ = service_inputs()
    cases = [c for c in result['cases'] if c['reachable'] and
             c['annual_service_km_16_trips_260_days']<=SPECIFIC_ACCEPTED_COMPARISON_KM+1e-8]
    for c in cases:
        c['h60_timetable_comparisons_not_adopted'] = []
        c['timetable_source_fingerprints'] = source_fingerprints(policy,c['loops'])
        for first in ('west_B','east_A'):
            r = solve(policy,c['loops'],first,False,60,time_limit,max_mid=85,
                      anchor_policy='flexible_real_trains')
            r['solver_time_limit_seconds'] = time_limit
            c['h60_timetable_comparisons_not_adopted'].append(r)
            print(c['omitted_names'],first,r['solver_status'],r['witness_found'],flush=True)
    result['timetable_domain'] = dict(case_ids=[c['case_id'] for c in cases],
        first_wings=['west_B','east_A'],full_trip_count=16,shoulder_cap_min=60,
        deep_offpeak_cap_min=120,deep_offpeak_window_min=[600,960],max_mid_offset_min=85,
        rail_policy='five consecutive archived trains per wing per peak, actual H30 departures',
        source='phase2_probe_rt031_line8_variable_fs_hold_v3.solve',
        omitted_cases_excluded_only_by_specific_comparison_km=True,
        km_filter_is_not_an_adopted_budget=True,timeout_is_not_infeasibility=True,
        solver_time_limit_seconds=time_limit,
        trip_authority_sha256_normalized_newlines=hashlib.sha256(
            AUTH.read_bytes().replace(b'\r\n',b'\n')).hexdigest())
    if json.loads(AUTH.read_text(encoding='utf-8'))['specific_annual_service_km_comparison_accepted'] != SPECIFIC_ACCEPTED_COMPARISON_KM:
        raise ValueError('specific caller comparison changed')
    return result


def trip_count_comparison(result, time_limit):
    """Price an explicit extra-trip change, never adopt it or exclude a loser."""
    _,policy,_,_,_ = service_inputs()
    for c in result['cases']:
        if c['case_id'] not in result['timetable_domain']['case_ids']:continue
        c['extra_trip_count_comparisons_not_adopted'] = []
        for count,first in itertools.product((17,18),('west_B','east_A')):
            r=solve(policy,c['loops'],first,False,60,time_limit,max_mid=85,
                    anchor_policy='flexible_real_trains',full_trip_count=count,
                    minimize_hold=True)
            r.update(solver_time_limit_seconds=time_limit,comparison_not_adopted=True,
                annual_service_km_260_day_comparison=count*c['distance_m']*.26,
                trip_count_differs_from_caller_16=True)
            if r['witness_found']:
                r['maximum_intermediate_fs_onboard_wait_by_engineering_scenario'] = [
                    dict(moving_multiplier=m,dwell_min=d,
                         max_wait_min=max(t['intermediate_offset_min']-g[first]['road_minutes']
                                          for t in r['full_trips']))
                    for (m,d),g in wing_offsets(c['loops']).items()]
            c['extra_trip_count_comparisons_not_adopted'].append(r)
            print('extra trips',c['omitted_names'],count,first,r['solver_status'],r['witness_found'],flush=True)
    result['extra_trip_count_domain_not_adopted']=dict(
        case_ids=result['timetable_domain']['case_ids'],full_trip_counts=[17,18],
        first_wings=['west_B','east_A'],other_timing_constraints_unchanged=True,
        extra_trips_authorised=False,territorial_losses_authorised=False,
        calendar_adopted=False,solver_time_limit_seconds=time_limit)
    result['extra_trip_count_domain_not_adopted']['objective'] = (
        'minimum sum of intermediate FS offsets at fixed trip count and exactly 20 '
        'rail assignments; not minimum maximum hold or a network selection')
    return result


def render_shortest_distance_diagnostic(result):
    """One labeled distance extreme for inspection, NOT a service recommendation."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import math
    shapes=json.loads(SHAPE.read_text(encoding='utf-8'))['features']
    shortest=min((c for c in result['cases'] if c['reachable']),key=lambda c:c['distance_m'])
    register=json.loads(gzip.decompress((BASE/'stop_plan_and_additions.json.gz').read_bytes()))
    coordinates={s['site_id']:s['road_coordinates'] for s in register['register']}
    coordinates[ARLATE]=next(s['coordinates'] for s in register['single_additions']
                            if s['candidate_id']=='N1212')
    fig,ax=plt.subplots(figsize=(10,7))
    for case_id in ('retain_all',shortest['case_id']):
        for f in shapes:
            if f['properties']['case_id']!=case_id:continue
            xy=f['geometry']['coordinates']
            if case_id=='retain_all':
                ax.plot(*zip(*xy),lw=1,ls='--',color='#999999')
            else:
                wing=f['properties']['wing']
                ax.plot(*zip(*xy),lw=2,color='#2586d8' if wing=='west_B' else '#ee8128',
                        label='Ala ovest' if wing=='west_B' else 'Ala est')
    for label,sid in [('Olgiate sud',LOCAL['west_B']),('San Zeno',LOCAL['east_A']),
                      ('Arlate',ARLATE),('Olgiate FS',FS),
                      *zip(shortest['omitted_names'],shortest['omitted_stop_ids'])]:
        xy=coordinates[sid]
        omitted=sid in shortest['omitted_stop_ids']
        ax.scatter(*xy,marker='x' if omitted else 'o',s=60 if omitted else 20,
                   color='red' if omitted or sid==FS else '#333333',zorder=4)
        ax.annotate(label+(' · esclusa' if omitted else ''),xy,xytext=(5,6),
                    textcoords='offset points',fontsize=8)
    ax.set_aspect(1/math.cos(math.radians(45.73)))
    ax.legend()
    tests=shortest.get('h60_timetable_comparisons_not_adopted',[])
    timing_label=('16 giri H60: nessun testimone nei casi verificati'
                  if tests and not any(t['witness_found'] for t in tests)
                  else 'orario: consultare gli esiti del confronto')
    ax.set_title('Linea 8 · estremo di distanza, NON soluzione selezionata\n'
        f"{shortest['site_count_including_fs']} siti · {shortest['annual_service_km_16_trips_260_days']:,.0f} km/anno · "
        +timing_label)
    fig.tight_layout();fig.savefig(MAP,dpi=150);plt.close(fig)


def save(result):
    OUTPUT.write_bytes(gzip.compress((json.dumps(result,sort_keys=True,ensure_ascii=False,
        separators=(',',':'))+'\n').encode('utf-8'),mtime=0))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--graph_dir',type=Path)
    p.add_argument('--walk_dir',type=Path)
    p.add_argument('--timetable',action='store_true')
    p.add_argument('--trip-count-comparison',action='store_true')
    p.add_argument('--render',action='store_true')
    p.add_argument('--time-limit',type=int,default=15)
    a=p.parse_args()
    if a.render:
        render_shortest_distance_diagnostic(json.loads(gzip.decompress(OUTPUT.read_bytes())))
        raise SystemExit(0)
    if a.trip_count_comparison:
        r=trip_count_comparison(json.loads(gzip.decompress(OUTPUT.read_bytes())),a.time_limit)
    elif a.timetable:
        r=timetable(json.loads(gzip.decompress(OUTPUT.read_bytes())),a.time_limit)
    else:
        if a.graph_dir is None or a.walk_dir is None:
            p.error('geometry requires graph_dir and walk_dir')
        r,shape=build(a.graph_dir,a.walk_dir)
        SHAPE.write_text(json.dumps(shape,sort_keys=True,ensure_ascii=False)+'\n',encoding='utf-8')
    save(r)
