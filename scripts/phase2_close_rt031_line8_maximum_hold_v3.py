"""Close the maximum-holding question on unadopted 17-trip comparisons.

Pure minimax diagnostic, no tradeoff weights or public network selection.
The short/long one-wing FS journeys are intrinsic to these fixed service paths.
"""
import argparse
import gzip
import hashlib
import json

from scripts.phase2_probe_rt031_line8_paired_cuts_v3 import OUTPUT as CUTS
from scripts.phase2_probe_rt031_line8_variable_fs_hold_v3 import solve, wing_offsets
from scripts.phase2_rebuild_rt031_uniform_complete_line_v3 import inputs, source_fingerprints

OUTPUT=CUTS.parent/'paired_cuts_maximum_hold_closure.json.gz'


def build(time_limit=30):
    source_bytes=CUTS.read_bytes()
    source=json.loads(gzip.decompress(source_bytes))
    _,policy,_,_,_=inputs()
    cases=[]
    for c in source['cases']:
        if c['case_id'] not in source['timetable_domain']['case_ids']:continue
        for first in ('west_B','east_A'):
            r=solve(policy,c['loops'],first,False,60,time_limit,max_mid=85,
                    full_trip_count=17,anchor_policy='flexible_real_trains',
                    minimize_max_hold=True)
            r.update(geometry_case_id=c['case_id'],omitted_stop_ids=c['omitted_stop_ids'],
                     omitted_names=c['omitted_names'],comparison_not_adopted=True,
                     solver_time_limit_seconds=time_limit,
                     source_fingerprints=source_fingerprints(policy,c['loops']))
            if r['witness_found']:
                r['maximum_fs_onboard_hold_by_scenario']=[
                    dict(moving_multiplier=m,dwell_min=d,
                         maximum_wait_min=max(q['intermediate_offset_min']-g[first]['road_minutes']
                                              for q in r['full_trips']))
                    for (m,d),g in wing_offsets(c['loops']).items()]
                r['maximum_fs_onboard_hold_over_nine_scenarios_min']=max(
                    v['maximum_wait_min'] for v in r['maximum_fs_onboard_hold_by_scenario'])
            print(c['omitted_names'],first,r['solver_status'],r['witness_found'],
                  r.get('maximum_fs_onboard_hold_over_nine_scenarios_min'),flush=True)
            cases.append(r)
    witnesses=[c for c in cases if c['witness_found']]
    return dict(contract='RT031_LINE8_FIXED_PATH_MAXIMUM_HOLD_CLOSURE_DIAGNOSTIC_V3',
        cut_source_sha256=hashlib.sha256(source_bytes).hexdigest(),cases=cases,
        conclusion='CONDITIONAL_HOLD_LIMIT_IDENTIFIED_NOT_A_FINAL_PROPOSAL',
        all_cases_resolved_in_this_run=all(c['solver_status'] in (0,2) for c in cases),
        lowest_maximum_hold_over_nine_scenarios_in_resolved_comparison_min=(
            min(c['maximum_fs_onboard_hold_over_nine_scenarios_min'] for c in witnesses)
            if witnesses and all(c['solver_status'] in (0,2) for c in cases) else None),
        lowest_hold_is_not_a_network_or_utility_selection=True,
        retained_within_wing_ride_times_cannot_change_by_root_departure_shift=True,
        caller_tradeoff_adoption_missing=True,
        remaining_approval_domains=['17_trips_instead_of_adopted_16',
          'explicit_stop_exclusions_and_territorial_losses','specific_extra_service_km',
          'service_phase_and_rail_targets','passenger_journey_and_holding_acceptability',
          'calendar_fleet_physical_boarding_and_full_history_road_validation'],
        semantics='Same four unadopted geometries below the specific 16-trip kilometer '
          'comparison. Test 17 complete trips in each fixed wing sequence, same retained '
          'event order, H60 readiness shoulders, H120 only 10-16, nine runtime/dwell '
          'scenarios, five-minute grid, max intermediate offset85, four actual archived '
          'five-train H30 banks. Minimising maximum intermediate offset is equivalent '
          'to minimising maximum onboard holding for every fixed first-wing runtime '
          'scenario: each runtime is a constant subtraction. Status0 certifies that '
          'conditional minimax optimum only; timeout is not a negative certificate. '
          'Changing root times cannot change the fixed within-wing ride times. '
          'These are not empirical probabilities, actual driving times or a full '
          'network/Pareto optimum. No trip, stop, budget, fleet or service adoption.',
        trip_count_adopted=False,stop_omissions_adopted=False,calendar_adopted=False,
        physical_bus_operation_certified=False,candidate_domain_complete=False,
        network_selected=False,primary_selection_authorised=False,
        runner_up_selection_authorised=False,decision_budget_km=None,uncertainty_band_min=None)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--time-limit',type=int,default=30)
    a=p.parse_args();r=build(a.time_limit)
    OUTPUT.write_bytes(gzip.compress((json.dumps(r,sort_keys=True,ensure_ascii=False,
        separators=(',',':'))+'\n').encode('utf-8'),mtime=0))
