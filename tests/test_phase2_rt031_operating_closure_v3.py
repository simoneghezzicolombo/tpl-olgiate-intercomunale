import copy
import json

import pytest

from scripts.phase2_prepare_rt031_operating_closure_v3 import (
    OUTPUT, build, render_brief, resource_quantities, service_event_forms,
)


@pytest.fixture(scope='module')
def pack():
    return build()


def test_fixed_weekday_quantities_do_not_become_driver_hours_or_cost(pack):
    bill = pack['weekday_bill_of_quantities']
    assert bill['days_before_local_exceptions'] == 254
    assert bill['full_commercial_trips'] == 4064
    assert bill['commercial_km'] == pytest.approx(110229.9360245941)
    assert bill['nominal']['daily_complete_trip_service_hours'] == pytest.approx(24.7140543479)
    assert bill['nominal']['weekday_annual_complete_trip_service_hours'] == pytest.approx(6277.3698043612)
    for key in ('nominal', 'slower_dwell_recovery'):
        case = bill[key]
        assert case['maximum_simultaneously_occupied_model_vehicles'] == 4
        assert case['daily_vehicle_occupation_hours_including_terminal_recovery']-case['daily_complete_trip_service_hours'] == pytest.approx(16*case['terminal_recovery_min']/60)
        for block in case['blocks']:
            gaps = sum(g['duration_min'] for g in block['uncommitted_gaps_after_recovery'])/60
            assert block['first_to_last_block_span_hours'] == pytest.approx(block['occupation_hours_including_terminal_recovery']+gaps)
            assert all(g['duration_min'] >= 0 and not g['other_work_or_depot_travel_authorised']
                       for g in block['uncommitted_gaps_after_recovery'])
        assert not case['hours_are_driver_duties'] and not case['gaps_are_certified_redeployment']
        assert not case['fleet_availability_certified'] and case['cost_eur'] is None
    for key in ('annual_noncommercial_km', 'payable_driver_hours', 'actual_dedicated_fleet_count',
                'capital_works_cost_eur', 'operating_cost_eur', 'funding_amount_eur'):
        assert bill[key] is None


def test_four_bus_occupation_is_explicit_not_an_all_day_dedicated_fleet(pack):
    case = pack['weekday_bill_of_quantities']['nominal']
    at_735 = next(c for c in case['concurrent_vehicle_occupation']
                  if c['begin_min'] <= 455 < c['end_min'])
    assert at_735['occupied_full_trip_numbers'] == [1, 2, 3, 4]
    assert at_735['occupied_vehicle_count'] == 4
    assert any(c['occupied_vehicle_count'] < 4 for c in case['concurrent_vehicle_occupation'])
    assert [b['complete_trip_numbers'] for b in case['blocks']] == [
        [1, 5, 9, 13], [2, 6, 10, 14], [3, 7, 11, 15], [4, 8, 12, 16]]


def test_occurrence_and_fs_role_approvals_remain_independent(pack):
    forms = pack['directional_service_event_forms']
    assert len(forms) == len({f['event_id'] for f in forms}) == 31
    assert len({f['site_id'] for f in forms}) == 27
    for name in ('Olgiate sud', 'San Zeno/Via Cantu'):
        rows = [f for f in forms if f['name'] == name]
        assert len(rows) == 2 and rows[0]['event_id'] != rows[1]['event_id']
        assert rows[0]['nominal_event_times_by_full_trip'] != rows[1]['nominal_event_times_by_full_trip']
    assert len([f for f in forms if f['event_id'].startswith('FS::')]) == 3
    for form in forms:
        assert len(form['nominal_event_times_by_full_trip']) == 16
        assert not form['physical_service_event_authorised']
        assert form['actual_platform_id'] is None and form['evidence_refs'] == []
        assert form['boarding_permission'] is None and form['alighting_permission'] is None


def test_saturday_arithmetic_is_not_a_service_selection(pack):
    saturday = pack['saturday_scope']
    assert saturday['nonholiday_saturday_count'] == 50
    assert saturday['annual_km_increment_for_one_full_trip_each_saturday'] == pytest.approx(1356.1753940034)
    assert saturday['delta_vs_published_reference_km'] == pytest.approx(167.1114185975)
    assert saturday['at_most_full_trips_in_remaining_arithmetic_margin'] == 43
    assert saturday['caller_selection'] is None and saturday['exact_departures'] is None
    assert saturday['complete_line_annual_commercial_km'] is None
    assert not saturday['useful_saturday_service_certified']


def test_pending_external_proofs_cannot_be_reported_as_approval(pack):
    assert len(pack['closure_items']) == len({i['id'] for i in pack['closure_items']}) == 12
    assert sum(i['blocking_weekday_operational_claim'] for i in pack['closure_items']) == 10
    assert all(i['status'] == 'PENDING_EXTERNAL_EVIDENCE' and not i['evidence_refs']
               for i in pack['closure_items'])
    for flag in ('physical_operation_ready', 'all_service_events_authorised',
                 'complete_annual_operating_calendar_adopted', 'funding_secured',
                 'network_selected', 'primary_selection_authorised', 'runner_up_selection_authorised'):
        assert pack[flag] is False
    for field in ('decision_budget_km', 'uncertainty_band_min', 'missed_connection_probability',
                  'demand_weighted_gjt_improvement_min'):
        assert pack[field] is None
    assert not pack['rail_review']['whole_2027_connections_certified']
    assert not pack['rail_review']['claims_all_2027_timetables_globally_unpublished']


def test_invalid_blocks_fail_closed_and_missing_event_does_not_inherit_identity_approval():
    from scripts.phase2_prepare_rt031_operating_closure_v3 import BLOCKS, HANDOFF
    case = json.loads(BLOCKS.read_text(encoding='utf-8'))['nominal_case']
    invalid = copy.deepcopy(case)
    invalid['vehicles'][0]['complete_trip_numbers'][1] = 1
    with pytest.raises(ValueError, match='omit or duplicate'):
        resource_quantities(invalid, 254)
    with pytest.raises(ValueError, match='Positive integer'):
        resource_quantities(case, 0)
    handoff = json.loads(HANDOFF.read_text(encoding='utf-8'))
    invalid = copy.deepcopy(handoff)
    invalid['ordered_stop_event_ledger_nominal'][5]['events'].pop(1)
    with pytest.raises(ValueError, match='every complete trip exactly once'):
        service_event_forms(invalid)


def test_materialised_pack_and_brief_reproduce_exactly(pack):
    assert json.loads(OUTPUT.read_text(encoding='utf-8')) == pack
    brief = render_brief(pack)
    assert '110.229,936' in brief and '31 schede indipendenti' in brief
    assert 'Non sono ore autista' in brief
    assert 'compilare una copia separata' in brief


def test_upstream_timetable_drift_cannot_be_accepted(monkeypatch):
    import scripts.phase2_prepare_rt031_operating_closure_v3 as module
    changed = json.loads(module.HANDOFF.read_text(encoding='utf-8'))
    changed['full_trips'][0]['first_fs_min'] -= 1
    monkeypatch.setattr(module, 'handoff_build', lambda: changed)
    with pytest.raises(ValueError, match='upstream source drift: handoff'):
        module.load_inputs()
