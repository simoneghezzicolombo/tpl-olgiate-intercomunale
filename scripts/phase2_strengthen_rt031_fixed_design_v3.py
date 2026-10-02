"""Rebuild local engineering repairs end-to-end; do not adopt a new design.

The confirmed timetable remains authoritative. This materialises full ordered
events and blocks for the evening repair, and a separately disclosed Scarpone
road/attachment hypothesis. No weights, new uncertainty band or probability.
"""
import argparse
import copy
import gzip
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from scripts.phase2_package_rt031_confirmed_design_handoff_v3 import (
    BASE, DESIGN, OUTPUT as HANDOFF, canonical_sha256, build as handoff_build,
)
from scripts.phase2_package_rt031_current_16_trip_proposal_v3 import SOURCE, RAIL, verify_schedule
from scripts.phase2_audit_rt031_internal_transfer_margins_v3 import (
    shifted_schedule, bank_margins, flows, flow_changes,
)
from scripts.phase2_probe_rt031_line8_variable_fs_hold_v3 import wing_offsets, ordered_stop_ledger
from scripts.phase2_audit_rt031_line8_dwell_sensitivity_v3 import adjusted_loops
from scripts.phase2_complete_rt031_current_design_evidence_v3 import make_intervals, complete_trip_blocks
from scripts.phase2_probe_rt031_line8_local_counterflow_v3 import inputs, FS, VIRTUAL, NORTH
from scripts.phase2_probe_rt031_unique_line_v3 import build_graph
from scripts.phase2_probe_rt031_line8_calco_through_path_v3 import through_path, refresh_events
from scripts.phase2_audit_rt031_confirmed_route_fieldwork_v3 import audit_path
from src.phase2_rt031_rt017_transition_adapter_v3 import FrozenRT017ViaNodeAdapter

OUTPUT = BASE / 'fixed_design_strengthening_20261002.json'
SHAPE = BASE / 'scarpone_main_road_comparison_20261002.geojson'
BRIEF = ROOT / 'docs/RT031_LINEA8_RAFFORZAMENTO_INTERNO_2026_10_02.md'
CALENDAR = BASE / 'caller_confirmed_weekday_calendar_2027.json'
SCARPONE = 'ASF::OLGIATE_MOLGORA_SCARPONE'


def validate_ledger(ledger, loops, trips):
    """Require every complete trip and exact ordered occurrences, not identities."""
    expected = [(w, e['occurrence_id']) for w in ('east_A', 'west_B')
                for e in sorted(loops[w]['events'], key=lambda e: (e['path_node_index'], e['stop_place_id']))]
    if len(ledger) != len(trips):
        raise ValueError('Incomplete trip ledger')
    for row, trip in zip(ledger, trips):
        if (row['first_fs_min'], row['second_fs_min']) != (trip['first_fs_min'], trip['second_fs_min']):
            raise ValueError('Ledger FS phase drift')
        events = row['events']
        stops = [e for e in events if e['role'] == 'DESIGN_STOP_OCCURRENCE']
        if [(e['wing'], e['occurrence_id']) for e in stops] != expected:
            raise ValueError('Missing, duplicated or reordered service occurrence')
        roles = [e['role'] for e in events if e['role'] != 'DESIGN_STOP_OCCURRENCE']
        if roles != ['FULL_TRIP_START_FS', 'INTERMEDIATE_FS_STAY_ONBOARD_DESIGN', 'FULL_TRIP_END_FS']:
            raise ValueError('Vehicle movement is not the full intended passenger trip')
        last = trip['first_fs_min']
        for event in events:
            if event['role'] == 'DESIGN_STOP_OCCURRENCE':
                arrival, departure = event['alight_event_min'], event['board_event_min']
                if event['physical_boarding_authorised'] is not False:
                    raise ValueError('Model ledger cannot approve boarding')
            elif event['role'] == 'INTERMEDIATE_FS_STAY_ONBOARD_DESIGN':
                arrival, departure = event['arrival_min'], event['departure_min']
                if event['physical_continuity_certified'] is not False:
                    raise ValueError('Vehicle continuity cannot certify passenger continuity')
            elif event['role'] == 'FULL_TRIP_START_FS':
                arrival = departure = event['time_min']
            else:
                arrival = departure = event['arrival_min']
            if not all(math.isfinite(v) for v in (arrival, departure)) or arrival+1e-8 < last or departure+1e-8 < arrival:
                raise ValueError('Nonmonotone ordered passenger events')
            last = departure


def scenario_ledger(loops, trips, moving, dwell):
    if (moving, dwell) == (1.1, .5):
        ledger = ordered_stop_ledger(loops, 'east_A', trips)
    else:
        adjusted = adjusted_loops(loops, moving, dwell)
        ledger = []
        for trip in trips:
            events = [dict(role='FULL_TRIP_START_FS', time_min=trip['first_fs_min'])]
            shift = 0
            for wing, start in [('east_A', trip['first_fs_min']), ('west_B', trip['second_fs_min'])]:
                for event in sorted(adjusted[wing]['events'], key=lambda e: (e['path_node_index'], e['stop_place_id'])):
                    departure = start+event['offset_from_wing_origin_min']
                    events.append(dict(role='DESIGN_STOP_OCCURRENCE', wing=wing,
                        site_id=event['stop_place_id'], occurrence_id=event['occurrence_id'],
                        full_path_edge_index=shift+event['path_node_index'],
                        board_event_min=departure, alight_event_min=departure-dwell,
                        physical_boarding_authorised=False))
                if wing == 'east_A':
                    events.append(dict(role='INTERMEDIATE_FS_STAY_ONBOARD_DESIGN',
                        arrival_min=start+adjusted[wing]['road_minutes'],
                        departure_min=trip['second_fs_min'], physical_continuity_certified=False))
                shift += len(loops[wing]['edge_ids'])
            events.append(dict(role='FULL_TRIP_END_FS',
                arrival_min=trip['second_fs_min']+adjusted['west_B']['road_minutes']))
            ledger.append(dict(first_fs_min=trip['first_fs_min'], second_fs_min=trip['second_fs_min'], events=events))
    validate_ledger(ledger, loops, trips)
    return ledger


def complete_case(case_id, schedule, loops, source, baseline_loops, rail, days, reference):
    _, offsets = verify_schedule(schedule, loops)
    # Nine complete event ledgers are built and validated. Retain nominal and
    # slowest; hash witnesses for the other seven keep the artifact compact.
    witnesses, display = [], {}
    for (moving, dwell) in offsets:
        ledger = scenario_ledger(loops, schedule['full_trips'], moving, dwell)
        witnesses.append(dict(moving_multiplier=moving, dwell_min=dwell,
            complete_trip_count=len(ledger), ordered_nonhub_events_per_trip=28,
            ordered_event_ledger_canonical_sha256=canonical_sha256(ledger)))
        if (moving, dwell) in ((1.1,.5), (1.1,1.)):
            display['nominal' if dwell == .5 else 'slowest'] = ledger
    blocks = []
    for (moving, dwell), g in offsets.items():
        for recovery in (5,10,15):
            intervals = make_intervals(schedule['full_trips'], g['east_A']['road_minutes'], g['west_B']['road_minutes'], recovery)
            assignment = complete_trip_blocks(intervals)
            blocks.append(dict(moving_multiplier=moving, dwell_min=dwell, terminal_recovery_min=recovery,
                total_service_min_per_day=sum(t['fs_end_min']-t['fs_start_min'] for t in intervals),
                total_occupation_min_per_day=sum(t['released_after_terminal_recovery_min']-t['fs_start_min'] for t in intervals),
                **assignment))
    rail_rows = flows(schedule, offsets, rail)
    changes = flow_changes(flows(source, wing_offsets(baseline_loops), rail), rail_rows)
    lost = [r for r in changes if r['old_same_nominal_bus_feasible_all_nine'] and not r['new_same_nominal_bus_feasible_all_nine']]
    waits = [r['new_rail_to_bus_wait_min']-r['old_rail_to_bus_wait_min'] for r in changes
             if r['new_rail_to_bus_wait_min'] is not None and r['old_rail_to_bus_wait_min'] is not None]
    new_bus_to_rail_unavailable = [r for r in changes if r['old_bus_to_rail_wait_min'] is not None and r['new_bus_to_rail_wait_min'] is None]
    new_rail_to_bus_unavailable = [r for r in changes if r['old_rail_to_bus_wait_min'] is not None and r['new_rail_to_bus_wait_min'] is None]
    metres = sum(l['distance_m'] for l in loops.values())
    annual = metres*16*days/1000
    return dict(case_id=case_id, comparison_not_adopted=case_id != 'confirmed_baseline',
        exact_fs_departure_pairs_min=[[t['first_fs_min'],t['second_fs_min']] for t in schedule['full_trips']],
        full_trips=schedule['full_trips'], h30_banks=schedule['selected_real_train_banks_not_adopted'],
        event_readiness_and_complete_trip_checks_pass=True,
        all_nine_event_ledgers_rebuilt_and_validated=True, event_ledger_witnesses=witnesses,
        ordered_service_event_ledgers=display, all_27_complete_vehicle_blocks=blocks,
        maximum_conditional_vehicles=max(c['minimum_vehicle_count_conditional'] for c in blocks),
        complete_path_distance_m=metres, weekday_service_days=days, weekday_commercial_km=annual,
        delta_vs_published_reference_km=annual-reference,
        bank_margins_assumed_3min_walk=bank_margins(schedule,offsets,3),
        diagnostic_5min_walk_not_adopted=bank_margins(schedule,offsets,5),
        all_dated_rail_rows=rail_rows, wing_train_rows_checked=len(rail_rows),
        transfer_flow_combinations_checked=2*len(rail_rows), rail_flow_changes=changes,
        lost_previous_all_nine_case_bus_to_rail=lost,
        newly_unavailable_bus_to_rail=new_bus_to_rail_unavailable,
        newly_unavailable_rail_to_bus=new_rail_to_bus_unavailable,
        maximum_increase_in_rail_to_bus_wait_min=max(waits,default=0),
        physical_boarding_authorised=False, physical_passenger_continuity_certified=False,
        full_operating_cost_certified=False, rail_2027_certified=False)


def am_phase_bound(source, loops, rail, walk=3):
    """Paired flow interval, not a declared robustness margin or new target."""
    offsets = wing_offsets(loops)
    duration = max(g['east_A']['road_minutes'] for g in offsets.values())
    bank = next(b for b in source['selected_real_train_banks_not_adopted'] if b['wing']=='east_A' and b['kind']=='bus_to_rail')
    rows=[]
    for dep, target in zip(bank['bus_departures_min'],bank['rail_minutes']):
        arrivals = [t for t in rail['events'] if t['ordinary_alighting_supported'] and t['arrival_min']==dep-walk]
        if len(arrivals)!=1:
            raise ValueError('Paired arrival identity not unique')
        arrival = arrivals[0]
        target_train = next(t for t in rail['events'] if t['departure_min']==target and t['direction']=='MILANO')
        lower = arrival['arrival_min']+walk
        upper = target-duration-walk
        rows.append(dict(arriving_train_number=arrival['train_number'], arrival_min=arrival['arrival_min'],
            departing_train_number=target_train['train_number'], departure_min=target,
            earliest_bus_departure_retaining_same_arrival_flow_min=lower,
            latest_bus_departure_retaining_all_nine_case_target_min=upper,
            available_common_phase_interval_min=upper-lower,
            maximum_equal_residual_margin_by_retiming_only_min=(upper-lower)/2))
    return dict(assumed_walk_each_transfer_min=walk, worst_east_duration_min=duration, pairs=rows,
        new_service_requirement_adopted=False, normative_margin_selected=False,
        semantics='Necessary interval for the same five paired arriving/departing trains, fixed route and inherited worst duration. Half its width is the maximum possible minimum of the two residual margins if phase alone is varied continuously. Not a global infeasibility proof, demand priority or probability.')


def splice_one_event(loop, lo, hi, replacement, candidate_node, edges, wing):
    """Replace a local edge slice only after checking its service-event boundary."""
    interior=[e for e in loop['events'] if lo < e['path_node_index'] <= hi]
    if len(interior)!=1 or interior[0]['stop_place_id']!=SCARPONE:
        raise ValueError('Local splice would silently drop or move another occurrence')
    old=loop['edge_ids']
    if not replacement or edges[replacement[0]]['u_node_id']!=edges[old[lo]]['u_node_id'] or edges[replacement[-1]]['v_node_id']!=edges[old[hi-1]]['v_node_id']:
        raise ValueError('Local splice boundary drift')
    visits=[i for i,eid in enumerate(replacement,1) if edges[eid]['v_node_id']==candidate_node]
    if len(visits)!=1:
        raise ValueError('Scarpone event requires one explicitly bound occurrence')
    revised=copy.deepcopy(loop)
    revised['edge_ids']=old[:lo]+replacement+old[hi:]
    for event in revised['events']:
        index=event['path_node_index']
        if lo < index <= hi:
            event.update(path_node_index=lo+visits[0], service_node_hypothesis=candidate_node,
                site_status='REATTACHMENT_HYPOTHESIS_NOT_ADOPTED', physical_boarding_authorised=False,
                original_graph_service_point_retained=False)
        elif index>hi:
            event['path_node_index']+=len(replacement)-(hi-lo)
    refresh_events(revised,edges,wing)
    if [e['stop_place_id'] for e in revised['events']]!=[e['stop_place_id'] for e in loop['events']]:
        raise ValueError('Ordered site sequence drift')
    return revised


def road_comparison(design, graph_dir):
    paths=inputs(graph_dir)
    for key in ('edges','nodes','rules','attachments'):
        if hashlib.sha256(paths[key].read_bytes()).hexdigest()!=design['road_graph_inputs_sha256'][key]:
            raise ValueError('Confirmed graph source drift: '+key)
    raw,nodes,rules,attachments=build_graph(paths)
    edges={k:v for k,v in raw.items() if not (k+'::IN' in raw and k+'::OUT' in raw)}
    fs=attachments[FS]['graph_node_id']
    audit=audit_path(design['loops'],edges,fs,nodes)
    runs=audit['service_road_segments']
    if len(runs)!=1 or {r['site_id'] for r in runs[0]['service_events_within_run']}!={SCARPONE}:
        raise ValueError('Current sole service segment no longer matches Scarpone')
    run=runs[0]; lo=run['first_edge_index_zero_based']; hi=run['last_edge_index_zero_based']+1
    old=design['loops']['west_B']; path=old['edge_ids']
    adapter=FrozenRT017ViaNodeAdapter(edges.values(),rules,unresolved_external_via_way_count=2)
    usable={k:v for k,v in edges.items() if v['highway']!='service'}
    original=next(e for e in old['events'] if e['stop_place_id']==SCARPONE)
    old_node=edges[original['incoming_edge']]['v_node_id']
    fixed=through_path(usable,adapter,path[lo-1],path[hi],[(old_node,None)],{fs})
    bypass=through_path(usable,adapter,path[lo-1],path[hi],[],{fs})
    if fixed['reachable'] or not bypass['reachable']:
        raise ValueError('Expected explicit attachment conflict or bypass has changed')
    candidates=[]
    for i,eid in enumerate(bypass['edge_ids'],1):
        node=edges[eid]['v_node_id']; n=nodes[node]; o=nodes[old_node]
        candidates.append(dict(node_id=node,path_node_index_within_replacement=i,
            coordinates_lon_lat=[float(n['lon']),float(n['lat'])],
            graph_attachment_displacement_m=math.hypot(float(n['x'])-float(o['x']),float(n['y'])-float(o['y']))))
    # Select for *diagnostic evaluation* only: nearest graph node on this exact
    # bypass. This is not a physical stop siting or a network preference.
    evaluated=min(candidates,key=lambda c:(c['graph_attachment_displacement_m'],c['node_id']))
    revised=copy.deepcopy(design['loops'])
    revised['west_B']=splice_one_event(old,lo,hi,bypass['edge_ids'],evaluated['node_id'],edges,'west_B')
    new_audit=audit_path(revised,edges,fs,nodes)
    transitions=[]
    combined=revised['east_A']['edge_ids']+revised['west_B']['edge_ids']
    for i, nxt in enumerate(combined):
        previous=combined[i-1]
        if adapter.decision((previous,),nxt)['allowed'] is not True:
            transitions.append(dict(previous=previous,next=nxt))
    if transitions or new_audit['immediate_edge_reversals'] or new_audit['service_road_segments']:
        raise ValueError('Bypass has inadmissible represented transition, reversal or service segment')
    osm_path=graph_dir/'rt017/frozen_osm_snapshot.json.gz'
    pinned_osm=json.loads((BASE/'caller_street_exclusions.json').read_text(encoding='utf-8'))['source_sha256']['osm']
    if hashlib.sha256(osm_path.read_bytes()).hexdigest()!=pinned_osm:
        raise ValueError('Previously audited road OSM snapshot drift')
    osm=json.loads(gzip.decompress(osm_path.read_bytes()))
    ways={str(w['id']):w for w in osm['elements'] if w['type']=='way'}
    way_tags={w:ways[w].get('tags',{}) for w in sorted({edges[e]['osm_way_id'] for e in bypass['edge_ids']+path[lo:hi]})}
    def coordinates(ids):
        vertices=[edges[ids[0]]['u_node_id']]+[edges[e]['v_node_id'] for e in ids]
        return [[float(nodes[n]['lon']),float(nodes[n]['lat'])] for n in vertices]
    original_xy=coordinates(path[lo:hi]); bypass_xy=coordinates(bypass['edge_ids'])
    extent=original_xy+bypass_xy
    bounds=[min(c[0] for c in extent)-.0015,min(c[1] for c in extent)-.001,
            max(c[0] for c in extent)+.0015,max(c[1] for c in extent)+.001]
    features=[]
    source_nodes={n['id']:[n['lon'],n['lat']] for n in osm['elements'] if n['type']=='node'}
    for way in osm['elements']:
        if way['type']=='way' and way.get('tags',{}).get('highway'):
            if any(n not in source_nodes for n in way.get('nodes',[])):
                continue
            xy=[source_nodes[n] for n in way['nodes']]
            if any(bounds[0]<=x<=bounds[2] and bounds[1]<=y<=bounds[3] for x,y in xy):
                features.append(dict(type='Feature',properties=dict(role='BASEMAP_ROAD',
                    osm_way_id=str(way['id']),name=way['tags'].get('name',''),highway=way['tags']['highway']),
                    geometry=dict(type='LineString',coordinates=xy)))
    if not features:
        raise ValueError('Missing sourced street basemap')
    features += [dict(type='Feature',properties=dict(role=role),geometry=dict(type='LineString',coordinates=xy))
                 for role,xy in [('CURRENT_SERVICE_LINK',original_xy),('MAIN_ROAD_BYPASS',bypass_xy)]]
    for role,node in [('CURRENT_ATTACHMENT',old_node),('HYPOTHETICAL_ATTACHMENT',evaluated['node_id'])]:
        n=nodes[node]
        features.append(dict(type='Feature',properties=dict(role=role,site_id=SCARPONE,physical_boarding_authorised=False),
            geometry=dict(type='Point',coordinates=[float(n['lon']),float(n['lat'])])))
    evidence=dict(fixed_original_attachment_without_service_edges_reachable=False,
        bypass_without_attachment_reachable=True, original_service_slice=run,
        bypass_edge_ids=bypass['edge_ids'], bypass_distance_m=bypass['distance_m'],
        distance_delta_m=bypass['distance_m']-run['length_m'],
        running_minutes_delta_model=revised['west_B']['road_minutes']-old['road_minutes'],
        evaluated_attachment_hypothesis=evaluated, all_nodes_on_bypass_attachment_domain=candidates,
        evaluation_rule='MINIMUM_EUCLIDEAN_GRAPH_ATTACHMENT_DISPLACEMENT_ON_EXACT_BYPASS_ONLY',
        road_way_tags=way_tags, revised_route_audit=new_audit,
        represented_via_node_transition_count=len(combined), represented_via_node_violations=transitions,
        original_site_id_sequence_preserved=True, physical_stop_siting_selected=False,
        physical_attachment_adopted=False, geometry_adopted=False,
        full_history_legality_certified=False, bus_suitability_certified=False,
        source_osm_snapshot_sha256=hashlib.sha256(osm_path.read_bytes()).hexdigest(),
        semantics='Local same directed boundary comparison. Removing service classification is a diagnostic road preference, not evidence of illegality. The same stop identity requires a different event/attachment hypothesis. Graph displacement is not walking distance or an approved platform. Only represented via-node rules and no-immediate-reversal checks are certified, never full-history/bus legality.')
    return evidence,revised,dict(type='FeatureCollection',features=features)


def walking_comparison(graph_dir,walk_dir,design,road):
    """Recompute the hypothetical shifted site's actual population catchment."""
    import numpy as np
    from fractions import Fraction
    from scripts.phase2_probe_rt031_line8_retention_tradeoffs_v3 import load_access
    from scripts.phase2_measure_rt031_line8_omission_walk_v3 import ARLATE
    from scripts.phase2_audit_rt031_unique_line_walk_access_v3 import pedestrian_time
    from scripts.phase2_compare_rt031_line8_santa_calco_exchange_v3 import coverage
    from scripts.phase2_audit_rt031_conditional_new_stop_access_v3 import weighted_ratio
    paths=inputs(graph_dir)
    paths.update(matrix=walk_dir/'output/rt028_population_unit_stop_walk_matrix_v3.csv',
        pedestrian_osm=walk_dir/'input/rt028_osm_pedestrian_snapshot_v3.osm',
        candidates_normalized=paths['candidates_normalized_newlines'],
        road_screen=BASE.parent/'rt031_unique_line_road_screen_v3/screen.json',
        access_reference=BASE/'brivio_existing_sites_walk.json')
    register=json.loads(gzip.decompress((BASE/'stop_plan_and_additions.json.gz').read_bytes()))
    old_sites={r['site_id']:{'node':r['graph_node_id']} for r in register['register'] if r['site_id']!=ARLATE}
    _,_,_,context=load_access(paths,old_sites,include_context=True)
    handoff=json.loads(HANDOFF.read_text(encoding='utf-8'))
    sites={s['site_id']:s for s in handoff['design_stop_register']}
    local=context['local']
    for sid in (ARLATE,design['selected_design_stop']['site_id']):
        lon,lat=sites[sid]['coordinates_lon_lat']
        values,_=pedestrian_time(context['graph'],context['snap_map'],context['units'],lat,lon)
        local=np.minimum(local,values)
    substrate=context['substrate']
    matrix_ids=sorted(set(sites)-{VIRTUAL,NORTH,ARLATE,design['selected_design_stop']['site_id'],SCARPONE})
    base=np.minimum(local,substrate.walk_time_matrix[:,[substrate.stop_index[s] for s in matrix_ids]].min(axis=1))
    previous=np.minimum(base,substrate.walk_time_matrix[:,substrate.stop_index[SCARPONE]])
    old_cover=coverage(previous,context)
    if old_cover!=design['coverage_fraction']:
        raise ValueError('Confirmed 27-site population coverage no longer reproduces')
    lon,lat=road['evaluated_attachment_hypothesis']['coordinates_lon_lat']
    shifted,snap=pedestrian_time(context['graph'],context['snap_map'],context['units'],lat,lon)
    updated=np.minimum(base,shifted)
    new_cover=coverage(updated,context)
    def changed_population(loss):
        return {code:{str(t):str(weighted_ratio(
            ((previous<=t)&(updated>t)) if loss else ((previous>t)&(updated<=t)),
            context['weights'],context['core'] if code=='TOTAL' else context['core']&(context['codes']==code)))
            for t in (5,8,10)} for code in old_cover}
    return dict(confirmed_baseline_reproduced=True, baseline_coverage_fraction=old_cover,
        hypothesis_coverage_fraction=new_cover, hypothesis_pedestrian_snap=snap,
        change_percentage_points={c:{t:100*float(Fraction(new_cover[c][t])-Fraction(old_cover[c][t])) for t in ('5','8','10')} for c in old_cover},
        gross_previously_covered_fraction_lost=changed_population(True),
        gross_newly_covered_fraction_gained=changed_population(False),
        source_sha256={k:hashlib.sha256(paths[k].read_bytes()).hexdigest() for k in ('matrix','pedestrian_osm')},
        physical_walking_or_boarding_access_certified=False, passenger_demand_inferred=False,
        semantics='Population-weighted potential access at 5/8/10 minutes on pinned RT028 directed walking substrate; same population, original inventory matrix at Scarpone versus recomputed new point. Not ridership or safety; geographic stop identity alone does not certify coverage preservation.')


def build(graph_dir,walk_dir):
    source,design,rail,handoff,calendar=[json.loads(p.read_text(encoding='utf-8')) for p in (SOURCE,DESIGN,RAIL,HANDOFF,CALENDAR)]
    if canonical_sha256(handoff)!=canonical_sha256(handoff_build()):
        raise ValueError('Confirmed design no longer reproduces')
    # The caller's dated calendar, not a newly chosen 260-day convention.
    days=calendar['weekday_base_day_count_before_local_exceptions']
    reference=calendar['reference_published_pdb_annual_km']
    if (calendar['contract']!='RT031_CALLER_CONFIRMED_2027_WEEKDAY_BASE_MATERIALISATION_V3'
            or calendar['source_canonical_sha256'][HANDOFF.name]!=canonical_sha256(handoff)
            or days!=254 or reference!=111419):
        raise ValueError('Caller-confirmed calendar/reference drift')
    road,revised,geo=road_comparison(design,Path(graph_dir))
    coverage=walking_comparison(Path(graph_dir),Path(walk_dir),design,road)
    retimed=shifted_schedule(source,west_delay=2)
    cases=[complete_case(k,s,l,source,design['loops'],rail,days,reference) for k,s,l in (
        ('confirmed_baseline',source,design['loops']),
        ('evening_plus2_same_geometry',retimed,design['loops']),
        ('scarpone_bypass_evening_plus2',retimed,revised))]
    original_nominal=next(c for c in cases[0]['all_27_complete_vehicle_blocks'] if (c['moving_multiplier'],c['dwell_min'],c['terminal_recovery_min'])==(1.1,.5,10))
    for case in cases:
        nominal=next(c for c in case['all_27_complete_vehicle_blocks'] if (c['moving_multiplier'],c['dwell_min'],c['terminal_recovery_min'])==(1.1,.5,10))
        case['additional_nominal_service_min_per_day_vs_confirmed']=nominal['total_service_min_per_day']-original_nominal['total_service_min_per_day']
        case['additional_nominal_service_hours_2027_vs_confirmed']=case['additional_nominal_service_min_per_day_vs_confirmed']*days/60
    return dict(contract='RT031_FIXED_DESIGN_INTERNAL_STRENGTHENING_V3', recorded_on='2026-10-02',
        generator_sha256=hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
        source_canonical_sha256={p.name:canonical_sha256(v) for p,v in zip((SOURCE,DESIGN,RAIL,HANDOFF,CALENDAR),(source,design,rail,handoff,calendar))},
        rail_reference_date=rail['service_date'],road_comparison=road,walking_comparison=coverage,
        completed_comparisons=cases, am_paired_flow_phase_bound=am_phase_bound(source,design['loops'],rail),
        remaining_internal_weakness='AM_EAST_PAIRED_FLOW_MARGIN_NOT_RESOLVED_BY_PHASE_ONLY',
        design_engineering_solidification_complete=False, timetable_change_adopted=False,
        physical_operation_certified=False, rail_2027_certified=False,
        network_selected=False, primary_selection_authorised=False,runner_up_selection_authorised=False,
        decision_budget_km=None,uncertainty_band_min=None,missed_connection_probability=None,
        demand_weighted_gjt_improvement_min=None,
        semantics='One fixed proposal, bounded local repairs rebuilt through all service occurrences, all dated rail flows and complete vehicle blocks. No automatic alternative adoption, weighted winner, new threshold or invented evidence. Operator paperwork is not internal engineering closure.'),geo


def render_brief(r):
    cases=r['completed_comparisons'];road=r['road_comparison'];cov=r['walking_comparison']
    lines=['# Linea 8 — rafforzamento interno, non chiusura di carta','',
        'La base confermata resta una linea unica, 16 giri completi, 27 siti e 28 eventi non-FS; calendario feriale 2027 di 254 giorni. Nessuna modifica sotto è adottata tacitamente.','',
        '## Correzioni verificate da un capo all’altro','',
        '| Confronto | Km commerciali feriali 2027 | Margine su riferimento 111.419 | Massimo mezzi nei 27 casi | Minuti servizio nominale aggiunti/giorno |',
        '|---|---:|---:|---:|---:|']
    for c in cases:
        lines.append(f"| {c['case_id']} | {c['weekday_commercial_km']:.3f} | {-c['delta_vs_published_reference_km']:.3f} | {c['maximum_conditional_vehicles']} | {c['additional_nominal_service_min_per_day_vs_confirmed']:.3f} |")
    lines += ['', 'Sono soli km commerciali della base lunedì–venerdì, esclusi festivi nazionali; non comprendono sabato, km a vuoto o costo completo. 111.419 è il riferimento produttivo pubblicato, non un finanziamento certificato.','',
        'Ogni confronto ricostruisce e valida i 16 giri × 31 eventi per ciascuno dei nove casi marcia/dwell. Sono salvati i ledger nominale/lento, i loro hash e i 27 blocchi completi. Si ricalcolano tutte le 74 chiamate ferroviarie del 1 ottobre 2026: 148 righe e 296 flussi, Lecco/Milano e arrivo/partenza. Mezzo continuo non significa autorizzazione a restare a bordo.','',
        '**Sera +2 minuti:** cambia solo la partenza FS intermedia dei giri 9–15. La banca ovest diventa 17:37–19:37 ogni 30 minuti, margine dopo cammino assunto di 3 minuti da zero a due minuti. Nessuna precedente compatibilità bus→treno nei nove casi persa sullo stesso tracciato; alcune attese aumentano due minuti. Il servizio aumenta 14 minuti/giorno, 59,27 ore sui 254 giorni: stessi km non significa stesso costo.','',
        '**Scarpone:** Via Pilata → rotatoria → Via Como evita il tratto classificato service. Nessuna classificazione OSM prova da sola divieto o sicurezza. Il punto originale non è raggiungibile senza service nel dominio verificato; non viene dichiarato magicamente conservato.','',
        f"La deviazione aggiunge **{road['distance_delta_m']:.3f} m/giro**; l’ipotesi di attacco più vicina fra i nodi del bypass dista **{road['evaluated_attachment_hypothesis']['graph_attachment_displacement_m']:.3f} m** dal vecchio nodo. È un punto del grafo su Via Como, non una palina approvata. Il percorso completo resta senza inversioni immediate e supera tutte le transizioni via-node rappresentate; restrizioni a storia completa, sagoma e accosto non sono certificati.",'',
        '## Copertura ricalcolata, non trasferita per nome','',
        '| Comune/codice | Variazione punti % a 5 min | a 8 min | a 10 min |','|---|---:|---:|---:|']
    from scripts.phase2_build_rt031_municipal_access_frontier_v4 import MUNICIPALITY_NAMES
    for code in sorted(cov['change_percentage_points'],key=lambda c:(c=='TOTAL',c)):
        values=cov['change_percentage_points'][code]
        lines.append(f"| {MUNICIPALITY_NAMES.get(code,'Totale')} | {values['5']:+.4f} | {values['8']:+.4f} | {values['10']:+.4f} |")
    lines += ['', 'Anche le perdite e i guadagni lordi sono ricalcolati e salvati per comune e soglia: zero in questo specifico modello, non uno scambio nascosto di abitanti dietro la stessa percentuale.','',
        '## Partenze del confronto serale, non nuovo orario adottato','',
        '| Giro completo | FS inizio est, invariata | FS intermedia ovest, base | FS intermedia ovest, confronto |','|---:|---|---|---|']
    from scripts.phase2_package_rt031_confirmed_design_handoff_v3 import clock
    for i,(before,after) in enumerate(zip(cases[0]['exact_fs_departure_pairs_min'],cases[1]['exact_fs_departure_pairs_min']),1):
        lines.append(f'| {i} | {clock(before[0])} | {clock(before[1])} | {clock(after[1])} |')
    width=r['am_paired_flow_phase_bound']['pairs'][0]['available_common_phase_interval_min']
    lines += ['', 'Copertura potenziale con stessi abitanti e grafo pedonale RT028, non domanda o accessibilità fisicamente approvata. Non si pretende che 18 metri preservino una percentuale senza ricalcolarla.','',
        '## Il problema mattutino è ora circoscritto e dimostrato','',
        f"Per gli stessi cinque treni che arrivano da Milano (:02) e i cinque verso Milano (:56), la fase della stessa corsa est deve stare in un intervallo largo soltanto **{width*60:.1f} secondi**, nel caso più lento ereditato e con 3 minuti assunti per ogni trasferimento. Anche una fase continua bilanciata potrebbe offrire al massimo **{width*30:.1f} secondi per lato**. Non è una soglia adottata o una prova di impossibilità globale.",'',
        'Anticipare di quattro minuti aumenta il margine verso Milano ma perde il bus immediato per chi arriva dal treno :02. Non è rafforzamento senza contropartite. Qui serve ridurre e misurare il tempo est effettivo, oppure dichiarare esplicitamente quale collegamento accettare di peggiorare: non basta rietichettare il margine.','',
        '## Chiusura onesta','',
        'Sono chiusi i ricalcoli di questi interventi locali, non l’intero esercizio. Rimangono la fragilità AM, la verifica fisica del punto Scarpone e degli altri accosti, tempi reali/turni/deposito, treni 2027, finanziamento e sabato separato. Nessun modulo per l’operatore elimina questi buchi. Non vengono aggiunti pesi, budget o banda di incertezza.','',
        '[Evidenza macchina e registri completi](../outputs/phase2/rt031_line8_local_shortcuts_v3/fixed_design_strengthening_20261002.json). [Geometrie Scarpone](../outputs/phase2/rt031_line8_local_shortcuts_v3/scarpone_main_road_comparison_20261002.geojson).','']
    return '\n'.join(lines)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--graph-dir',type=Path,required=True)
    parser.add_argument('--walk-dir',type=Path,required=True)
    args=parser.parse_args();result,geo=build(args.graph_dir,args.walk_dir)
    for path,data in ((OUTPUT,result),(SHAPE,geo)):
        path.write_text(json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    BRIEF.write_text(render_brief(result),encoding='utf-8')
    print(json.dumps(dict(cases=[{k:c[k] for k in ('case_id','weekday_commercial_km','maximum_conditional_vehicles','additional_nominal_service_min_per_day_vs_confirmed')} for c in result['completed_comparisons']],
        road_delta_m=result['road_comparison']['distance_delta_m'],coverage_delta_pp=result['walking_comparison']['change_percentage_points']),ensure_ascii=False))
