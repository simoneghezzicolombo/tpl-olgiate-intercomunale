import json

import pytest

from scripts.phase2_audit_rt031_internal_transfer_margins_v3 import OUTPUT, build


@pytest.fixture(scope='module')
def audit():
    return build()


def case(audit, advance, delay):
    return next(r for r in audit['phase_comparisons']
                if r['east_am_advance_min'] == advance and r['west_trips_9_to_15_delay_min'] == delay)


def test_baseline_has_tiny_or_zero_margins_not_empirical_reliability(audit):
    banks = {(r['wing'], r['kind']): r for r in audit['baseline_bank_margins_assumed_3min_walk']}
    assert banks['east_A', 'bus_to_rail']['minimum_residual_margin_min'] == pytest.approx(.2234063721)
    assert banks['west_B', 'rail_to_bus']['minimum_residual_margin_min'] == 0
    assert all(r['event_count'] == 5 and not r['observed_walk_or_delay'] for r in banks.values())
    alternate = {(r['wing'], r['kind']): r for r in audit['diagnostic_5min_walk_not_adopted']}
    assert alternate['east_A', 'bus_to_rail']['minimum_residual_margin_min'] < 0
    assert alternate['west_B', 'rail_to_bus']['minimum_residual_margin_min'] == -2
    assert audit['uncertainty_band_min'] is None and audit['missed_connection_probability'] is None


def test_simple_am_advance_can_harm_reverse_flows_and_increase_fleet(audit):
    four = case(audit, 4, 0)
    assert four['event_readiness_and_complete_trip_checks_pass']
    assert four['maximum_model_vehicles'] == 4
    assert four['additional_commercial_km'] == 0
    assert four['additional_full_trip_service_min_per_day'] == 20
    assert four['maximum_increase_in_nominal_rail_to_bus_wait_min'] == 55
    assert any(r['train_arrival_min'] == 362 and r['old_rail_to_bus_wait_min'] == 3
               and r['new_rail_to_bus_wait_min'] == 29 for r in four['rail_flow_changes'])
    five = case(audit, 5, 0)
    assert five['maximum_model_vehicles'] == 5
    assert any(c['minimum_model_vehicles'] == 5 and len(c['overlap_witness']['simultaneous_full_trip_numbers']) == 5
               for c in five['all_27_vehicle_cases'])


def test_small_pm_repair_is_computable_but_not_an_unqualified_improvement(audit):
    two = case(audit, 0, 2)
    assert two['event_readiness_and_complete_trip_checks_pass']
    assert two['maximum_model_vehicles'] == 4
    assert two['additional_commercial_km'] == 0 and two['additional_full_trip_service_min_per_day'] == 14
    assert two['lost_previous_all_nine_case_bus_to_rail'] == []
    assert two['maximum_increase_in_nominal_rail_to_bus_wait_min'] == 2
    assert len(case(audit, 0, 3)['lost_previous_all_nine_case_bus_to_rail']) == 7
    assert not case(audit, 0, 5)['event_readiness_and_complete_trip_checks_pass']


def test_all_flows_recomputed_without_selecting_or_adopting_a_new_timetable(audit):
    for row in audit['phase_comparisons']:
        assert row['rail_call_count'] == 74
        assert row['wing_train_rows_checked'] == 148
        assert row['transfer_flow_combinations_checked'] == 296
        assert len(row['all_27_vehicle_cases']) == 27
        assert row['full_trip_count'] == 16
        assert not row['proposed_timetable_adopted'] and not row['full_service_event_ledger_rebuilt']
    for flag in ('design_engineering_solidification_complete', 'best_phase_selected',
                 'caller_uncertainty_band_selected', 'physical_operation_certified',
                 'rail_2027_certified', 'primary_selection_authorised', 'runner_up_selection_authorised'):
        assert audit[flag] is False


def test_saved_audit_reproduces(audit):
    assert json.loads(OUTPUT.read_text(encoding='utf-8')) == audit
