"""All dated rail flows on corrected design events; old 17-trip times diagnostic only."""
from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path

from scripts.phase2_audit_rt031_line8_dwell_sensitivity_v3 import adjusted_loops

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'outputs/phase2/rt031_line8_local_shortcuts_v3'
DESIGN=BASE/'calco_centre_adopted_design.json'
RAIL=BASE/'all_station_rail_20261001.json'
REFERENCE=BASE/'conditional_proposal_17_trips.json'
OUTPUT=BASE/'current_rail_connections_corrected_design.json'


def connection_row(train, wing, departures, durations, walk=3):
    if walk < 0: raise ValueError('Nonnegative transfer assumption required')
    onward=next((d for d in departures if d>=train['arrival_min']+walk),None) if train['ordinary_alighting_supported'] else None
    nominal=durations[(1.1,.5)]
    nominal_arrivals=[d+nominal for d in departures]
    possible=[a for a in nominal_arrivals if a+walk<=train['departure_min']]
    latest=max(possible,default=None) if train['ordinary_boarding_supported'] else None
    same_bus=[]
    if latest is not None:
        chosen_departure=departures[nominal_arrivals.index(latest)]
        same_bus=[dict(runtime_multiplier=m,dwell_per_event_min=d,
            bus_arrival_min=chosen_departure+duration,
            margin_after_assumed_transfer_min=train['departure_min']-chosen_departure-duration-walk,
            deterministically_feasible=chosen_departure+duration+walk<=train['departure_min'])
            for (m,d),duration in sorted(durations.items())]
    return dict(wing=wing,trip_id=train['trip_id'],train_number=train['train_number'],
        train_direction=train['direction'],train_origin=train['origin_name'],train_destination=train['destination_name'],
        train_arrival_min=train['arrival_min'],train_departure_min=train['departure_min'],
        rail_to_bus=dict(ordinary_alighting_supported=train['ordinary_alighting_supported'],
            next_wing_departure_min=onward,wait_from_train_arrival_min=None if onward is None else onward-train['arrival_min'],
            inherited_3_to_8_min_test=onward is not None and 3<=onward-train['arrival_min']<=8),
        bus_to_rail=dict(ordinary_boarding_supported=train['ordinary_boarding_supported'],
            latest_nominal_bus_arrival_min=latest,wait_to_train_departure_min=None if latest is None else train['departure_min']-latest,
            same_nominal_bus_engineering_cases=same_bus,
            same_bus_feasible_in_all_nine_cases=bool(same_bus) and all(r['deterministically_feasible'] for r in same_bus)))


def build():
    design=json.loads(DESIGN.read_text(encoding='utf-8'))
    rail=json.loads(RAIL.read_text(encoding='utf-8'))
    reference=json.loads(REFERENCE.read_text(encoding='utf-8'))
    if not rail['ready_for_dated_rail_diagnostic']: raise ValueError('Rail scope/calendar reconciliation unresolved')
    if not design['selected_design_stop']['design_position_adopted'] or design['network_selected']:
        raise ValueError('Unexpected design authority')
    if reference['wing_sequence']!=design['wing_sequence']: raise ValueError('Full-route order drift')
    departures={wing:sorted(t['first_fs_min' if wing=='east_A' else 'second_fs_min'] for t in reference['full_trips']) for wing in design['loops']}
    durations={wing:{} for wing in design['loops']}
    for m,d in itertools.product((.9,1.,1.1),(0.,.5,1.)):
        adjusted=adjusted_loops(design['loops'],m,d)
        for wing,loop in adjusted.items(): durations[wing][m,d]=loop['road_minutes']
    rows=[connection_row(train,wing,departures[wing],durations[wing]) for wing in design['loops'] for train in rail['events']]
    holds=[]
    for t in reference['full_trips']:
        hold=t['second_fs_min']-t['first_fs_min']-durations['east_A'][1.1,.5]
        minimum=t['second_fs_min']-t['first_fs_min']-max(durations['east_A'].values())
        holds.append(dict(first_fs_min=t['first_fs_min'],second_fs_min=t['second_fs_min'],nominal_hold_min=hold,
            minimum_hold_over_nine_cases_min=minimum,feasible_without_negative_hold_in_nine_cases=minimum>=0))
    summary=[]
    for wing,direction in itertools.product(design['loops'],('MILANO','LECCO')):
        for flow,key,start,end in (('RAIL_TO_BUS','rail_to_bus',960,1200),('BUS_TO_RAIL','bus_to_rail',390,570)):
            group=[r for r in rows if r['wing']==wing and r['train_direction']==direction and
                start<=r['train_arrival_min' if flow=='RAIL_TO_BUS' else 'train_departure_min']<=end]
            waits=[r[key]['wait_from_train_arrival_min' if flow=='RAIL_TO_BUS' else 'wait_to_train_departure_min'] for r in group]
            summary.append(dict(wing=wing,direction=direction,flow=flow,reporting_window_min=[start,end],
                train_count=len(group),no_eligible_bus_count=sum(w is None for w in waits),
                min_wait_min=min((w for w in waits if w is not None),default=None),
                max_wait_min=max((w for w in waits if w is not None),default=None)))
    # A concrete zero-distance PM comparison: advance first-wing departures
    # three minutes, keep the same trip's second-wing departure fixed. This
    # INCREASES intermediate FS holding, does not shorten the complete trip,
    # add a reverse service or silently alter the adopted daily trip count.
    pm_comparison=[]
    shifted=[d-3 if 970<=d<=1090 else d for d in departures['east_A']]
    for train in rail['events']:
        if train['origin_axis']=='MILANO' and 962<=train['arrival_min']<=1082:
            before=connection_row(train,'east_A',departures['east_A'],durations['east_A'])
            after=connection_row(train,'east_A',shifted,durations['east_A'])
            pm_comparison.append(dict(train_number=train['train_number'],train_arrival_min=train['arrival_min'],
                old_departure_min=before['rail_to_bus']['next_wing_departure_min'],
                compared_departure_min=after['rail_to_bus']['next_wing_departure_min'],
                old_wait_min=before['rail_to_bus']['wait_from_train_arrival_min'],
                compared_wait_min=after['rail_to_bus']['wait_from_train_arrival_min']))
    return dict(contract='RT031_CURRENT_ALL_RAIL_CORRECTED_DESIGN_DIAGNOSTIC_V3',service_date=rail['service_date'],
        all_calling_trains_in_reconciled_sources=True,event_count=rail['event_count'],row_count=len(rows),rows=rows,
        example_schedule=dict(reference=str(REFERENCE.relative_to(ROOT)),full_trip_count=len(reference['full_trips']),
            caller_adopted_trip_count=reference['caller_adopted_full_trips_per_day'],trip_count_change_adopted=False,
            public_timetable_adopted=False,departures_min=departures,
            corrected_nominal_duration_min={w:durations[w][1.1,.5] for w in durations},intermediate_holds=holds,
            negative_hold_in_any_inherited_case=any(not h['feasible_without_negative_hold_in_nine_cases'] for h in holds)),
        reporting_window_summary=summary,
        unadopted_zero_km_pm_phase_comparison=dict(
            first_wing_departure_change_min=-3,second_wing_departure_change_min=0,
            first_wing_reporting_window_min=[970,1090],affected_full_trip_count=5,
            additional_service_distance_m=0,additional_nominal_intermediate_hold_min_per_affected_trip=3,
            preserves_existing_five_departure_h30_bank=True,
            other_rail_flows_not_guaranteed=True,comparison_not_adopted=True,
            compared_departures_min=shifted,examples=pm_comparison),
        transfer_walk_assumption_min=3,
        transfer_walk_observed_or_caller_declared=False,rail_to_bus_inherited_test_window_min=[3,8],
        bus_to_rail_new_maximum_wait_declared=None,
        source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (DESIGN,RAIL,REFERENCE)},
        semantics='Recompute exact corrected route-event moving/dwell durations, enumerate every dated calling train and both transfer flows for each wing of ONE full-trip line. Preserve the old 17-trip schedule ONLY as an explicitly unadopted diagnostic; do not turn it into the adopted 16-trip service. Waits are scheduled nominal calculations, not quality guarantees. Nine moving/dwell engineering cases stress the SAME nominal connecting bus, not nine observed trials and not an empirical probability. Arrival and departure are separate; GTFS after-midnight service-day times retained. No weights, invented priorities, annual calendar, reverse line or public schedule selection.',
        route_od_available=False,missed_connection_probability=None,demand_weighted_gjt_improvement_min=None,
        physical_passenger_continuity_certified=False,calendar_adopted=False,
        bidirectional_h30_action_deferred=True,network_selected=False,
        primary_selection_authorised=False,runner_up_selection_authorised=False,
        decision_budget_km=None,uncertainty_band_min=None)


if __name__=='__main__':
    result=build(); OUTPUT.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(summary=result['reporting_window_summary'],schedule=result['example_schedule']),ensure_ascii=False))
