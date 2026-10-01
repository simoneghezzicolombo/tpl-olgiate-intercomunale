import json
from scripts.phase2_adopt_rt031_line8_calco_stop_v3 import OUTPUT, AUTH
from scripts.phase2_audit_rt031_line8_current_rail_connections_v3 import connection_row, build


def test_exact_one_adopted_calco_event_no_false_boarding():
    r=json.loads(OUTPUT.read_text(encoding='utf-8'));a=json.loads(AUTH.read_text(encoding='utf-8'))
    events=[e for l in r['loops'].values() for e in l['events']]
    hits=[e for e in events if e['stop_place_id']==a['site_id']]
    assert len(hits)==1 and hits[0]['path_node_index']==520
    assert not hits[0]['physical_boarding_authorised']
    assert not any(e['stop_place_id']==a['removed_site_id'] for e in events)
    assert any(e['stop_place_id']==a['retained_santa_maria_site_id'] for e in events)
    assert r['served_design_site_count_including_fs']==27
    assert r['nonhub_ordered_occurrence_count_per_trip']==28
    assert not r['previous_timetable_transplanted'] and not r['network_selected']
    assert r['decision_budget_km'] is None and r['uncertainty_band_min'] is None


def test_arrival_departure_and_same_bus_stress_not_conflated():
    t=dict(trip_id='t',train_number='1',direction='MILANO',origin_name='Lecco',destination_name='Milano',
        arrival_min=100,departure_min=102,ordinary_alighting_supported=True,ordinary_boarding_supported=True)
    durations={(1.1,.5):10,(1.,1.):15}
    row=connection_row(t,'east_A',[88,103],durations)
    assert row['rail_to_bus']['wait_from_train_arrival_min']==3
    assert row['bus_to_rail']['latest_nominal_bus_arrival_min']==98
    assert row['bus_to_rail']['wait_to_train_departure_min']==4
    assert not row['bus_to_rail']['same_bus_feasible_in_all_nine_cases']


def test_no_bus_is_not_zero_wait_or_connection():
    t=dict(trip_id='t',train_number='1',direction='LECCO',origin_name='Milano',destination_name='Lecco',
        arrival_min=100,departure_min=101,ordinary_alighting_supported=False,ordinary_boarding_supported=False)
    r=connection_row(t,'west_B',[80,105],{(1.1,.5):10})
    assert r['rail_to_bus']['wait_from_train_arrival_min'] is None
    assert r['bus_to_rail']['latest_nominal_bus_arrival_min'] is None


def test_complete_dated_diagnostic_and_zero_km_comparison_not_selected():
    r=build()
    assert r['event_count']==74 and r['row_count']==148
    assert {e['train_direction'] for e in r['rows']}=={'MILANO','LECCO'}
    assert all('rail_to_bus' in e and 'bus_to_rail' in e for e in r['rows'])
    assert r['example_schedule']['full_trip_count']==17
    assert r['example_schedule']['caller_adopted_trip_count']==16
    assert not r['example_schedule']['trip_count_change_adopted']
    c=r['unadopted_zero_km_pm_phase_comparison']
    assert len(c['examples'])==5 and all(e['old_wait_min']==8 and e['compared_wait_min']==5 for e in c['examples'])
    assert c['additional_service_distance_m']==0 and c['comparison_not_adopted']
    assert r['missed_connection_probability'] is None
    assert r['demand_weighted_gjt_improvement_min'] is None
