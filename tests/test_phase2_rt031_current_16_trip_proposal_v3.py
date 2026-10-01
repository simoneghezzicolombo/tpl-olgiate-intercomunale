import copy
import json
import pytest
from scripts.phase2_package_rt031_current_16_trip_proposal_v3 import build, verify_schedule, SOURCE, DESIGN
from scripts.phase2_probe_rt031_line8_variable_fs_hold_v3 import original_target_compatibility


def test_current_16_trip_proposal_is_not_an_adopted_timetable():
    r=build()
    assert r['full_trip_count']==16 and r['served_design_site_count_including_fs']==27
    assert r['all_trips_same_complete_path']
    assert r['annual_service_km_260_day_comparison']==pytest.approx(112833.79278108056)
    assert r['difference_vs_111419_reference_percent']==pytest.approx(1.2697949013009913)
    assert len(r['all_current_rail_flows'])==148
    assert r['old_22_target_compatibility']['distinct_event_matching_count']==19
    assert r['proposed_transition_end_min']==980
    assert not r['transition_extension_adopted'] and not r['detailed_timetable_adopted']
    assert r['exact_peak_phases_require_caller_confirmation']
    assert r['last_nominal_return_to_fs_min']==pytest.approx(1268.3027038045448)
    assert not r['primary_selection_authorised'] and not r['network_selected']
    assert r['decision_budget_km'] is None and r['uncertainty_band_min'] is None
    assert r['missed_connection_probability'] is None and r['demand_weighted_gjt_improvement_min'] is None
    assert {row['input'] for row in r['requirements_readiness']} >= {'offpeak_transition','dated_all_rail_calls','annual_service_days','decision_budget_km','uncertainty_band_min'}


def test_reinstating_16_00_transition_refutes_this_witness_not_all_services():
    schedule=json.loads(SOURCE.read_text(encoding='utf-8'));loops=json.loads(DESIGN.read_text(encoding='utf-8'))['loops']
    schedule['ready_windows_min']=[[410,600,60],[600,960,120],[960,1180,60]]
    with pytest.raises(ValueError,match='Ready-time violation'):verify_schedule(schedule,loops)


def test_complete_trip_and_bank_identity_cannot_be_faked():
    schedule=json.loads(SOURCE.read_text(encoding='utf-8'));loops=json.loads(DESIGN.read_text(encoding='utf-8'))['loops']
    broken=copy.deepcopy(schedule);broken['full_trips'].pop()
    with pytest.raises(ValueError,match='sixteen'):verify_schedule(broken,loops)
    broken=copy.deepcopy(schedule);broken['selected_real_train_banks_not_adopted'][0]['rail_minutes'][0]-=30
    with pytest.raises(ValueError,match='not consecutive'):verify_schedule(broken,loops)


def test_three_minute_pm_advance_from_17_trip_example_does_not_transfer():
    schedule=json.loads(SOURCE.read_text(encoding='utf-8'));loops=json.loads(DESIGN.read_text(encoding='utf-8'))['loops']
    for trip in schedule['full_trips']:
        if 1000<=trip['first_fs_min']<=1120:
            trip['first_fs_min']-=3
            trip['intermediate_offset_min']+=3
    with pytest.raises(ValueError,match='Ready-time violation'):verify_schedule(schedule,loops)


def test_eligibility_overlap_is_not_two_distinct_connections():
    p={'anchors':[dict(wing='east',kind='bus_to_rail',rail_min=t) for t in (100,130)],'wait_ceiling':100}
    offsets={(1.,0.):{'east_A':{'road_minutes':10}}}
    r=original_target_compatibility(p,offsets,{'east_A':[50]})
    assert r['compatible_count']==2
    assert r['eligibility_overlaps_present']
    assert r['distinct_event_matching_count']==1
    assert not r['all_potentially_compatible_targets_have_distinct_events']
