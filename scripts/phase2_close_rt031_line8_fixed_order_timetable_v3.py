"""Bounded timetable closure on the unadopted fixed-order Hoe omission shape."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

from scripts.phase2_probe_rt031_line8_no_reverse_all_orders_v3 import OUTPUT as ROAD
from scripts.phase2_probe_rt031_line8_variable_fs_hold_v3 import solve
from scripts.phase2_rebuild_rt031_uniform_complete_line_v3 import inputs

OUTPUT = ROAD.parent/'hoe_fixed_order_timetable_closure.json.gz'


def build(time_limit=30):
    source = json.loads(gzip.decompress(ROAD.read_bytes()))
    candidate = source['hoe_omission_fixed_event_order_comparison_not_adopted']
    if not candidate['retained_journey_times_preserved'] or candidate['stop_omission_adopted']:
        raise ValueError('wrong fixed-order source semantics')
    _, policy, _, _, _ = inputs()
    cases = []
    comparisons = [
        ('west_B',60,None,None,55,16), ('west_B',65,None,None,55,16),
        ('east_A',60,None,None,55,16), ('east_A',65,None,None,55,16),
        ('west_B',70,4,None,55,16),
        ('west_B',70,None,('east','rail_to_bus',962),55,16),
        ('east_A',70,None,('east','rail_to_bus',962),55,16),
        ('west_B',60,None,None,85,16),('east_A',60,None,None,85,16),
        ('west_B',70,4,None,85,16),('west_B',60,None,None,55,17),
        ('west_B',60,None,None,55,18),
        ('west_B',70,None,('east','rail_to_bus',992),55,16),
        ('east_A',70,None,('east','rail_to_bus',992),55,16),
    ]
    for first, shoulder, fleet, bank, max_mid, count in comparisons:
        # Same 16 complete trips and 50/55-minute inter-wing offsets where
        # stress permits. All changes are comparisons, not caller adoption.
        result = solve(policy,candidate['loops'],first,False,shoulder,time_limit,
            max_mid=max_mid,anchor_policy='flexible_real_trains',vehicle_cap=fleet,
            required_train_bank_start=bank,full_trip_count=count)
        bank_label=bank[2] if bank else 'free'
        result['case_id']=f'{first}_H{shoulder}_fleet{fleet}_east_bank{bank_label}_mid{max_mid}_trips{count}'
        result['comparison_not_adopted']=True
        cases.append(result)
        print(result['case_id'],result['solver_status'],result['witness_found'],flush=True)
    return {
        'contract':'RT031_LINE8_HOE_FIXED_ORDER_TIMETABLE_CLOSURE_DIAGNOSTIC_V3',
        'road_source_sha256':hashlib.sha256(ROAD.read_bytes()).hexdigest(),
        'baseline_case_not_adopted':candidate['timetable_comparison_not_adopted'],
        'annual_service_km_16_trips_260_days':candidate['annual_service_km_16_trips_260_days'],
        'cases':cases,
        'scope':'Same 28 design sites, one fixed complete eight per trip, 16 trips. '
            'Compare H60/H65 readiness shoulders in both full-route orientations, '
            'four-vehicle common-stress cap and east inbound banks 16:02/16:32. '
            'H30 binds five actual archived trains per wing/peak. H120 only 10-16. '
            'Five-minute departure grid; compare maximum intermediate offsets '
            '55/85 minutes and a diagnostic unadopted 17th trip. Status 2 proves '
            'infeasibility ONLY in the exact case domain; '
            'a solver timeout without a witness is not proof. '
            'No OD, demand inference, empirical miss probability or service selection.',
        'calendar_adopted':False,'stop_omission_adopted':False,
        'physical_bus_operation_certified':False,'network_selected':False,
        'primary_selection_authorised':False,'runner_up_selection_authorised':False,
        'decision_budget_km':None,'uncertainty_band_min':None,
    }


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--time-limit',type=int,default=30)
    args=parser.parse_args()
    result=build(args.time_limit)
    OUTPUT.write_bytes(gzip.compress((json.dumps(result,ensure_ascii=False,
        sort_keys=True,separators=(',',':'))+'\n').encode('utf-8'),mtime=0))
