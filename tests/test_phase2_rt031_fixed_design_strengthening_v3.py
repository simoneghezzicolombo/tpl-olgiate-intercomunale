"""Regression gates for disclosed local repairs, not an operating certificate."""
import copy
import hashlib
import json

import pytest

from scripts.phase2_strengthen_rt031_fixed_design_v3 import (
    OUTPUT, SHAPE, BRIEF, SOURCE, DESIGN, RAIL, HANDOFF, CALENDAR,
    complete_case, am_phase_bound, scenario_ledger, validate_ledger, splice_one_event,
    canonical_sha256, render_brief,
)


@pytest.fixture(scope='module')
def result():
    return json.loads(OUTPUT.read_text(encoding='utf-8'))


@pytest.fixture(scope='module')
def upstream():
    return [json.loads(p.read_text(encoding='utf-8')) for p in (SOURCE,DESIGN,RAIL)]


def test_authorised_sources_are_pinned_and_unchanged(result):
    assert result['generator_sha256']==hashlib.sha256((OUTPUT.parents[3]/'scripts/phase2_strengthen_rt031_fixed_design_v3.py').read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    for path in (SOURCE,DESIGN,RAIL,HANDOFF,CALENDAR):
        assert result['source_canonical_sha256'][path.name]==canonical_sha256(json.loads(path.read_text(encoding='utf-8')))
    assert not result['timetable_change_adopted']
    for flag in ('network_selected','primary_selection_authorised','runner_up_selection_authorised',
                 'design_engineering_solidification_complete','physical_operation_certified','rail_2027_certified'):
        assert result[flag] is False
    for field in ('decision_budget_km','uncertainty_band_min','missed_connection_probability','demand_weighted_gjt_improvement_min'):
        assert result[field] is None


def test_baseline_and_same_geometry_repair_reproduce_without_cached_graph(result,upstream):
    source,design,rail=upstream
    from scripts.phase2_audit_rt031_internal_transfer_margins_v3 import shifted_schedule
    for saved,schedule in zip(result['completed_comparisons'][:2],(source,shifted_schedule(source,west_delay=2))):
        actual=complete_case(saved['case_id'],schedule,design['loops'],source,design['loops'],rail,254,111419)
        assert actual=={k:v for k,v in saved.items() if k not in (
            'additional_nominal_service_min_per_day_vs_confirmed','additional_nominal_service_hours_2027_vs_confirmed')}


def test_evening_plus2_has_exact_seven_changed_intermediate_departures(result):
    before,after=result['completed_comparisons'][:2]
    differences=[(i+1,b[0]-a[0],b[1]-a[1]) for i,(a,b) in enumerate(zip(before['exact_fs_departure_pairs_min'],after['exact_fs_departure_pairs_min'])) if a!=b]
    assert differences==[(i,0,2) for i in range(9,16)]
    assert after['weekday_commercial_km']==before['weekday_commercial_km']
    assert after['additional_nominal_service_min_per_day_vs_confirmed']==14
    assert after['additional_nominal_service_hours_2027_vs_confirmed']==pytest.approx(59.2666666667)


def test_all_rebuilt_ledger_scenarios_and_blocks_are_present(result):
    for case in result['completed_comparisons']:
        assert len(case['event_ledger_witnesses'])==9
        assert len(case['all_27_complete_vehicle_blocks'])==27
        assert case['maximum_conditional_vehicles']==4
        assert case['all_nine_event_ledgers_rebuilt_and_validated']
        for ledger in case['ordered_service_event_ledgers'].values():
            assert len(ledger)==16
            for trip in ledger:
                assert len(trip['events'])==31
                assert sum(e['role']=='DESIGN_STOP_OCCURRENCE' for e in trip['events'])==28
        for c in case['all_27_complete_vehicle_blocks']:
            assignments=[i for b in c['vehicles'] for i in b['complete_trip_numbers']]
            assert sorted(assignments)==list(range(1,17))
            assert all(b['same_model_vehicle_through_intermediate_fs'] for b in c['vehicles'])


def test_same_stop_identity_cannot_hide_missing_occurrence(upstream):
    source,design,_=upstream
    ledger=scenario_ledger(design['loops'],source['full_trips'],1.1,.5)
    corrupted=copy.deepcopy(ledger)
    del corrupted[0]['events'][1]
    with pytest.raises(ValueError,match='occurrence'):
        validate_ledger(corrupted,design['loops'],source['full_trips'])
    corrupted=copy.deepcopy(ledger)
    intermediate=next(e for e in corrupted[0]['events'] if e['role']=='INTERMEDIATE_FS_STAY_ONBOARD_DESIGN')
    intermediate['physical_continuity_certified']=True
    with pytest.raises(ValueError,match='Vehicle continuity'):
        validate_ledger(corrupted,design['loops'],source['full_trips'])


def test_all_rail_flows_recomputed_and_counterpart_harms_are_explicit(result):
    for case in result['completed_comparisons']:
        assert case['wing_train_rows_checked']==148
        assert case['transfer_flow_combinations_checked']==296
        assert {r['train_direction'] for r in case['all_dated_rail_rows']}=={'MILANO','LECCO'}
        assert case['lost_previous_all_nine_case_bus_to_rail']==[]
        assert case['newly_unavailable_bus_to_rail']==case['newly_unavailable_rail_to_bus']==[]
    for case in result['completed_comparisons'][1:]:
        assert case['maximum_increase_in_rail_to_bus_wait_min']==2
        bank=next(b for b in case['bank_margins_assumed_3min_walk'] if b['wing']=='west_B' and b['kind']=='rail_to_bus')
        assert bank['minimum_residual_margin_min']==2


def test_scarpone_bypass_explicitly_relocates_not_just_preserves_identity(result):
    road=result['road_comparison']
    assert not road['fixed_original_attachment_without_service_edges_reachable']
    assert road['bypass_without_attachment_reachable']
    assert road['distance_delta_m']==pytest.approx(25.8394562335)
    assert road['evaluated_attachment_hypothesis']['graph_attachment_displacement_m']==pytest.approx(17.8909393624)
    assert road['revised_route_audit']['full_trip_directed_edge_count']==1447
    assert not road['revised_route_audit']['immediate_edge_reversals']
    assert not road['revised_route_audit']['service_road_segments']
    assert not road['represented_via_node_violations']
    for f in ('physical_stop_siting_selected','physical_attachment_adopted','geometry_adopted',
              'full_history_legality_certified','bus_suitability_certified'):
        assert road[f] is False


def test_splice_fails_closed_when_another_stop_would_move(upstream):
    _,design,_=upstream
    loop=copy.deepcopy(design['loops']['west_B'])
    event=copy.deepcopy(loop['events'][0]);event.update(stop_place_id='ANOTHER',path_node_index=185)
    loop['events'].append(event)
    with pytest.raises(ValueError,match='another occurrence'):
        splice_one_event(loop,180,191,[],None,{},'west_B')


def test_pedestrian_coverage_recomputed_instead_of_asserted_by_stop_name(result):
    walk=result['walking_comparison']
    assert walk['confirmed_baseline_reproduced']
    assert len(walk['hypothesis_coverage_fraction'])==6
    assert walk['hypothesis_coverage_fraction']==walk['baseline_coverage_fraction']
    assert all(v==0 for values in walk['change_percentage_points'].values() for v in values.values())
    assert all(v=='0' for values in walk['gross_previously_covered_fraction_lost'].values() for v in values.values())
    assert not walk['physical_walking_or_boarding_access_certified']
    assert not walk['passenger_demand_inferred']
    assert result['completed_comparisons'][2]['weekday_commercial_km']==pytest.approx(110334.947574727)


def test_am_bound_is_a_necessary_paired_flow_constraint_not_a_selected_margin(result,upstream):
    source,design,rail=upstream
    bound=am_phase_bound(source,design['loops'],rail)
    assert bound==result['am_paired_flow_phase_bound']
    assert len(bound['pairs'])==5
    assert bound['worst_east_duration_min']==pytest.approx(47.7765936279)
    for pair in bound['pairs']:
        assert pair['available_common_phase_interval_min']==pytest.approx(.2234063721)
        assert pair['maximum_equal_residual_margin_by_retiming_only_min']==pytest.approx(.11170318605)
    assert not bound['normative_margin_selected']
    assert not bound['new_service_requirement_adopted']


def test_scarpone_geometry_has_real_basemap_and_two_different_attachments():
    geo=json.loads(SHAPE.read_text(encoding='utf-8'))
    basemap=[f for f in geo['features'] if f['properties']['role']=='BASEMAP_ROAD']
    assert len(basemap)>10 and all(f['properties']['osm_way_id'] for f in basemap)
    sites=[f for f in geo['features'] if f['geometry']['type']=='Point']
    assert len(sites)==2 and sites[0]['geometry']['coordinates']!=sites[1]['geometry']['coordinates']
    assert all(not f['properties']['physical_boarding_authorised'] for f in sites)


def test_readable_brief_reproduces_machine_conclusion(result):
    assert BRIEF.read_text(encoding='utf-8')==render_brief(result)
    assert result['remaining_internal_weakness']=='AM_EAST_PAIRED_FLOW_MARGIN_NOT_RESOLVED_BY_PHASE_ONLY'
