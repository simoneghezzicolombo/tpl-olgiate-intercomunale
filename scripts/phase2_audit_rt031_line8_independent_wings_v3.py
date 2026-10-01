"""Independent FS-rooted wing dispatch diagnostics, not an approved timetable."""
import argparse
import json
import itertools
from pathlib import Path
from scripts.phase2_audit_rt031_south_road_probe_v3 import EXPECTED, FS, digest
from scripts.phase2_probe_rt031_unique_line_v3 import build_graph
from scripts.phase2_audit_rt031_line8_band_switch_v3 import dispatches, largest_gap
from src.phase2_rt031_rt017_transition_adapter_v3 import FrozenRT017ViaNodeAdapter


def minimum_blocks(trips, loops, joins, allowance):
    """Minimum path cover of acyclic feasible trip-successor graph."""
    successors = {i:[j for j,b in enumerate(trips) if b['departure_min'] > a['departure_min']
        and a['departure_min']+loops[a['loop']]['road_minutes']+allowance <= b['departure_min']+1e-9
        and joins[a['loop']+'>'+b['loop']]] for i,a in enumerate(trips)}
    matched = {}
    def augment(i, seen):
        for j in successors[i]:
            if j in seen:
                continue
            seen.add(j)
            if j not in matched or augment(matched[j], seen):
                matched[j] = i
                return True
        return False
    for i in range(len(trips)):
        augment(i,set())
    next_trip = {i:j for j,i in matched.items()}
    blocks = []
    for start in range(len(trips)):
        if start in matched:
            continue
        block = [start]
        while block[-1] in next_trip:
            block.append(next_trip[block[-1]])
        blocks.append(block)
    return {'minimum_vehicle_count_conditional':len(blocks),'trip_index_blocks':blocks,
            'allowance_per_wing_trip_min':allowance}


def build(paths):
    source = json.loads(paths['source'].read_text(encoding='utf-8'))
    policy = json.loads(paths['policy'].read_text(encoding='utf-8'))
    if source['contract'] != 'RT031_LINE8_OCCURRENCE_SERVICE_DIAGNOSTIC_V3' or source['network_selected']:
        raise ValueError('unsupported source')
    for k in EXPECTED:
        if source['source_sha256'][k] != digest(paths[k], k.endswith('normalized_newlines')):
            raise ValueError('upstream mismatch '+k)
    if policy['contract'] != 'PHASE2_HUMAN_APPROVED_FINAL_POLICY_V3':
        raise ValueError('policy mismatch')
    edges,_,rules,attachments = build_graph(paths)
    fs_node = attachments[FS]['graph_node_id']
    adapter = FrozenRT017ViaNodeAdapter(edges.values(), rules, unresolved_external_via_way_count=2)
    loops = {}
    for direction, names in (('forward',('west_A','east_A')), ('reverse',('east_B','west_B'))):
        path = source['road_patterns'][direction]['edge_ids']
        returns = [i+1 for i,eid in enumerate(path) if edges[eid]['v_node_id']==fs_node]
        if len(returns)!=2 or returns[-1]!=len(path):
            raise ValueError('ambiguous FS split')
        boundaries = [0,*returns]
        for name,lo,hi in zip(names,boundaries,boundaries[1:]):
            segment = path[lo:hi]
            if any(adapter.decision((a,),b)['allowed'] is not True for a,b in zip(segment,segment[1:])):
                raise ValueError('forbidden represented turn inside wing')
            start_time = sum(float(edges[e]['running_minutes_model']) for e in path[:lo])
            events = [{**e,'offset_from_wing_origin_min':round(e['offset_road_minutes']-start_time,6)}
                      for e in source['events'] if e['direction']==direction and lo <= e['path_node_index'] < hi and e['stop_place_id']!=FS]
            loops[name] = {'edge_ids':segment,'events':events,
                'distance_m':sum(float(edges[e]['length_m']) for e in segment),
                'road_minutes':sum(float(edges[e]['running_minutes_model']) for e in segment)}
    joins = {a+'>'+b:adapter.decision((ra['edge_ids'][-1],),rb['edge_ids'][0])['allowed'] is True
             for a,ra in loops.items() for b,rb in loops.items()}
    cases = []
    for mode,east_shift in itertools.product(('synchronised_07','add_0630','move_last_1900_to_0630'),(-15,0,15)):
        times = dispatches(420,1200)
        if mode != 'synchronised_07':
            times = [390]+times
        if mode == 'move_last_1900_to_0630':
            times.remove(1140)
        trips = [{'departure_min':t+(east_shift if loop.startswith('east') else 0),'loop':loop} for t in times
                 for loop in (('west_A','east_B') if t<540 else ('west_B','east_A'))]
        trips.sort(key=lambda t:(t['departure_min'],t['loop']))
        by_site = {}
        for i,trip in enumerate(trips):
            for e in loops[trip['loop']]['events']:
                sid = e['stop_place_id']
                value = by_site.setdefault(sid,{'name':e['name'],'to_fs':[],'from_fs':[]})
                for direction,minute in (('to_fs',trip['departure_min']+e['offset_from_wing_origin_min']),('from_fs',trip['departure_min'])):
                    value[direction].append({'minute':round(minute,6),'event_id':f'{i}:{e["occurrence_id"]}:{direction}'})
        diagnostics = {sid:{'name':v['name'],**{d:{'first_boarding_min':min(e['minute'] for e in v[d]),
            'last_boarding_min':max(e['minute'] for e in v[d]),'optimistic_identity_gap':largest_gap(v[d])}
            for d in ('to_fs','from_fs')}} for sid,v in by_site.items()}
        km = sum(loops[t['loop']]['distance_m'] for t in trips)/1000*260
        allowances = [0]+sorted({r['recovery_min_assumption'] for r in source['runtime_sensitivities']})
        cases.append({'case_id':mode+':east_shift_'+str(east_shift),'calendar_case':mode,
            'east_shift_min':east_shift,'trips':trips,'annual_km_before_extras':round(km,3),
            'remaining_km_before_extras':round(policy['human_policy_decisions']['annual_bus_km_cap']-km,3),
            'by_site':diagnostics, 'blocks': [minimum_blocks(trips,loops,joins,r) for r in allowances]})
    return {'contract':'RT031_LINE8_INDEPENDENT_WINGS_DIAGNOSTIC_V3',
        'source_sha256':{k:digest(v,k not in ('edges','nodes','rules','attachments','successor')) for k,v in paths.items()},
        'loops':loops,'represented_via_node_joins':joins,'cases':cases,
        'phase_semantics':'East offsets -15/0/+15 minutes are a bounded comparison grid, not optimised train phases. They also shift local peak-band boundaries and first/last departures; exact 07-09 and 17-19 local H30 coverage is not certified.',
        'semantics':'One public-line concept with separate wing departures at FS; no public-route-count choice or guaranteed through passenger journey. Boardable sites and zero passenger-event dwell are optimistic assumptions, not facts. End of last trip is not last departure.',
        'block_semantics':'Exact minimum path cover ONLY for given road-only trips, represented via-node joins and uniform allowance per wing trip. 0 is an optimistic bound; 5/10/15 are existing sensitivity values now charged at EACH wing, not each full eight. No depot, actual dwell, full-history legality or driver-duty certification.',
        'not_certified':['boarding events','train connections','full-history restrictions','bus suitability','depot km','passenger continuity at FS','actual operating timetable'],
        'network_selected':False,'primary_selection_authorised':False,'runner_up_selection_authorised':False,
        'decision_budget_km':None,'uncertainty_band_min':None}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in (*EXPECTED,'source','policy','output'):
        p.add_argument('--'+k,required=True,type=Path)
    a=p.parse_args(); result=build({k:v for k,v in vars(a).items() if k!='output'})
    a.output.write_text(json.dumps(result,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
