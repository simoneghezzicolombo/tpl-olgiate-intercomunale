"""One explicit 16-trip proposal for caller review; no network selection."""
import copy
import hashlib
import json
from pathlib import Path

from scripts.phase2_close_rt031_current_16_trip_timetable_v3 import BASE, DESIGN, RAIL
from scripts.phase2_probe_rt031_line8_variable_fs_hold_v3 import wing_offsets
from scripts.phase2_audit_rt031_line8_passenger_peaks_v3 import uncovered_intervals
from scripts.phase2_audit_rt031_line8_current_rail_connections_v3 import connection_row

SOURCE=BASE/'current_16_trip_timetable_step5_H60_mid55_PM8_AMinherited_flexible_real_trains_core980_eastfree.json'
OUTPUT=BASE/'current_16_trip_proposal_for_caller_review.json'


def verify_schedule(schedule,loops):
    trips=schedule['full_trips']; offsets=wing_offsets(loops)
    if len(trips)!=16 or len({t['first_fs_min'] for t in trips})!=16 or len({t['second_fs_min'] for t in trips})!=16:
        raise ValueError('Not sixteen complete distinct trips')
    times={'east_A':[t['first_fs_min'] for t in trips],'west_B':[t['second_fs_min'] for t in trips]}
    failures=[]
    for scenario,g in offsets.items():
        for wing,loop in g.items():
            for sid,site in loop['sites'].items():
                for direction in ('to_fs','from_fs'):
                    opportunities=[t+site[direction] for t in times[wing]]
                    for lo,hi,wait in schedule['ready_windows_min']:
                        gaps=uncovered_intervals(opportunities,lo,hi,wait)
                        if gaps: failures.append((scenario,wing,sid,direction,lo,hi,gaps))
    if failures: raise ValueError(f'Ready-time violation: {failures[:2]}')
    for trip in trips:
        for g in offsets.values():
            if trip['second_fs_min']-trip['first_fs_min'] < g['east_A']['road_minutes']+1-1e-8:
                raise ValueError('Intermediate FS departure precedes arrival plus assumed public dwell')
    banks=schedule['selected_real_train_banks_not_adopted']
    if len(banks)!=4 or any(len(b['bus_departures_min'])!=5 or
        any(y-x!=30 for x,y in zip(b['bus_departures_min'],b['bus_departures_min'][1:])) for b in banks):
        raise ValueError('Four complete H30 banks required')
    assignments=schedule['rail_assignments']
    if len(assignments)!=20 or len({(a['wing'],a['kind'],a['wing_fs_departure_min']) for a in assignments})!=20:
        raise ValueError('Twenty distinct flow-event assignments required')
    for bank in banks:
        if any(t not in times[bank['wing']] for t in bank['bus_departures_min']):
            raise ValueError('H30 bank departure not in complete timetable')
        if any(b-a!=30 for a,b in zip(bank['rail_minutes'],bank['rail_minutes'][1:])):
            raise ValueError('H30 train sequence not consecutive')
        for rail_min,dep in zip(bank['rail_minutes'],bank['bus_departures_min']):
            if not any(a['wing']==bank['wing'] and a['kind']==bank['kind'] and
                       a['rail_min']==rail_min and a['wing_fs_departure_min']==dep for a in assignments):
                raise ValueError('Train bank not supported by distinct assignments')
    return times,offsets


def build():
    schedule=json.loads(SOURCE.read_text(encoding='utf-8'))
    design=json.loads(DESIGN.read_text(encoding='utf-8'));rail=json.loads(RAIL.read_text(encoding='utf-8'))
    if not schedule['witness_found'] or not rail['ready_for_dated_rail_diagnostic']:
        raise ValueError('Unverified upstream schedule or rail scope')
    times,offsets=verify_schedule(schedule,design['loops'])
    durations={wing:{s:g[wing]['road_minutes'] for s,g in offsets.items()} for wing in design['loops']}
    rows=[connection_row(train,w,times[w],durations[w]) for w in design['loops'] for train in rail['events']]
    for assignment in schedule['rail_assignments']:
        kind=assignment['kind']; field='departure_min' if kind=='bus_to_rail' else 'arrival_min'
        direction='MILANO' if kind=='bus_to_rail' else 'LECCO'
        trains=[e for e in rail['events'] if e['direction']==direction and e[field]==assignment['rail_min']]
        if len(trains)!=1: raise ValueError('Chosen train bank event absent/ambiguous')
        t=assignment['wing_fs_departure_min']; w=assignment['wing']
        if t not in times[w]: raise ValueError('Assigned FS departure absent')
        if kind=='bus_to_rail':
            residual=[assignment['rail_min']-t-duration-3 for duration in durations[w].values()]
            if min(residual)<-1e-8 or max(residual)>schedule['compared_am_residual_wait_ceiling_min']+1e-8:
                raise ValueError('Assigned AM engineering window violation')
        elif not 3<=t-assignment['rail_min']<=schedule['compared_pm_train_to_bus_window_min'][1]:
            raise ValueError('Assigned PM transfer violation')
    nominal=offsets[1.1,.5]
    hold_scenarios=[t['second_fs_min']-t['first_fs_min']-g['east_A']['road_minutes'] for t in schedule['full_trips'] for g in offsets.values()]
    service_km=16*design['complete_path_distance_m']/1000*260
    assessment=[
        dict(input='complete_path_and_design_events',state='CALLER_ADOPTED_DESIGN_NOT_PHYSICAL_APPROVAL',source=str(DESIGN.name),semantics='27 sites incl FS; 28 ordered nonhub events; Mirasole/Cartiglio excluded; Santa Maria kept; one Calco added; same complete eight every trip'),
        dict(input='commercial_full_trip_count',state='CALLER_DECLARED_16',source='config/rt031_16_full_trips_authority_v3.json',semantics='16 FULL circuits, not 31 wing movements renamed; newer site amendments supersede the historical 29-site field'),
        dict(input='dated_all_rail_calls',state='VERIFIED_FOR_2026_10_01',source=str(RAIL.name),semantics='74 active station calls across all routes, exact full-day RFI departure-clock reconciliation; neither all guaranteed nor live disruption data'),
        dict(input='h30_peak_banks',state='WITNESS_VERIFIED_EXACT_PHASES_NOT_ADOPTED',source=SOURCE.name,semantics='Four five-departure actual train banks, 30-minute gaps on each wing; phased peaks, not common 07-09/17-19 at every occurrence or clockwise plus counterclockwise H30'),
        dict(input='offpeak_transition',state='NEEDS_CALLER_CONFIRMATION',source=SOURCE.name,semantics='Diagnostic readiness cap 120 min 10:00-16:20 rather than 10:00-16:00; H60 cap on both shoulders retained. Does not mean a bus departs every 120 minutes until 16:20; inspect exact timetable'),
        dict(input='moving_dwell_recovery',state='INHERITED_ENGINEERING_SCENARIOS_NOT_EMPIRICAL',source='src/phase2_rt031_frequent_access_shortlist_v3.py',semantics='9 moving/dwell cases, 27 incl recovery; no observed dwell or delay probability and no caller uncertainty band inferred'),
        dict(input='rail_transfer_wait',state='INHERITED_DIAGNOSTIC_NOT_NEW_AUTHORITY',source=SOURCE.name,semantics='3-min walking assumption, PM 3-8 and inherited AM residual ceiling; useful/missing all-direction waits exposed separately, no normative demand weights'),
        dict(input='annual_service_days',state='260_DAY_COMPARISON_ONLY',source='config/rt031_16_full_trips_authority_v3.json',semantics='Not adopted annual calendar; no weekends or holidays silently counted'),
        dict(input='decision_budget_km',state='CALLER_INPUT_UNDECLARED',source='config/rt031_16_full_trips_authority_v3.json',semantics='null; 111419 is reference, not an invented current Decision Contract ceiling'),
        dict(input='uncertainty_band_min',state='CALLER_INPUT_UNDECLARED',source='config/rt031_16_full_trips_authority_v3.json',semantics='null; deterministic engineering grid cannot supply it'),
        dict(input='demand_weighted_gjt_improvement_min',state='UNSUPPORTED_NULL',source='Certified municipal work OD not route/passenger downscaled',semantics='No inferred passenger-demand weighted result'),
        dict(input='missed_connection_probability',state='UNSUPPORTED_NULL',source='Engineering sensitivity only',semantics='No deterministic failure ratio reinterpreted as empirical probability')]
    return dict(contract='RT031_CURRENT_16_TRIP_PROPOSAL_FOR_CALLER_REVIEW_V3',
        status='VERIFIED_BOUNDED_TIMETABLE_WITNESS_ONE_TRANSITION_CHANGE_REQUIRES_CALLER_CONFIRMATION',
        public_route_name='Linea 8',public_wing_sequence=['east_A','west_B'],
        full_trip_count=16,served_design_site_count_including_fs=27,complete_path_distance_m=design['complete_path_distance_m'],
        full_trips=schedule['full_trips'],ordered_stop_event_ledger_nominal=schedule['ordered_stop_event_ledger_nominal'],
        intended_same_vehicle_and_stay_onboard_per_complete_trip=True,
        physical_passenger_continuity_certified=False,all_trips_same_complete_path=True,
        adopted_new_bidirectional_service=False,comparison_ready_windows_min=schedule['ready_windows_min'],
        proposed_transition_end_min=980,transition_extension_adopted=False,
        exact_peak_phases_require_caller_confirmation=True,
        h30_banks=schedule['selected_real_train_banks_not_adopted'],
        old_22_target_compatibility=schedule['original_22_target_compatibility_full_timetable'],
        all_current_rail_flows=rows,all_rail_connections_guaranteed=False,
        nominal_wing_duration_min={w:g['road_minutes'] for w,g in nominal.items()},
        nominal_intermediate_fs_hold_range_min=[min(t['intermediate_offset_min']-nominal['east_A']['road_minutes'] for t in schedule['full_trips']),max(t['intermediate_offset_min']-nominal['east_A']['road_minutes'] for t in schedule['full_trips'])],
        engineering_intermediate_fs_hold_range_min=[min(hold_scenarios),max(hold_scenarios)],
        last_nominal_return_to_fs_min=schedule['full_trips'][-1]['second_fs_min']+nominal['west_B']['road_minutes'],
        vehicle_cases_conditional=schedule['vehicle_cases_conditional'],fleet_or_operator_availability_certified=False,
        annual_service_km_260_day_comparison=service_km,annual_noncommercial_km=None,
        difference_vs_111419_reference_km=service_km-111419,
        difference_vs_111419_reference_percent=100*(service_km/111419-1),
        calendar_adopted=False,requirements_readiness=assessment,
        coverage_fraction=design['coverage_fraction'],physical_boarding_authorised=False,
        detailed_timetable_adopted=False,network_selected=False,
        primary_selection_authorised=False,runner_up_selection_authorised=False,
        demand_weighted_gjt_improvement_min=None,missed_connection_probability=None,
        decision_budget_km=None,uncertainty_band_min=None,
        source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (SOURCE,DESIGN,RAIL)},
        semantics='One concrete non-decisional 16-trip timetable example on the caller-adopted path. Independent exact checks of event readiness in all inherited engineering scenarios, full-trip continuity and four actual-train H30 banks. All railway directions/flows disclosed without weights. Not a global optimum or automatically selected network. Requires caller confirmation of the modest diagnostic transition change and external physical/operating approvals. Historical V2 final-tournament probability/GJT fields remain unsupported null.')


if __name__=='__main__':
    result=build();OUTPUT.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('full_trip_count','served_design_site_count_including_fs','annual_service_km_260_day_comparison','difference_vs_111419_reference_percent','nominal_intermediate_fs_hold_range_min','engineering_intermediate_fs_hold_range_min','last_nominal_return_to_fs_min')}))
