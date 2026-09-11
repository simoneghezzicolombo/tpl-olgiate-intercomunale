"""Screen predeclared full physical cycles against the already approved budget."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from src.phase2_rt031_exact_resource_screen_v3 import screen_cycle

PINNED={
 'config/phase2_final_policy_contract_v3.json':'28909df6b9cdcf49608d4e7456f819959d35d1bf2c41dd1800d026bb06d963e0',
 'config/phase2_service_policy_design_space_v2.json':'3f5667ec09e70b530e3adff7240c8445027fb62073b25e4b0617652f43a1a468'}


def main(routes_path,out):
    configs={}
    for name,digest in PINNED.items():
        data=Path(name).read_bytes()
        if hashlib.sha256(data).hexdigest()!=digest:raise ValueError('policy source changed')
        configs[name]=json.loads(data)
    policy=configs['config/phase2_final_policy_contract_v3.json']
    grid=configs['config/phase2_service_policy_design_space_v2.json']
    cap=policy['human_policy_decisions']['annual_bus_km_cap']
    routes=json.loads(routes_path.read_text())
    if routes['contract']!='RT031_DECLARED_COMPLETE_ROUTE_PHYSICAL_EVALUATION_V3':raise ValueError('route contract mismatch')
    rows=[]
    for route in routes['scenarios']:
        if not route['closed']:continue
        if not route['exact'] or route['full_history_replay_pass'] is not True:raise ValueError('unverified complete route')
        for h in grid['headways_min']:
            for span in grid['spans']:
                for calendar in grid['annual_service_days']:
                    r=screen_cycle(route['minimum_distance_m'],headway=h,start=span['start_min'],end=span['end_min'],days=calendar['days'],cap_km=cap)
                    r.update(scenario_id=route['scenario_id'],minimum_cycle_distance_m=route['minimum_distance_m'],
                        headway_min=h,span_id=span['span_id'],calendar_id=calendar['calendar_id'],
                        annual_days=calendar['days'],calendar_status=calendar['status'],
                        span_status=span['status'],headway_status=grid['headway_status'])
                    rows.append(r)
    lower_bound_screen=[]
    bound=routes['all_stop_single_closed_walk_lower_bound']
    for h in grid['headways_min']:
        for span in grid['spans']:
            for calendar in grid['annual_service_days']:
                r=screen_cycle(bound['lower_bound_m'],headway=h,start=span['start_min'],end=span['end_min'],days=calendar['days'],cap_km=cap)
                r.update(headway_min=h,span_id=span['span_id'],annual_days=calendar['days'])
                lower_bound_screen.append(r)
    audit=dict(contract='RT031_EXACT_DECLARED_CYCLE_RESOURCE_SCREEN_V3',approved_annual_bus_km_cap=cap,
        policy_sha256=PINNED,route_input_sha256=hashlib.sha256(routes_path.read_bytes()).hexdigest(),
        all_stop_single_closed_walk_lower_bound=bound,
        all_stop_lower_bound_contexts=lower_bound_screen,
        evaluated_contexts=len(rows),status_counts=dict(sorted(Counter(r['status'] for r in rows).items())),
        scope='Necessary budget screen of three declared physical stress cycles under existing design assumptions; not a search over all 35-stop orders.',
        full_service_feasibility_certified=False,network_selected=False,rows=rows)
    out.mkdir(parents=True,exist_ok=True)
    (out/'exact_resource_screen.json').write_text(json.dumps(audit,sort_keys=True,indent=2)+'\n')
    print(json.dumps({k:v for k,v in audit.items() if k not in ('rows','all_stop_lower_bound_contexts')},sort_keys=True))
    for r in rows:
        if r['headway_min']==60 and r['span_id']=='CORE_0600_2200' and r['annual_days']==260:
            print(json.dumps(r,sort_keys=True))
    return audit


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--routes',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();main(a.routes,a.out)
