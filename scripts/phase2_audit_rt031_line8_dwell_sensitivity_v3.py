"""Inherited deterministic dwell grid on hypothetical road-node stop events."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
from src.phase2_rt031_frequent_access_shortlist_v3 import engineering_cycle_sensitivity
from scripts.phase2_audit_rt031_line8_independent_wings_v3 import minimum_blocks
from scripts.phase2_audit_rt031_line8_band_switch_v3 import largest_gap


def adjusted_loops(loops,multiplier,dwell):
    result=copy.deepcopy(loops)
    for k,loop in result.items():
        indices=sorted({e['path_node_index'] for e in loop['events']})
        loop['road_minutes']=loops[k]['road_minutes']*multiplier+len(indices)*dwell
        for e in loop['events']:
            e['offset_from_wing_origin_min']=e['offset_from_wing_origin_min']*multiplier+sum(i<=e['path_node_index'] for i in indices)*dwell
    return result


def build(source):
    if source['contract']!='RT031_LINE8_INDEPENDENT_WINGS_DIAGNOSTIC_V3' or source['network_selected']:
        raise ValueError('unsupported source')
    loops=source['loops']
    counts={k:len({e['path_node_index'] for e in v['events']}) for k,v in loops.items()}
    grid=engineering_cycle_sensitivity([{'component_id':k,'running_minutes_source_model_excludes_dwell':v['road_minutes'],
        'nonhub_public_stop_event_count':counts[k]} for k,v in loops.items()],headway_min=30)
    base=next(c for c in source['cases'] if c['calendar_case']=='synchronised_07' and c['east_shift_min']==-15)
    results=[]
    for sensitivity in grid['cases']:
        multiplier=float(sensitivity['runtime_multiplier'])
        dwell=float(sensitivity['dwell_per_nonhub_public_stop_event_min'])
        recovery=float(sensitivity['recovery_minutes'])
        adjusted=adjusted_loops(loops,multiplier,dwell)
        for advance in range(30):
            trips=[{**t,'departure_min':t['departure_min']-(advance if t['loop'] in ('west_A','east_B') else 0)} for t in base['trips']]
            trips.sort(key=lambda t:(t['departure_min'],t['loop']))
            opportunities={}
            for i,t in enumerate(trips):
                for e in adjusted[t['loop']]['events']:
                    for direction,time in (('to_fs',t['departure_min']+e['offset_from_wing_origin_min']),('from_fs',t['departure_min'])):
                        opportunities.setdefault((e['stop_place_id'],direction),[]).append({'minute':time,'event_id':str(i)+':'+e['occurrence_id']})
            gap=max(largest_gap(events)['minutes'] for events in opportunities.values())
            arrivals={wing:min(t['departure_min']+adjusted[t['loop']]['road_minutes'] for t in trips if t['loop'].startswith(wing)) for wing in ('west','east')}
            results.append({'runtime_multiplier':multiplier,'dwell_per_hypothetical_event_min':dwell,
                'recovery_per_wing_min':recovery,'morning_advance_min':advance,
                'first_fs_arrival_min':{k:round(v,6) for k,v in arrivals.items()},
                'maximum_optimistic_identity_gap_min':gap,
                'minimum_blocks':minimum_blocks(trips,adjusted,source['represented_via_node_joins'],recovery)})
    return {'contract':'RT031_LINE8_HYPOTHETICAL_DWELL_SENSITIVITY_V3','cases':results,
        'hypothetical_distinct_nonhub_road_node_occurrences_by_loop':counts,
        'annual_km_before_extras':base['annual_km_before_extras'],
        'semantics':'Each distinct nonhub path-node occurrence is assumed to be a served stop, not certified as one. Co-located identities at the same path index receive one dwell. Boarding is after that dwell; uniform runtime multiplier scales moving time only. Recovery is at FS after passenger alighting and is not added to train-transfer arrival time.',
        'grid_source':'Inherited engineering_cycle_sensitivity defaults: 0.9/1.0/1.1 running multipliers, 0/0.5/1 minute per event, 5/10/15 minutes recovery per wing.',
        'status':'DETERMINISTIC_SENSITIVITY_NOT_OBSERVED_DWELL_OR_PROBABILITY',
        'observed_dwell_available':False,'actual_timetable_certified':False,
        'network_selected':False,'primary_selection_authorised':False,'runner_up_selection_authorised':False,
        'decision_budget_km':None,'uncertainty_band_min':None}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,required=True); p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); result=build(json.loads(a.source.read_text(encoding='utf-8')))
    grid_source=Path(__file__).resolve().parents[1]/'src/phase2_rt031_frequent_access_shortlist_v3.py'
    result['source_sha256']={k:hashlib.sha256(v.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for k,v in (('wings',a.source),('grid_code',grid_source))}
    a.output.write_text(json.dumps(result,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
