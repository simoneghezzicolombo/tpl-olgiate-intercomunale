"""Combine independent wing infeasibility certificates into a bounded km floor."""
import argparse
import hashlib
import json
from pathlib import Path


def build(wings, west, east, policy):
    if wings['contract'] != 'RT031_LINE8_INDEPENDENT_WINGS_DIAGNOSTIC_V3':
        raise ValueError('wrong road contract')
    for source in (wings,west,east):
        if any(source[k] for k in ('network_selected','primary_selection_authorised','runner_up_selection_authorised')):
            raise ValueError('decisional source')
    sites = {wing:{e['stop_place_id'] for k,v in wings['loops'].items() if k.startswith(wing) for e in v['events']}
             for wing in ('west','east')}
    if sites['west'] & sites['east']:
        raise ValueError('shared destinations invalidate independent coverage lower bound')
    for wing, audit in (('west',west),('east',east)):
        if (audit['contract'] != 'RT031_LINE8_JOINT_FLEXIBLE_PEAK_COMPARISON_V3'
                or audit['wing_relaxation'] != wing
                or audit['maximum_trip_count_each_wing'] != 17
                or audit['solver_status'] != 2
                or not audit.get('infeasibility_proven_in_declared_finite_domain')
                or audit['ready_span_min'] != [360,1140]
                or audit['reference_service_km_cap_if_tested'] is not None):
            raise ValueError('no independent unbudgeted wing infeasibility certificate')
    for key in ('departure_grid_min','phase_domain','source_sha256'):
        if west[key] != east[key]:
            raise ValueError('incompatible independent domains')
    if policy['contract'] != 'PHASE2_HUMAN_APPROVED_FINAL_POLICY_V3':
        raise ValueError('wrong cap source')
    lower_per_wing = {wing:18*min(v['distance_m'] for k,v in wings['loops'].items() if k.startswith(wing))/1000*260
                      for wing in ('west','east')}
    total = sum(lower_per_wing.values())
    cap = policy['human_policy_decisions']['annual_bus_km_cap']
    return {'contract':'RT031_LINE8_FLEXIBLE_PEAK_KM_FLOOR_V3',
        'status':'REFERENCE_CAP_EXCLUDED_IN_DECLARED_FINITE_DOMAIN' if total > cap else 'CAP_NOT_EXCLUDED',
        'minimum_trips_per_wing_lower_bound':18,
        'annual_service_km_lower_bound':round(total,6),
        'reference_cap_from_existing_policy':cap,'lower_bound_excess_km':round(total-cap,6),
        'lower_bound_is_attainable_timetable':False,
        'departure_grid_min':west['departure_grid_min'],'phase_domain':west['phase_domain'],
        'ready_span_min':[360,1140],
        'proof':'Each wing separately cannot cover its full ready-time requirements with <=17 trips even with independent morning/evening phase choices. Any joint feasible solution therefore needs >=18 complete trips on each wing. Charge all 18 at that wing cheapest pattern distance. This is a relaxation, not a witness or exact optimum.',
        'limits':['fixed four complete wing paths','finite departure and peak-phase grids','13-hour common ready-time promise 06-19',
                  'two common 120-minute peaks per day','260 assumed service days','optimistic identity boarding union',
                  '1.1 moving multiplier and 0.5 minute dwell','no depot or positioning km'],
        'network_selected':False,'primary_selection_authorised':False,'runner_up_selection_authorised':False,
        'decision_budget_km':None,'uncertainty_band_min':None}


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    for key in ('wings','west','east','policy','output'):
        p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args()
    sources={k:json.loads(v.read_text(encoding='utf-8')) for k,v in vars(a).items() if k!='output'}
    digest=hashlib.sha256(a.wings.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    if any(sources[k]['source_sha256'] != digest for k in ('west','east')):
        raise ValueError('certificate road source mismatch')
    result=build(**sources)
    result['source_sha256']={k:hashlib.sha256(v.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for k,v in vars(a).items() if k!='output'}
    a.output.write_text(json.dumps(result,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    print(json.dumps(result))
