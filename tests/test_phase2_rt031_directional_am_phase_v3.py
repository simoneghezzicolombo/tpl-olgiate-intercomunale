"""Complete phase witnesses cannot certify missing operational transfers."""
import copy
import hashlib
import json

import pytest

from scripts.phase2_complete_rt031_directional_am_phase_v3 import (
    OUTPUT, BRIEF, SOURCE, DESIGN, RAIL, HANDOFF, CALENDAR, PLATFORM, ACCESSIBILITY_REVIEW,
    build, render_brief, evaluate_budget_inputs, approach_flow_changes,
    validate_platform_pairs,
)
from scripts.phase2_package_rt031_confirmed_design_handoff_v3 import canonical_sha256


@pytest.fixture(scope='module')
def result():
    return json.loads(OUTPUT.read_text(encoding='utf-8'))


def test_full_audit_is_reproducible_and_sources_unchanged(result):
    assert result == build()
    assert BRIEF.read_text(encoding='utf-8') == render_brief(result)
    for path in (SOURCE, DESIGN, RAIL, HANDOFF, CALENDAR, PLATFORM, ACCESSIBILITY_REVIEW):
        assert result['source_canonical_sha256'][path.name] == canonical_sha256(json.loads(path.read_text(encoding='utf-8')))
    for name, expected in result['generator_code_sha256'].items():
        path = OUTPUT.parents[3]/'scripts'/name
        assert hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest() == expected


def test_only_disclosed_five_east_departures_move(result):
    base = result['phase_comparisons'][0]['entire_complete_timetable_checks']
    for shift, case in enumerate(result['phase_comparisons']):
        full = case['entire_complete_timetable_checks']
        assert case['east_first_five_departures_delay_min'] == shift
        for i, (a, b) in enumerate(zip(base['exact_fs_departure_pairs_min'], full['exact_fs_departure_pairs_min'])):
            assert b == [a[0]+(shift if i < 5 else 0), a[1]]
        assert full['complete_path_distance_m'] == base['complete_path_distance_m']
        assert full['weekday_commercial_km'] == pytest.approx(110229.9360245941)
        assert full['weekday_service_days'] == 254
        assert full['event_readiness_and_complete_trip_checks_pass']
        assert len(full['h30_banks']) == 4
        assert all([b-a for a, b in zip(bank['bus_departures_min'], bank['bus_departures_min'][1:])] == [30]*4
                   for bank in full['h30_banks'])


def test_every_ordered_occurrence_and_block_is_rebuilt(result):
    for case in result['phase_comparisons']:
        full = case['entire_complete_timetable_checks']
        assert full['all_nine_event_ledgers_rebuilt_and_validated']
        assert len(full['event_ledger_witnesses']) == 9
        assert len(full['all_27_complete_vehicle_blocks']) == 27
        assert full['maximum_conditional_vehicles'] == 4
        for ledger in full['ordered_service_event_ledgers'].values():
            assert len(ledger) == 16
            for trip in ledger:
                assert len(trip['events']) == 31
                assert sum(e['role'] == 'DESIGN_STOP_OCCURRENCE' for e in trip['events']) == 28
        for blockcase in full['all_27_complete_vehicle_blocks']:
            assert sorted(i for b in blockcase['vehicles'] for i in b['complete_trip_numbers']) == list(range(1,17))


def test_shorter_hold_is_not_a_distance_or_driver_cost_saving(result):
    for shift, case in enumerate(result['phase_comparisons']):
        assert case['nominal_full_trip_service_delta_min_per_day'] == -5*shift
        assert case['nominal_full_trip_service_delta_hours_2027'] == pytest.approx(-5*shift*254/60)
        assert case['shorter_intermediate_hold_not_shorter_road_route']
        assert not case['actual_implementation_ready']


def test_diagnostic_disagreement_is_retained_not_cherry_picked(result):
    for shift, case in enumerate(result['phase_comparisons']):
        full = case['entire_complete_timetable_checks']
        assert len(full['all_dated_rail_rows']) == 148
        assert full['transfer_flow_combinations_checked'] == 296
        assert len(case['all_dated_rail_flows_approach_only']) == 148
        assert {r['train_direction'] for r in case['all_dated_rail_flows_approach_only']} == {'MILANO', 'LECCO'}
        assert len(full['lost_previous_all_nine_case_bus_to_rail']) == (0 if shift == 0 else 5)
        diagnosis = case['approach_only_flow_comparison']
        assert diagnosis['lost_previous_same_bus_all_nine_approach_diagnostics'] == []
        assert diagnosis['maximum_increase_in_rail_to_bus_wait_min'] == shift
        assert not diagnosis['all_passenger_connections_certified']


def test_five_exact_pair_expense_limits_and_unmeasured_totals(result):
    for shift, case in enumerate(result['phase_comparisons']):
        pairs = case['paired_directional_total_expense_budgets']
        assert len(pairs) == 5
        assert [p['train_arrival_min'] for p in pairs] == [362,392,422,452,482]
        for pair in pairs:
            assert pair['maximum_inbound_total_expenses_min'] == 3+shift
            assert pair['maximum_outbound_total_expenses_after_worst_bus_model_min'] == pytest.approx(3.2234063721-shift)
            assert pair['observed_inbound_total_expenses_min'] is None
            assert pair['observed_outbound_total_expenses_min'] is None
            assert pair['declared_expense_assessment']['both_fit_event_budgets'] is None
            assert not pair['passenger_connection_certified']
            assert not pair['actual_arrival_platform_certified']


def test_budget_requires_two_directions_no_average_no_certification():
    budget = dict(maximum_inbound_total_expenses_min=4,
                  maximum_outbound_total_expenses_after_worst_bus_model_min=2)
    missing = evaluate_budget_inputs(budget, None, 1)
    assert missing['both_fit_event_budgets'] is None and missing['inbound_residual_min'] is None
    exact = evaluate_budget_inputs(budget, 4, 2)
    assert exact['both_fit_event_budgets'] and exact['inbound_residual_min'] == exact['outbound_residual_min'] == 0
    assert not exact['passenger_connection_certified'] and not exact['measurements_authenticated']
    assert not evaluate_budget_inputs(budget, 4.001, 1)['both_fit_event_budgets']
    # The average fits, but the outbound journey does not.
    assert not evaluate_budget_inputs(budget, 1, 3)['both_fit_event_budgets']
    with pytest.raises(ValueError, match='Both sourced'):
        evaluate_budget_inputs(dict(budget, maximum_inbound_total_expenses_min=None), 1, 1)


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -1, True, '3'])
def test_invalid_expenses_fail_closed(value):
    budget = dict(maximum_inbound_total_expenses_min=4,
                  maximum_outbound_total_expenses_after_worst_bus_model_min=2)
    with pytest.raises(ValueError, match='Finite nonnegative'):
        evaluate_budget_inputs(budget, value, 1)


def test_flow_comparison_cannot_silently_drop_train_or_reverse_platform(result):
    rows = result['phase_comparisons'][0]['all_dated_rail_flows_approach_only']
    with pytest.raises(ValueError, match='universe drift'):
        approach_flow_changes(rows, rows[:-1])
    with pytest.raises(ValueError, match='Duplicate'):
        approach_flow_changes(rows, rows+[rows[0]])
    changed = copy.deepcopy(rows)
    changed[0]['planned_platform'] = 'incorrect'
    with pytest.raises(ValueError, match='assumption drift'):
        approach_flow_changes(rows, changed)


@pytest.mark.parametrize('field,value', [
    ('worst_inherited_east_duration_min', 40),
    ('baseline_bus_start_min', 364),
    ('inbound_planned_platform', '2'),
    ('departure_min', 417),
])
def test_saved_pair_cannot_make_favourable_budget_by_changing_derived_evidence(field, value):
    source, design, rail, platform = [json.loads(p.read_text(encoding='utf-8'))
                                    for p in (SOURCE, DESIGN, RAIL, PLATFORM)]
    platform['paired_AM_directional_envelopes'][0][field] = value
    with pytest.raises(ValueError, match='runtime drift'):
        validate_platform_pairs(source, design, rail, platform)


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -1])
def test_unusable_platform_approach_does_not_default_to_favourable_zero(value):
    source, design, rail, platform = [json.loads(p.read_text(encoding='utf-8'))
                                    for p in (SOURCE, DESIGN, RAIL, PLATFORM)]
    platform['platforms']['1']['platform_to_bus']['approach_only_walk_model_min'] = value
    with pytest.raises(ValueError, match='Finite nonnegative platform'):
        validate_platform_pairs(source, design, rail, platform)


def test_no_authority_probability_or_readiness_manufactured(result):
    for flag in ('best_phase_selected', 'timetable_change_adopted', 'normative_rail_priority_adopted',
                 'external_operating_evidence_available', 'physical_operation_ready', 'rail_2027_certified',
                 'full_operating_cost_certified', 'network_selected', 'primary_selection_authorised',
                 'runner_up_selection_authorised', 'directional_approach_times_are_complete_transfers',
                 'uniform_3min_times_are_measured', 'actual_arrival_platforms_certified',
                 'global_or_exhaustive_phase_optimality_claimed', 'normative_rail_priority_required_by_this_audit'):
        assert result[flag] is False
    for field in ('decision_budget_km', 'uncertainty_band_min', 'missed_connection_probability',
                  'demand_weighted_gjt_improvement_min'):
        assert result[field] is None
    assert result['confirmed_geometry_unchanged'] and result['confirmed_timetable_unchanged']
