"""Joint AM/rest phase feasibility, conditional and without candidate selection."""
import argparse
import hashlib
import json
from pathlib import Path
from scripts.phase2_audit_rt031_line8_dwell_sensitivity_v3 import adjusted_loops
from scripts.phase2_audit_rt031_line8_band_switch_v3 import largest_gap
from scripts.phase2_audit_rt031_line8_independent_wings_v3 import minimum_blocks


def shifted_trips(base, wing, am, rest):
    return [{'loop':t['loop'],'departure_min':t['departure_min']+(15 if wing=='east' else 0)
             -(am if t['loop'] in ('west_A','east_B') else rest)}
            for t in base if t['loop'].startswith(wing)]


def metrics(trips,loops):
    events={}
    for i,t in enumerate(trips):
        for e in loops[t['loop']]['events']:
            events.setdefault(e['stop_place_id'],[]).append({'minute':t['departure_min']+e['offset_from_wing_origin_min'],
                                                           'event_id':str(i)+':'+e['occurrence_id']})
    gaps=[largest_gap(v)['minutes'] for v in events.values()]
    gaps += [b['departure_min']-a['departure_min'] for a,b in zip(trips,trips[1:])]
    return {'max_optimistic_identity_gap_min':max(gaps),
        'first_fs_arrival_min':min(t['departure_min']+loops[t['loop']]['road_minutes'] for t in trips),
        'last_fs_departure_min':max(t['departure_min'] for t in trips)}


def build(source,rail_audit):
    if source['contract']!='RT031_LINE8_INDEPENDENT_WINGS_DIAGNOSTIC_V3' or source['network_selected']:
        raise ValueError('unexpected source')
    if rail_audit['contract']!='RT031_LINE8_FROZEN_RAIL_BOUNDARY_DIAGNOSTIC_V3' or rail_audit['service_date']!='2026-09-03':
        raise ValueError('unexpected frozen rail source')
    anchor=next(c for c in rail_audit['cases'] if c['calendar_case']=='synchronised_07' and c['advance_scope']=='morning_only' and c['common_advance_min']==8)
    inbound=next(r for r in anchor['interchange_rows'] if r['wing']=='west' and r['rail_direction']=='MILANO' and r['transfer_walk_min_assumption']==3)
    outbound=next(r for r in anchor['interchange_rows'] if r['wing']=='west' and r['rail_direction']=='LECCO' and r['transfer_walk_min_assumption']==3)
    latest_arrival=inbound['first_reachable_train_departure_min']-3
    earliest_last=outbound['last_train_arrival_with_onward_bus_min']+3
    base=next(c for c in source['cases'] if c['calendar_case']=='synchronised_07' and c['east_shift_min']==-15)
    result=[]
    for dwell in (.5,1.):
        adjusted=adjusted_loops(source['loops'],1.1,dwell)
        for wing in ('west','east'):
            feasible=[]
            for am in range(30):
                for rest in range(30):
                    trips=shifted_trips(base['trips'],wing,am,rest)
                    m=metrics(trips,adjusted)
                    if m['first_fs_arrival_min']<=latest_arrival and m['last_fs_departure_min']>=earliest_last and m['max_optimistic_identity_gap_min']<=60.000001:
                        feasible.append({'am_advance_min':am,'rest_advance_min':rest,**{k:round(v,6) for k,v in m.items()}})
            result.append({'wing':wing,'runtime_multiplier':1.1,'dwell_min_assumption':dwell,'feasible_phases':feasible})
    # One reproducible diagnostic witness, never a selected/recommended phase.
    trips=sorted(shifted_trips(base['trips'],'west',18,20)+shifted_trips(base['trips'],'east',18,20),key=lambda t:(t['departure_min'],t['loop']))
    adjusted=adjusted_loops(source['loops'],1.1,.5)
    witness={'purpose':'ILLUSTRATION_NOT_RANKED_OR_SELECTED','am_advance_min':18,'rest_advance_min':20,
        'runtime_multiplier':1.1,'dwell_min_assumption':.5,'trips':trips,
        'wing_metrics':{w:{k:round(v,6) for k,v in metrics([t for t in trips if t['loop'].startswith(w)],adjusted).items()} for w in ('west','east')},
        'blocks':[minimum_blocks(trips,adjusted,source['represented_via_node_joins'],r) for r in (5,10,15)],
        'annual_km_before_extras':base['annual_km_before_extras'],
        'remaining_km_before_extras':base['remaining_km_before_extras']}
    constant=[]
    for name,loop in adjusted.items():
        wing=name.split('_')[0]
        feasible=[]
        for advance in range(30):
            constant_trips=[{**t,'loop':name} for t in shifted_trips(base['trips'],wing,advance,advance)]
            m=metrics(constant_trips,adjusted)
            if m['first_fs_arrival_min']<=latest_arrival and m['last_fs_departure_min']>=earliest_last and m['max_optimistic_identity_gap_min']<=60.000001:
                feasible.append(advance)
        required={e['stop_place_id'] for k,v in adjusted.items() if k.startswith(wing) for e in v['events']}
        seen={e['stop_place_id'] for e in loop['events']}
        constant.append({'loop':name,'uniform_advance_min_feasible_for_station_boundaries':feasible,
            'annual_wing_km_before_extras':round(loop['distance_m']*17*260/1000,3),
            'lost_hypothetical_site_ids_vs_both_orientations':sorted(required-seen),
            'maximum_hypothetical_minutes_to_fs_after_boarding':round(max(loop['road_minutes']-e['offset_from_wing_origin_min'] for e in loop['events']),6)})
    return {'contract':'RT031_LINE8_JOINT_PHASE_FEASIBILITY_V3','phase_tables':result,'illustrative_witness':witness,
        'constant_orientation_diagnostics':constant,
        'frozen_rail_targets':{'service_date':'2026-09-03','train_to_milano_departure_min':latest_arrival+3,
            'train_from_milano_arrival_min':earliest_last-3,'transfer_walk_min_assumption':3},
        'domain':'Per wing, all 30x30 integer-minute AM/rest advances; fixed 17-trip inventory and AM/rest orientations. Separate wing feasibility is not joint fleet certification.',
        'semantics':'H60 bound is optimistic across hypothetical boardable identity occurrences. Peak dispatch groups retain 30-minute spacing but their clock windows shift. Exact 07-09/17-19 local H30 is NOT certified or silently relaxed. No observed dwell or delay probability.',
        'actual_timetable_certified':False,'requested_peak_windows_certified':False,
        'network_selected':False,'primary_selection_authorised':False,'runner_up_selection_authorised':False,
        'decision_budget_km':None,'uncertainty_band_min':None}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ('source','rail_audit','output'):
        p.add_argument('--'+k,required=True,type=Path)
    a=p.parse_args(); result=build(json.loads(a.source.read_text(encoding='utf-8')),json.loads(a.rail_audit.read_text(encoding='utf-8')))
    result['source_sha256']={k:hashlib.sha256(v.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for k,v in vars(a).items() if k!='output'}
    a.output.write_text(json.dumps(result,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
