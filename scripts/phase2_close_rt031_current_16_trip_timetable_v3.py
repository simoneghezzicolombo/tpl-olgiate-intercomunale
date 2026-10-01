"""Bounded current 16-trip closure. Audit inherited promises, no silent loosening."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from scripts.phase2_rebuild_rt031_uniform_complete_line_v3 import inputs
from scripts.phase2_probe_rt031_line8_variable_fs_hold_v3 import solve

BASE=ROOT/'outputs/phase2/rt031_line8_local_shortcuts_v3'
DESIGN=BASE/'calco_centre_adopted_design.json'
RAIL=BASE/'all_station_rail_20261001.json'
OUTPUT=BASE/'current_16_trip_timetable_closure.json'


def current_inputs():
    design=json.loads(DESIGN.read_text(encoding='utf-8'))
    rail=json.loads(RAIL.read_text(encoding='utf-8'))
    if not rail['ready_for_dated_rail_diagnostic']:
        raise ValueError('Current all-route railway inventory unresolved')
    _,legacy,_,_,_=inputs()
    policy=copy.deepcopy(legacy)
    policy['rail']=rail
    # Preserve old objectives as a diagnostic ledger. No stale per-stop
    # eligibility list or removed Alpino identity enters the new search.
    policy['anchors']=[dict(wing=w,kind=k,rail_min=m) for w,k,m in sorted({
        (a['wing'],a['kind'],a['rail_min']) for a in legacy['anchors']})]
    return design,rail,policy


def build(step=5,time_limit=20,shoulder=60,max_mid=55,pm_ceiling=8,am_ceiling=None,anchor_policy='flexible_real_trains',core_end=960,east_return_bank=None):
    design,rail,policy=current_inputs()
    inherited_am_ceiling=policy['wait_ceiling']
    if am_ceiling is not None: policy['wait_ceiling']=am_ceiling
    result=solve(policy,design['loops'],'east_A',False,shoulder,time_limit,
        max_mid=max_mid,full_trip_count=16,anchor_policy=anchor_policy,
        departure_step_min=step,pm_transfer_ceiling_min=pm_ceiling,
        required_train_bank_start=None if east_return_bank is None else ('east','rail_to_bus',east_return_bank),
        ready_windows_override=[[410,600,shoulder],[600,core_end,120],[core_end,1180,shoulder]])
    result.update(contract='RT031_CURRENT_FIXED_DESIGN_16_TRIP_CLOSURE_DIAGNOSTIC_V3',
        service_date=rail['service_date'],public_route_name='Linea 8',
        required_full_trip_count=16,public_wing_sequence=['east_A','west_B'],
        distinct_design_site_count=design['served_design_site_count_including_fs'],
        complete_path_distance_m=design['complete_path_distance_m'],
        all_rail_calls_audited_count=rail['event_count'],
        legacy_binding_scope='Five consecutive actual MILANO departures AM and five consecutive arrivals from MILANO PM per wing. Historical diagnostic policy, NOT proof of all-direction guarantees or caller adoption of these exact banks.',
        all_rail_connections_guaranteed=False,
        inherited_nine_engineering_cases_not_empirical_uncertainty=True,
        inherited_transfer_walk_assumption_min=3,
        inherited_am_residual_wait_ceiling_min=inherited_am_ceiling,
        compared_am_residual_wait_ceiling_min=policy['wait_ceiling'],
        comparison_am_wait_change_adopted=False,
        inherited_pm_train_to_bus_window_min=[3,8],
        compared_pm_train_to_bus_window_min=[3,pm_ceiling],
        comparison_pm_wait_change_adopted=False,
        inherited_ready_windows_min=[[410,600,shoulder],[600,960,120],[960,1180,shoulder]],
        compared_core_end_min=core_end,comparison_core_end_change_adopted=False,
        ready_windows_are_comparison_not_new_caller_authority=True,
        grid_infeasibility_not_continuous_time_proof=True,
        detailed_timetable_adopted=False,calendar_adopted=False,
        source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (DESIGN,RAIL,ROOT/'config/rt031_16_full_trips_authority_v3.json')},
        missed_connection_probability=None,demand_weighted_gjt_improvement_min=None,
        decision_budget_km=None,uncertainty_band_min=None,
        network_selected=False,primary_selection_authorised=False,runner_up_selection_authorised=False)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--step',type=int,default=5)
    parser.add_argument('--time-limit',type=int,default=20);parser.add_argument('--shoulder',type=int,default=60)
    parser.add_argument('--max-mid',type=int,default=55);parser.add_argument('--pm-ceiling',type=int,default=8)
    parser.add_argument('--am-ceiling',type=float);parser.add_argument('--anchor-policy',choices=['flexible_real_trains','h30_unbound'],default='flexible_real_trains')
    parser.add_argument('--core-end',type=int,default=960);parser.add_argument('--east-return-bank',type=int);args=parser.parse_args()
    result=build(args.step,args.time_limit,args.shoulder,args.max_mid,args.pm_ceiling,args.am_ceiling,args.anchor_policy,args.core_end,args.east_return_bank)
    output=OUTPUT.with_name(f'current_16_trip_timetable_step{args.step}_H{args.shoulder}_mid{args.max_mid}_PM{args.pm_ceiling}_AM{args.am_ceiling or "inherited"}_{args.anchor_policy}_core{args.core_end}_east{args.east_return_bank or "free"}.json')
    output.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result.get(k) for k in ('solver_status','solver_message','witness_found','infeasibility_proven','full_trips','annual_service_km_260_day_comparison','selected_real_train_banks_not_adopted')}),flush=True)
