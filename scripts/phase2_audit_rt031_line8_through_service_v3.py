"""Fixed-trip interlining frontier: vehicle blocking is not passenger permission.

No departure, road edge, budget or fleet increase is adopted. Includes only the
caller-accepted Arlate design addition; keeps the rejected flyover point out.
"""
import copy
import gzip
import json
from fractions import Fraction
import argparse

import numpy as np
from scipy.optimize import Bounds,LinearConstraint,milp
from scipy.sparse import csc_matrix,hstack,vstack

from scripts.phase2_audit_rt031_line8_stop_plan_v3 import (
    BASE,EXAMPLES,read_result,sources,PATTERNS,TIMETABLE,digest,timing_check)
from scripts.phase2_close_rt031_line8_31_trips_v3 import ROOT
from scripts.phase2_audit_rt031_line8_dwell_sensitivity_v3 import adjusted_loops
from scripts.phase2_audit_rt031_line8_independent_wings_v3 import minimum_blocks

AUTH=ROOT/'config/rt031_stop_choices_and_through_line_v3.json'
OUTPUT=BASE/'through_service_fixed_31.json.gz'
DOC=ROOT/'docs/RT031_LINEA8_CONTINUITA_INTERCOMUNALE_V3.md'


def read_result_file():
    return json.loads(gzip.decompress(OUTPUT.read_bytes()))


def inputs():
    authority=json.loads(AUTH.read_text(encoding='utf-8'))
    if (authority['accepted_design_addition_ids']!=['N1212'] or
        authority['rejected_design_addition_ids']!=['N0655'] or
        authority['operating_approval'] or authority['new_fleet_increase_accepted']):
        raise ValueError('caller scope changed; review contract')
    p=sources();r=read_result();tt=json.loads(TIMETABLE.read_text(encoding='utf-8'))
    if r['source_sha256_normalized_newlines']['timetable']!=digest(TIMETABLE):
        raise ValueError('timetable drift')
    proof=json.loads(EXAMPLES.read_text(encoding='utf-8'))
    if proof['source_sha256_normalized_newlines']!=r['source_sha256_normalized_newlines']:
        raise ValueError('addition source drift')
    addition=next(c for c in proof['examples'] if c['candidate_ids']==['N1212'])
    loops=copy.deepcopy({pat:p['family']['loops'][pat] for pat in PATTERNS})
    for pat,events in addition['added_events_by_pattern'].items():
        loops[pat]['events']+=events
        loops[pat]['events'].sort(key=lambda e:(e['path_node_index'],e['stop_place_id']))
    if timing_check(loops,p,tt)!=addition['timing'] or not addition['timing']['fixed_31_timetable_pass']:
        raise ValueError('accepted addition timing drift')
    return authority,p,r,tt,loops


def successor_edges(trips,grid,joins,recovery):
    """Common vehicle successors valid in EVERY declared timing scenario."""
    nominal=grid[1.1,.5];edges=[]
    for i,a in enumerate(trips):
        for j,b in enumerate(trips):
            if b['departure_min']<=a['departure_min'] or joins.get(a['loop']+'>'+b['loop']) is not True:
                continue
            waits=[b['departure_min']-a['departure_min']-g[a['loop']]['road_minutes'] for g in grid.values()]
            if min(waits)<recovery-1e-8:continue
            edges.append({'from_trip_index':i,'to_trip_index':j,
                'cross_wing':a['loop']!=b['loop'],
                'nominal_fs_wait_min':b['departure_min']-a['departure_min']-nominal[a['loop']]['road_minutes'],
                'scenario_fs_wait_min':min(waits),'scenario_fs_wait_max':max(waits)})
    return edges


def solve_links(trip_count,edges,vehicle_count,wait_ceiling=None,cross_only=False):
    """Maximise cross-wing links at fixed block count, no passenger/utility weights.

    The threshold bounds only cross-wing onboard waits. Same-wing layovers are
    operational, never advertised as cross-wing passenger continuation.
    """
    domain=[e for e in edges if (not cross_only or e['cross_wing']) and
            (not e['cross_wing'] or wait_ceiling is None or e['scenario_fs_wait_max']<=wait_ceiling+1e-8)]
    required=trip_count-vehicle_count
    if not domain:
        return None if required else {'links':[],'vehicle_count':trip_count,'cross_wing_count':0}
    rows=[];cols=[];data=[]
    for k,e in enumerate(domain):
        for row in (e['from_trip_index'],trip_count+e['to_trip_index'],2*trip_count):
            rows.append(row);cols.append(k);data.append(1.)
    matrix=csc_matrix((data,(rows,cols)),shape=(2*trip_count+1,len(domain)))
    lower=np.r_[np.zeros(2*trip_count),required];upper=np.r_[np.ones(2*trip_count),required]
    answer=milp(-np.array([int(e['cross_wing']) for e in domain],dtype=float),
        integrality=np.ones(len(domain)),bounds=Bounds(0,1),
        constraints=LinearConstraint(matrix,lower,upper),options={'time_limit':20,'mip_rel_gap':0})
    if answer.status==2:return None
    if answer.status!=0 or answer.x is None:raise ValueError('inconclusive blocking solver')
    if max(abs(answer.x-np.rint(answer.x)))>1e-6:raise ValueError('fractional blocking')
    chosen=[e for e,x in zip(domain,answer.x) if x>.5]
    if len(chosen)!=required or len({e['from_trip_index'] for e in chosen})!=required or len({e['to_trip_index'] for e in chosen})!=required:
        raise ValueError('invalid path cover')
    return {'links':chosen,'vehicle_count':vehicle_count,'cross_wing_count':sum(e['cross_wing'] for e in chosen)}


def through_frontier(trips,edges,vehicle_count):
    """Exact finite frontier: maximum continuation count vs worst onboard FS wait.

    Enumerates observed feasible-link wait breakpoints, not arbitrary acceptable
    passenger thresholds. A witness is not an adopted operating plan.
    """
    points=[];best=-1
    for ceiling in sorted({0.}|{e['scenario_fs_wait_max'] for e in edges if e['cross_wing']}):
        plan=solve_links(len(trips),edges,vehicle_count,ceiling)
        if plan is not None and plan['cross_wing_count']>best:
            best=plan['cross_wing_count']
            plan['max_cross_wing_fs_wait_min']=max((e['scenario_fs_wait_max'] for e in plan['links'] if e['cross_wing']),default=0.)
            points.append(plan)
    return points


def plan_blocks(trips,links):
    nxt={e['from_trip_index']:e['to_trip_index'] for e in links}
    previous={e['to_trip_index'] for e in links};blocks=[]
    for i in range(len(trips)):
        if i in previous:continue
        block=[i]
        while block[-1] in nxt:block.append(nxt[block[-1]])
        blocks.append(block)
    if sorted(i for b in blocks for i in b)!=list(range(len(trips))):raise ValueError('invalid vehicle chain')
    return blocks


def passenger_ledger(trips,plan,route_id):
    """Explicit proposed passenger continuation; physical vehicle alone is insufficient."""
    blocks=plan_blocks(trips,plan['links'])
    vehicles={i:f'VEHICLE_BLOCK_{k+1:02d}' for k,b in enumerate(blocks) for i in b}
    ledger=[]
    for e in plan['links']:
        i,j=e['from_trip_index'],e['to_trip_index']
        ledger.append({**e,'from_vehicle_block_id':vehicles[i],'to_vehicle_block_id':vehicles[j],
            'from_design_route_id':route_id,'to_design_route_id':route_id,
            'passenger_continuation_planned':e['cross_wing'],
            'remain_onboard_planned':e['cross_wing'],
            'requires_vehicle_change_in_plan':False if e['cross_wing'] else None,
            'physical_continuation_certified':False,'operating_authorisation':False})
    return blocks,ledger


def through_permission(link):
    return (link.get('cross_wing') is True and link.get('passenger_continuation_planned') is True
        and link.get('remain_onboard_planned') is True
        and bool(link.get('from_vehicle_block_id'))
        and link['from_vehicle_block_id']==link.get('to_vehicle_block_id')
        and bool(link.get('from_design_route_id'))
        and link['from_design_route_id']==link.get('to_design_route_id')
        and link.get('requires_vehicle_change_in_plan') is False)


def journeys(trips,grid,ledger):
    """Ordered cross-wing rides, retaining worst-case time and boarding occurrences.

    These are model opportunities, not demand, empirical reliability or approved
    platform journeys. Per OD and incoming trip, board the LAST origin occurrence
    and alight at the FIRST destination occurrence. No internal trip teleportation.
    """
    rows=[];nominal=grid[1.1,.5]
    for link in ledger:
        if not through_permission(link):continue
        i,j=link['from_trip_index'],link['to_trip_index'];a,b=trips[i],trips[j]
        origins={e['stop_place_id'] for e in nominal[a['loop']]['events']}
        destinations={e['stop_place_id'] for e in nominal[b['loop']]['events']}
        for sid in sorted(origins):
            for did in sorted(destinations):
                if sid==did:continue
                metrics=[]
                for (moving,dwell),loops in grid.items():
                    source=max((e for e in loops[a['loop']]['events'] if e['stop_place_id']==sid),key=lambda e:e['path_node_index'])
                    dest=min((e for e in loops[b['loop']]['events'] if e['stop_place_id']==did),key=lambda e:e['path_node_index'])
                    board=a['departure_min']+source['offset_from_wing_origin_min']
                    alight=b['departure_min']+dest['offset_from_wing_origin_min']-dwell
                    metrics.append((moving,dwell,board,alight,alight-board,source['occurrence_id'],dest['occurrence_id']))
                nom=next(m for m in metrics if m[:2]==(1.1,.5))
                rows.append({'origin_site_id':sid,'destination_site_id':did,'from_trip_index':i,'to_trip_index':j,
                    'boarding_occurrence_id':nom[5],'alighting_occurrence_id':nom[6],
                    'nominal_boarding_min':nom[2],'nominal_alighting_min':nom[3],
                    'nominal_elapsed_min':nom[4],'scenario_elapsed_min':min(m[4] for m in metrics),
                    'scenario_elapsed_max':max(m[4] for m in metrics),
                    'nominal_onboard_fs_wait_min':link['nominal_fs_wait_min'],
                    'design_transfer_count':0,'physical_journey_certified':False})
    return rows


def build():
    authority,p,stops,tt,loops=inputs();trips=tt['trips']
    allgrid={key:adjusted_loops(loops,*key) for key in p['adjusted']}
    modes=[('nominal', {(1.1,.5):allgrid[1.1,.5]},10,4),
           ('entire_nine_case_grid_with_15min_recovery',allgrid,15,6)]
    diagnostics=[]
    alternating={a+'>'+b:a!=b and p['family']['joins'][a+'>'+b] for a in PATTERNS for b in PATTERNS}
    # Twenty-seven separate minima are diagnostics, not one fixed duty plan.
    pure_grid=[{'moving_multiplier':m,'dwell_min':d,'recovery_min':recovery,
        **minimum_blocks(trips,g,alternating,recovery)}
        for (m,d),g in allgrid.items() for recovery in (5,10,15)]
    for name,grid,recovery,fleet in modes:
        edges=successor_edges(trips,grid,p['family']['joins'],recovery)
        frontier=through_frontier(trips,edges,fleet)
        if not frontier:raise ValueError('baseline vehicle count cannot be reconstructed')
        example=copy.deepcopy(frontier[-1])
        blocks,ledger=passenger_ledger(trips,example,authority['design_route_identity'])
        diagnostic={'case':name,'recovery_min':recovery,'vehicle_count_comparison':fleet,
            'timing_scenarios':[list(k) for k in grid],
            'pure_alternation_possible_at_this_fleet':solve_links(len(trips),edges,fleet,cross_only=True) is not None,
            'frontier':frontier,'maximum_continuation_example':{**example,
                'trip_index_blocks':blocks,'ordered_continuation_ledger':ledger,
                'no_cross_wing_continuation_after_trip_indices':[i for i in range(len(trips)) if not any(e['from_trip_index']==i and through_permission(e) for e in ledger)],
                'journeys':journeys(trips,grid,ledger)},
            'operating_plan_adopted':False}
        if name=='nominal':
            # Concrete illustration at an actual frontier breakpoint, not an
            # accepted wait threshold or adopted operating plan.
            point=next(f for f in frontier if f['cross_wing_count']==20)
            b,l=passenger_ledger(trips,point,authority['design_route_identity'])
            diagnostic['illustrative_20_link_plan']={**point,'trip_index_blocks':b,
                'ordered_continuation_ledger':l,'journeys':journeys(trips,grid,l),
                'scope':'Disclosed 20-link frontier example; 24.84 minutes is its achieved bound, not a caller-approved wait limit.',
                'operating_plan_adopted':False}
        diagnostics.append(diagnostic)
        print(name,[(f['cross_wing_count'],round(f['max_cross_wing_fs_wait_min'],2)) for f in frontier],flush=True)
    arlate=next(c for c in stops['single_additions'] if c['candidate_id']=='N1212')
    design_stops=copy.deepcopy(stops['register'])
    design_stops.append({'number':29,'site_id':'PROXY::RT031_ADDITIONAL::'+arlate['node_id'],
        'source_candidate_id':'N1212','name':'Arlate — Via Nuova Provinciale (progetto)',
        'road_coordinates':arlate['coordinates'],'status':'CALLER_ACCEPTED_DESIGN_ADDITION_NOT_OPERATIONALLY_APPROVED',
        'physical_platform_side':None,'platform_count':None,'boarding_authorised':False,
        'occurrences':[e for e in loops['east_A']['events'] if e['stop_place_id']=='PROXY::RT031_ADDITIONAL::'+arlate['node_id']]})
    trip_ledger=[{**t,'trip_index':i,'fs_return_nominal_min':t['departure_min']+allgrid[1.1,.5][t['loop']]['road_minutes'],
        'events_nominal':[{**e,'departure_min':t['departure_min']+e['offset_from_wing_origin_min']}
                         for e in allgrid[1.1,.5][t['loop']]['events']]}
        for i,t in enumerate(trips)]
    return {'contract':'RT031_EXPLICIT_THROUGH_SERVICE_FIXED_31_AUDIT_V3',
        'source_sha256_normalized_newlines':{'authority':digest(AUTH),'timetable':digest(TIMETABLE),
            'addition_examples':digest(EXAMPLES),'counterflow':digest(BASE/'local_counterflow.json')},
        'accepted_design_addition_ids':['N1212'],'rejected_design_addition_ids':['N0655'],
        'proposed_site_count_including_fs':29,'new_site_boarding_authorised':False,
        'current_design_stop_register':design_stops,'current_design_trip_ledger':trip_ledger,
        'baseline_potential_access_fraction':stops['baseline_potential_access_fraction'],
        'current_potential_access_fraction':arlate['potential_access_fraction'],
        'municipality_names':stops['municipality_names'],
        'design_route_identity':authority['design_route_identity'],'operator_route_id':None,
        'trips':trips,'annual_service_km':tt['annual_service_km'],'extra_service_km':0,
        'geometry_changed':False,'departures_changed':False,'accepted_addition_timing_check':timing_check(loops,p,tt),
        'pure_alternation_27_separate_scenario_minima':pure_grid,'cases':diagnostics,
        'semantics':'Fixed 31 trips with Arlate design addition. Exact matching frontier of cross-wing continuation count versus worst FS onboard wait at declared fleet/timing conditions. No passenger weights or acceptable wait threshold. Example is the maximum continuation endpoint, not a globally preferred service plan. Vehicle assignment and intended stay-onboard permission are separate fields; no physical/operating approval follows.',
        'limits':['No empirical missed-connection probability or passenger demand',
            'Existing service sites inherit optimistic boarding occurrence assumptions',
            'FS through joins only have represented via-node compatibility; full restriction history, bus swept paths, platform permissions, accessible boarding and recovery with passengers on board remain unverified',
            'No depot movements, driver duties, capacity or full operating costs',
            'Cross-wing journey time includes the FS layover; same vehicle does not imply a fast journey',
            'No proof over retimed departures, different paths, other calendars or all possible operating plans'],
        'physical_passenger_continuity_certified':False,'operating_plan_adopted':False,
        'new_fleet_increase_accepted':False,'decision_budget_km':None,'uncertainty_band_min':None,
        'network_selected':False,'primary_selection_authorised':False,'runner_up_selection_authorised':False}


def clock(minute):
    minute=round(minute);return f'{minute//60:02d}:{minute%60:02d}'


def middle_schedules(start,end,count,limit):
    """Exhaust exact five-minute departure choices under the inherited gap bound."""
    if count==0:
        return [[]] if end-start<=limit else []
    result=[]
    for minute in range(start+5,min(end-5,start+limit)+1,5):
        if end-minute>(count)*limit:continue
        result.extend([[minute]+tail for tail in middle_schedules(minute,end,count-1,limit)])
    return result


def middle_retiming_comparison():
    """Only the existing five central departures move; all peak/rail banks fixed.

    This is a separately declared bounded comparison, not automatic replacement
    of the current timetable. It retains 155/120-minute offpeak bounds.
    """
    _,p,_,tt,loops=inputs()
    nominal=adjusted_loops(loops,1.1,.5);severe=adjusted_loops(loops,1.1,1.)
    alternating={a+'>'+b:a!=b and p['family']['joins'][a+'>'+b] for a in PATTERNS for b in PATTERNS}
    fixed=[t for t in tt['trips'] if not (540<t['departure_min']<995 and t['loop']=='west_B')
           and not (545<t['departure_min']<995 and t['loop']=='east_A')]
    west=middle_schedules(540,995,2,155);east=middle_schedules(545,995,3,120)
    results=[]
    for w in west:
        for e in east:
            trips=sorted(fixed+[{'loop':pat,'departure_min':minute} for pat,times in [('west_B',w),('east_A',e)] for minute in times],
                         key=lambda t:(t['departure_min'],t['loop']))
            nominal_count=minimum_blocks(trips,nominal,alternating,10)['minimum_vehicle_count_conditional']
            severe_count=minimum_blocks(trips,severe,alternating,15)['minimum_vehicle_count_conditional']
            results.append({'west_central_departures_min':w,'east_central_departures_min':e,
                'pure_alternating_nominal_vehicles':nominal_count,'pure_alternating_severe_vehicles':severe_count,
                'unrestricted_nominal_vehicles':minimum_blocks(trips,nominal,p['family']['joins'],10)['minimum_vehicle_count_conditional'],
                'trips':trips})
    return {'scope':'Only 2 west and 3 east central departures retimed on five-minute grid; unchanged first/last, peak banks and 155/120 departure-gap limits. No global or continuous-time optimality claim.',
        'bound_semantics':'Necessary departure-gap relaxation. All 504 cases are used to establish a lower bound on pure-alternating fleet, not promoted to fully checked passenger timetables. The unchanged validated base attains the reported minima.',
        'west_alternative_count':len(west),'east_alternative_count':len(east),'cases':results,
        'minimum_pure_alternating_nominal_vehicles':min(c['pure_alternating_nominal_vehicles'] for c in results),
        'minimum_pure_alternating_severe_vehicles':min(c['pure_alternating_severe_vehicles'] for c in results),
        'retiming_adopted':False}


def joint_retiming_comparison(time_limit=45,vehicle_count=4,fs_wait_limit=None):
    """Test joint dispatch and alternating vehicle blocks without freezing peak banks.

    Keep ALL existing site-ready H30, rail eligibility, counts, first/last,
    155/120 limits and nominal four-vehicle conditions. Continuous matching
    variables only relax implementation of a bipartite path cover; independently
    reconstruct an integral matching before accepting any witness.
    """
    from scripts.phase2_close_rt031_line8_31_trips_v3 import constraints
    _,p,_,tt,loops=inputs();p=copy.deepcopy(p)
    p['family']['loops']=loops
    p['adjusted']={key:adjusted_loops(loops,*key) for key in p['adjusted']}
    # Rebuild rail trip eligibility after adding the Arlate dwell; include the
    # new site explicitly instead of reusing the old 297 eligibility sets.
    targets=sorted({(a['wing'],a['kind'],a['rail_min']) for a in p['anchors']})
    anchors=[]
    for wing,kind,minute in targets:
        pat=next(k for k in loops if k.startswith(wing));eligible=[]
        for i,t in enumerate(p['trips']):
            if t['loop']!=pat:continue
            residual=[minute-t['departure_min']-g[pat]['road_minutes']-3 for g in p['adjusted'].values()]
            ok=all(-1e-8<=v<=p['wait_ceiling']+1e-8 for v in residual) if kind=='bus_to_rail' else 3<=t['departure_min']-minute<=8
            if ok:eligible.append(i)
        for sid in sorted({e['stop_place_id'] for e in loops[pat]['events']}):
            anchors.append({'wing':wing,'kind':kind,'rail_min':minute,'stop_place_id':sid,'eligible':tuple(eligible)})
    p['anchors']=anchors
    matrix,lo,hi,lower=constraints(p,tt['wait_limit_min_by_pattern'])
    # Only rows with upper bound four are the inherited instantaneous fleet
    # constraints (counts are 15/16; cover rows have infinite upper bounds).
    if vehicle_count!=4:
        from scripts.phase2_solve_rt031_line8_joint_evening_v3 import occupied_sets
        if sum(hi==4)!=len(occupied_sets(p['candidate_trips_31'],p['adjusted'][1.1,.5],10)):
            raise ValueError('fleet row identification drift')
        hi=hi.copy();hi[hi==4]=vehicle_count
    trips=p['candidate_trips_31'];n=len(trips)
    alternate={a+'>'+b:a!=b and p['family']['joins'][a+'>'+b] for a in loops for b in loops}
    edges=successor_edges(trips,{(1.1,.5):p['adjusted'][1.1,.5]},alternate,10)
    if fs_wait_limit is not None:
        edges=[e for e in edges if e['nominal_fs_wait_min']<=fs_wait_limit+1e-8]
    m=len(edges)
    rows=list(range(2*n));cols=list(range(n))*2;data=[-1.]*(2*n)
    for k,e in enumerate(edges):
        for row in (e['from_trip_index'],n+e['to_trip_index'],2*n):
            rows.append(row);cols.append(n+k);data.append(1.)
    joins=csc_matrix((data,(rows,cols)),shape=(2*n+1,n+m))
    full=vstack([hstack([matrix,csc_matrix((matrix.shape[0],m))]),joins],format='csc')
    answer=milp(np.zeros(n+m),integrality=np.r_[np.ones(n),np.zeros(m)],
        bounds=Bounds(np.r_[lower,np.zeros(m)],np.ones(n+m)),
        constraints=LinearConstraint(full,np.r_[lo,np.full(2*n,-np.inf),31-vehicle_count],np.r_[hi,np.zeros(2*n),31-vehicle_count]),
        options={'time_limit':time_limit,'mip_rel_gap':0})
    result={'scope':'Joint five-minute departure grid, full original site-ready and rail constraints recompiled for Arlate, 31 trips, first/last, same 155/120 limits, pure alternating blocks and simultaneous vehicle occupation at the explicitly compared vehicle count. No all-day clockface constraint. No new km, relaxed rail targets or phase-window shifts.',
        'vehicle_count_comparison':vehicle_count,'nominal_fs_wait_ceiling_comparison':fs_wait_limit,
        'solver_status':int(answer.status),'infeasible_in_declared_domain':answer.status==2,
        'time_limit_seconds':time_limit,'departure_candidate_count':n,'vehicle_successor_candidate_count':m,
        'witness_found':False,'retiming_adopted':False}
    if answer.x is not None:
        if max(abs(answer.x[:n]-np.rint(answer.x[:n])))>1e-6:raise ValueError('fractional dispatch witness')
        selected=sorted([t for t,x in zip(trips,answer.x[:n]) if x>.5],key=lambda t:(t['departure_min'],t['loop']))
        if len(selected)!=31:raise ValueError('dispatch count drift')
        check=timing_check(loops,p,{**tt,'trips':selected})
        cover=minimum_blocks(selected,p['adjusted'][1.1,.5],alternate,10)
        other_failures={k:v for k,v in check['failure_counts'].items() if k!='NOMINAL_FLEET'}
        if other_failures or check['nominal_vehicle_count']>vehicle_count or cover['minimum_vehicle_count_conditional']>vehicle_count:
            raise ValueError('joint witness fails independent passenger or integral matching verification')
        witnessed_edges=successor_edges(selected,{(1.1,.5):p['adjusted'][1.1,.5]},alternate,10)
        plan=solve_links(31,witnessed_edges,vehicle_count,fs_wait_limit,True)
        if plan is None:raise ValueError('integral bounded-wait path cover absent')
        blocks,ledger=passenger_ledger(selected,plan,'LINEA_8_DESIGN')
        result.update(witness_found=True,trips=selected,independent_timing_check=check,
            preserves_original_four_vehicle_timing_contract=check['fixed_31_timetable_pass'],
            alternating_blocks=blocks,links=ledger,
            achieved_max_nominal_fs_wait_min=max(e['nominal_fs_wait_min'] for e in ledger))
    if answer.status not in (0,1,2):raise ValueError('joint solver failed')
    return result


def five_vehicle_wait_comparison():
    """Unapproved fifth vehicle: minimum worst FS wait, not an assumed solution."""
    _,p,_,_,loops=inputs();nominal=adjusted_loops(loops,1.1,.5)
    # All exact feasible wait breakpoints on the existing five-minute grid.
    alternating={a+'>'+b:a!=b and p['family']['joins'][a+'>'+b] for a in loops for b in loops}
    edges=successor_edges(p['candidate_trips_31'],{(1.1,.5):nominal},alternating,10)
    cutoffs=sorted({e['nominal_fs_wait_min'] for e in edges});lo=0;hi=len(cutoffs)-1;checks=[]
    initial=joint_retiming_comparison(vehicle_count=5,fs_wait_limit=cutoffs[hi]);checks.append(initial)
    if not initial['witness_found']:
        return {'checks':checks,'minimum_proven':False,'fleet_increase_adopted':False}
    witness=initial
    while lo<hi:
        mid=(lo+hi)//2
        test=joint_retiming_comparison(vehicle_count=5,fs_wait_limit=cutoffs[mid]);checks.append(test)
        if test['witness_found']:hi=mid;witness=test
        elif test['infeasible_in_declared_domain']:lo=mid+1
        else:return {'checks':checks,'minimum_proven':False,'fleet_increase_adopted':False}
    return {'checks':checks,'minimum_proven':True,'minimum_maximum_nominal_fs_wait_min':cutoffs[lo],
        'witness':witness,'fleet_increase_adopted':False,
        'semantics':'Five alternating vehicle blocks and up to five simultaneous occupied trips compared, not approved. Exact bounded-grid minimax FS onboard wait, not a global or accepted operating optimum.'}


def report(r):
    nominal=r['cases'][0];robust=r['cases'][1];example=nominal['illustrative_20_link_plan']
    lines=['# Linea 8 — continuità fra le ali e viaggi intercomunali','',
        '**Chiarimento successivo: il committente richiede lo stesso percorso completo per tutte le corse, '
        'senza corse limitate a FS.** L’audit qui sotto resta diagnostica del precedente schema a corse d’ala, '
        'non la soluzione richiesta. Il requisito di alternare ogni riuso fisico del mezzo non equivale '
        'a definire tutte le corse commerciali sull’otto completo. '
        '[Ricostruzione nel contratto corretto](RT031_LINEA8_PERCORSO_UNICO_COMPLETO_V3.md).','',
        '**Scelte registrate:** sì alla nuova fermata nell’area di Arlate (N1212) come scelta di progetto; '
        'no a N0655 in Via Indipendenza a Olgiate, segnalata dal committente sul cavalcavia. '
        'Non viene spostata automaticamente prima o dopo. Olgiate sud e San Zeno già presenti restano inclusi. '
        'La verifica delle manovre è rimandata, non cancellata.','',
        'La base del confronto storico comprende **29 siti di progetto**, non 29 paline autorizzate: i 28 precedenti più Arlate. '
        '**31 giri d’ala e 111.460,883 km di servizio/anno su 260 giorni ipotizzati**, senza nuove deviazioni. '
        'L’aggiunta mantiene nei test H30 nelle punte, limiti centrali e 308 controlli ferroviari per sito. '
        'Il residuo ferroviario minimo rimane circa 50 secondi oltre i tre minuti ipotizzati per il cambio.','',
        'Il sito **29** è Arlate — Via Nuova Provinciale: coordinate indicative del nodo stradale '
        '**45.727365, 9.442071**, non il progetto di una palina. Il registro completo aggiornato e '
        'gli eventi ricalcolati delle 31 corse sono nel file macchina collegato in fondo.',
        '',
        'Copertura potenziale a piedi entro dieci minuti, con **solo** la nuova Arlate:',
        '',
        '| Comune | Base precedente | Progetto con Arlate |','|---|---:|---:|',
        *[f"| {name} | {100*float(Fraction(r['baseline_potential_access_fraction'][m]['10'])):.2f}% | {100*float(Fraction(r['current_potential_access_fraction'][m]['10'])):.2f}% |" for m,name in r['municipality_names'].items()],
        '',
        'Sono percentuali di accessibilità spaziale potenziale, non previsioni di passeggeri. '
        'Il beneficio della proposta esclusa a Olgiate non viene più conteggiato.','',
        '## Una linea unica non è soltanto il nome','',
        'L’intento del committente è **una Linea 8 riconoscibile anche per gli spostamenti tra paesi**. '
        'Il modello precedente aveva due elenchi di partenze indipendenti da FS. '
        'Ora ogni prosecuzione studiata indica autobus, corsa successiva, identità di servizio e '
        'permesso **proposto** di rimanere a bordo. Un semplice riuso dello stesso mezzo non viene contato come viaggio diretto.',
        '',
        'Le prosecuzioni sono **testimoni ingegneristici, non ancora un orario pubblico adottato**. '
        'Il passeggero deve poter effettivamente restare a bordo durante la sosta e il collegamento stradale a FS; '
        'né questo, né accessi, manovre o restrizioni complete sono già certificati.','',
        '## Risultato sullo stesso orario, senza nuovi km','',
        '| Condizione | Mezzi nominali | Mezzi nel caso più severo | Significato |',
        '|---|---:|---:|---|',
        '| Due ali con riuso libero del mezzo | 4 | 6 | Nessuna continuità passeggeri implicita |',
        '| Ogni concatenamento del mezzo deve alternare ala | 5 | 7 | Alternanza sistematica; le soste possono comunque essere lunghe |',
        '',
        'La seconda riga è un confronto, **non l’approvazione di un quinto o settimo autobus**. '
        'Ogni mezzo può iniziare e terminare il servizio: nemmeno l’alternanza sistematica promette '
        'una prosecuzione dopo l’ultima corsa di ciascun blocco. I 27 minimi per scenario non sono '
        'un unico piano operativo valido in ogni scenario.','',
        '### Quattro mezzi: quante prosecuzioni, con quale sosta a FS?','',
        'La tabella è la frontiera esatta del dominio a partenze fissate. '
        'Non usa pesi tra passeggeri o comuni né una soglia arbitraria di attesa accettabile. '
        'Il numero conta concatenamenti fra corse, **non percentuale di passeggeri serviti**.',
        '',
        '| Prosecuzioni fra ali al giorno | Peggiore sosta a bordo a FS, nominale |',
        '|---|---:|']
    for f in nominal['frontier']:
        lines.append(f"| {f['cross_wing_count']} | {f['max_cross_wing_fs_wait_min']:.2f} min |")
    lines+=['',
        '**Esempio concreto a 20 prosecuzioni:** quattro blocchi mezzo, soste a FS da '
        f"{min(e['nominal_fs_wait_min'] for e in example['links'] if e['cross_wing']):.2f} a "
        f"{example['max_cross_wing_fs_wait_min']:.2f} minuti. Gli altri 11 giri d’ala **non** hanno una prosecuzione "
        'diretta verso l’altra ala in questo esempio. Le sette concatenazioni sullo stesso lato '
        'sono movimenti/riusi del mezzo, non viaggi intercomunali garantiti.',
        '',
        'La soglia di circa 25 minuti è un **risultato di questo esempio**, non una preferenza già approvata. '
        'Il massimo di 26 prosecuzioni richiede invece fino a 199,84 minuti di sosta: '
        '**non è una proposta di buon servizio**, anche se tecnicamente il mezzo potrebbe proseguire.',
        '',
        '### Concatenamenti passeggeri dell’esempio a 20','',
        'Le ore sono le partenze delle due corse da FS. Fra esse il mezzo percorre la prima ala, '
        'rientra a FS, sosta e parte nell’altra. Non sono due partenze consecutive a distanza di pochi minuti.',
        '',
        '| Prima ala: partenza FS | Rientro FS nominale | Prosegue nell’altra ala alle | Sosta a FS |',
        '|---|---|---|---|']
    for e in example['ordered_continuation_ledger']:
        if not through_permission(e):continue
        a=r['trips'][e['from_trip_index']];b=r['trips'][e['to_trip_index']]
        label='Ovest' if a['loop']=='west_B' else 'Est'
        arrival=b['departure_min']-e['nominal_fs_wait_min']
        lines.append(f"| {label} {clock(a['departure_min'])} | {clock(arrival)} | {clock(b['departure_min'])} | {e['nominal_fs_wait_min']:.1f} min |")
    lines+=['','### Tempi per chi non va in stazione','',
        'Viaggi diretti nominali nell’esempio a 20, con imbarco in punta mattutina 07–09; '
        'includono **tutta la sosta a FS**. Non sono tempi porta-a-porta, frequenze garantite fra le ali '
        'o medie ponderate per domanda. Ogni viaggio conserva gli identificativi delle due occorrenze.',
        '',
        '| Collegamento | Durata a bordo, compresa sosta FS | Sosta FS compresa |',
        '|---|---|---|']
    pairs=[('ASF::ROVAGNATE_STRADA_STATALE_AGIP','ASF::BRIVIO_BAR_CRISTALLO','Rovagnate AGIP → Brivio Via Como'),
        ('ASF::BRIVIO_BAR_CRISTALLO','ASF::ROVAGNATE_STRADA_STATALE_AGIP','Brivio Via Como → Rovagnate AGIP'),
        ('RT031::P2V2S_0031_PROJECTED_ROAD_POINT','PROXY::RT031_ADDITIONAL::n:534398.29:5063851.64','Olgiate sud → nuova Arlate'),
        ('PROXY::RT031_ADDITIONAL::n:534398.29:5063851.64','RT031::P2V2S_0031_PROJECTED_ROAD_POINT','Nuova Arlate → Olgiate sud'),
        ('PROXY::SAN_ZENO_VIA_CANTU_ROAD_NODE','RT031::P2V2S_0031_PROJECTED_ROAD_POINT','San Zeno → Olgiate sud')]
    for a,b,label in pairs:
        rows=[j for j in example['journeys'] if j['origin_site_id']==a and j['destination_site_id']==b and 420<=j['nominal_boarding_min']<=540]
        if rows:lines.append(f"| {label} | {min(j['nominal_elapsed_min'] for j in rows):.1f}–{max(j['nominal_elapsed_min'] for j in rows):.1f} min | {min(j['nominal_onboard_fs_wait_min'] for j in rows):.1f}–{max(j['nominal_onboard_fs_wait_min'] for j in rows):.1f} min |")
    lines+=['',
        '**Restare a bordo elimina il cambio, non accorcia automaticamente il viaggio.** '
        'L’H30 già verificato riguarda i viaggi verso/dalla stazione: non viene esteso per etichetta '
        'a tutti i viaggi fra ali. Il registro pubblica anche le corse senza prosecuzione.','',
        '## Stress: non confondere quattro mezzi nominali con una garanzia','',
        'Con sei blocchi fissi compatibili con tutti i nove scenari e 15 minuti di recupero, '
        'la frontiera cambia: 16 prosecuzioni richiedono fino a 62,87 minuti di sosta '
        'nel caso di arrivo più anticipato; il recupero è verificato anche con l’arrivo più tardo. '
        'Il massimo di 24 richiede 332,87 minuti. '
        'Non sono probabilità di ritardo e non sono prestazioni da proporre al pubblico. '
        'Un blocco valido nel nominale non è automaticamente valido nello stress.','',
        '## Abbiamo provato anche a spostare le corse centrali','',
        'Enumerate **6 combinazioni ovest × 84 est = 504**, spostando soltanto le due partenze centrali '
        'ovest e le tre est ogni cinque minuti. Rimangono fermi punte, prime/ultime, 31 corse '
        'e i limiti fra partenze di 155/120 minuti. Anche in questo dominio il minimo per '
        'concatenamenti sempre alternati è **5 nominali / 7 severi**. '
        'È una prova su una rilassata necessaria, non la certificazione di tutti i 504 orari: '
        'includere anche eventuali casi non ammissibili rende il limite inferiore prudente. '
        'La base invariata, già verificata, raggiunge entrambi i minimi. '
        'Non è un’impossibilità globale su altri orari o requisiti.']
    if 'joint_retiming_comparison' in r:
        joint=r['joint_retiming_comparison'];five=r['five_vehicle_wait_comparison']
        lines+=['','## Ricontrollo congiunto: anche le partenze di punta possono muoversi','',
            'Non ci siamo fermati ai 504 casi centrali: il modello congiunto considera '
            f"**{joint['departure_candidate_count']} partenze possibili e {joint['vehicle_successor_candidate_count']} concatenamenti**. "
            'Le partenze possono cambiare ogni cinque minuti anche in punta, ma restano H30 per sito, '
            'gli obiettivi ferroviari ricalcolati con Arlate, 31 corse, prime/ultime, '
            'limiti centrali 155/120 e quattro mezzi nominali. Non è imposta la regolarità dei minuti.',
            '',
            f"Esito: **{'nessuna soluzione con concatenamenti sempre alternati' if joint['infeasible_in_declared_domain'] else 'vedere il testimone nel file macchina'}** "
            'nel dominio dichiarato. Non è quindi solo un difetto dei minuti della tabella corrente.',
            '',
            '**Confronto separato, non approvato, con cinque mezzi:** '
            +(f"anche ottimizzando la peggiore sosta, il minimo nel dominio è **{five['minimum_maximum_nominal_fs_wait_min']:.2f} minuti** "
              'per concatenamenti tutti alternati. La verifica ricalcola le opportunità passeggeri e ricostruisce '
              'blocchi interi: non accetta flussi frazionari del risolutore come autobus. '
              'Questo dimostra perché aggiungere un autobus non basta a produrre una buona linea continua.'
              if five['minimum_proven'] else 'ricerca non conclusiva; nessun minimo dichiarato.'),
            '',
            'Queste sono prove su un requisito **più forte del solo nome unico**: ogni riuso del mezzo '
            'deve passare nell’altra ala. Una linea unica può invece avere alcune corse limitate a FS '
            'e cicli completi dichiarati: il modello non deve imporre l’alternanza sistematica al committente '
            'come se ne fosse l’unica interpretazione.']
    lines+=['',
        '## Conseguenza progettuale','',
        'L’aggiunta di Arlate e l’esclusione di Via Indipendenza sono chiuse come indirizzo. '
        'La geometria e la produzione a 31 corse non vengono riaperte da questo audit. '
        '**Non è invece chiusa una linea intercomunale sempre continua e rapida:** '
        'il successivo chiarimento richiede che ogni corsa commerciale comprenda entrambe le ali '
        'e respinge corse limitate a FS. I contratti esaminati in questo audit '
        'non sono identici all’alternanza obbligatoria di ogni riuso del mezzo. '
        'Un mezzo in più, da solo, non dimostra che i viaggi diventino rapidi. '
        'Nessun incremento di flotta, nuova regola ferroviaria o orario alternativo è adottato qui.',
        '',
        'Rigenerazione: `python -m scripts.phase2_audit_rt031_line8_through_service_v3` con '
        '`PYTHONPATH` su radice repository e `src`. Test: '
        '`python -m unittest discover -s tests -p test_phase2_rt031_line8_through_service_v3.py`.',
        '',
        '[Scelte del committente](../config/rt031_stop_choices_and_through_line_v3.json) · '
        '[Frontiere, blocchi, eventi e viaggi (JSON gzip)](../outputs/phase2/rt031_line8_local_shortcuts_v3/through_service_fixed_31.json.gz) · '
        '[Base a 31 corse](RT031_LINEA8_ORARIO_31_CORSE_V3.md)']
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--joint_retiming',action=argparse.BooleanOptionalAction,default=True)
    args=parser.parse_args()
    result=build()
    result['central_retiming_comparison']=middle_retiming_comparison()
    print('Central retiming:',{k:v for k,v in result['central_retiming_comparison'].items() if k!='cases'})
    if args.joint_retiming:
        result['joint_retiming_comparison']=joint_retiming_comparison()
        print('Joint retiming:',{k:v for k,v in result['joint_retiming_comparison'].items() if k not in ('trips','independent_timing_check','alternating_blocks')},flush=True)
        result['five_vehicle_wait_comparison']=five_vehicle_wait_comparison()
        print('Five-vehicle wait:',{k:v for k,v in result['five_vehicle_wait_comparison'].items() if k not in ('checks','witness')},flush=True)
    OUTPUT.write_bytes(gzip.compress((json.dumps(result,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8'),mtime=0))
    DOC.write_text(report(result),encoding='utf-8')
