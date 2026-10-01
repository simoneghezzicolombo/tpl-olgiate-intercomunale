import copy
import json

import pytest

from scripts.phase2_complete_rt031_current_design_evidence_v3 import (
    CALENDAR_EVIDENCE, HANDOFF, OUTPUT, accounting, build, complete_trip_blocks,
    make_intervals, render_brief, validate_blocks, validate_calendar_evidence,
)


@pytest.fixture(scope='module')
def evidence():
    return build()


def test_current_full_trip_blocks_match_minimum_witness_not_separate_wing_fleets(evidence):
    assert evidence['conditional_fleet_distribution'] == {'3': 2, '4': 25}
    for case in evidence['all_27_resource_cases']:
        trips = [t for v in case['vehicles'] for t in v['trips']]
        assert sorted(t['full_trip_number'] for t in trips) == list(range(1, 17))
        validate_blocks(trips, case['vehicles'], case['minimum_vehicle_count_conditional'])
        witness = case['overlap_lower_bound_witness']
        active = sorted(t['full_trip_number'] for t in trips
                        if t['fs_start_min'] <= witness['time_min'] < t['released_after_terminal_recovery_min'])
        assert active == witness['simultaneous_full_trip_numbers']
        assert len(active) == case['minimum_vehicle_count_conditional']
        assert all(v['same_model_vehicle_through_intermediate_fs'] for v in case['vehicles'])
        assert all(v['actual_vehicle_identity'] is None and v['driver_duty_assignment'] is None
                   for v in case['vehicles'])
    for key in ('nominal_case', 'slower_dwell_recovery_case'):
        case = evidence[key]
        assert [v['complete_trip_numbers'] for v in case['vehicles']] == [
            [1, 5, 9, 13], [2, 6, 10, 14], [3, 7, 11, 15], [4, 8, 12, 16]]
        assert case['overlap_lower_bound_witness']['time_min'] == 455
        assert case['overlap_lower_bound_witness']['simultaneous_full_trip_numbers'] == [1, 2, 3, 4]
    assert evidence['same_full_route_for_all_trips'] and not evidence['separate_wing_fleets']


def test_recovery_is_once_per_complete_trip_and_included_only_in_occupation(evidence):
    for case in evidence['all_27_resource_cases']:
        service = case['total_complete_trip_service_hours_excluding_terminal_recovery']
        occupation = case['total_vehicle_occupation_hours_including_terminal_recovery']
        assert occupation-service == pytest.approx(16*case['terminal_recovery_min']/60)
        assert not case['time_totals_are_driver_duties']
    # A trip departing exactly at release can reuse the vehicle; one minute
    # earlier cannot, even though the previous public trip has already ended.
    exact = make_intervals([{'first_fs_min': 0, 'second_fs_min': 5},
                            {'first_fs_min': 20, 'second_fs_min': 25}], 4, 5, 10)
    assert complete_trip_blocks(exact)['minimum_vehicle_count_conditional'] == 1
    early = make_intervals([{'first_fs_min': 0, 'second_fs_min': 5},
                            {'first_fs_min': 19, 'second_fs_min': 24}], 4, 5, 10)
    assert complete_trip_blocks(early)['minimum_vehicle_count_conditional'] == 2
    with pytest.raises(ValueError, match='before full-trip terminal recovery'):
        validate_blocks(early, [{'complete_trip_numbers': [1, 2]}], 1)
    with pytest.raises(ValueError, match='omit or duplicate'):
        validate_blocks(exact, [{'complete_trip_numbers': [1, 1]}], 1)
    with pytest.raises(ValueError, match='public dwell'):
        make_intervals([{'first_fs_min': 0, 'second_fs_min': 4}], 4, 5, 10)
    with pytest.raises(ValueError, match='Finite'):
        make_intervals([{'first_fs_min': float('nan'), 'second_fs_min': 4}], 4, 5, 10)


def test_source_calendar_is_planning_only_and_drift_or_adoption_fails_closed():
    source = json.loads(CALENDAR_EVIDENCE.read_text(encoding='utf-8'))
    handoff = json.loads(HANDOFF.read_text(encoding='utf-8'))
    assert validate_calendar_evidence(source, handoff) == (111419, 303)
    for section, key, value, error in [
        ('primary_source', 'sha256', '0'*64, 'PDF source drift'),
        ('current_confirmed_design_arithmetic', 'source_canonical_sha256', '0'*64, 'source drift'),
        ('current_confirmed_design_arithmetic', 'calendar_adopted', True, 'cannot adopt'),
        ('current_confirmed_design_arithmetic', 'reference_funding_transfer_certified', True, 'cannot adopt'),
        ('day_type_table_shared_by_d184_d185', 'ordinary_project_service_days', 365, 'sum differs'),
    ]:
        broken = copy.deepcopy(source); broken[section][key] = value
        with pytest.raises(ValueError, match=error):
            validate_calendar_evidence(broken, handoff)
    broken = copy.deepcopy(source)
    broken['day_type_table_shared_by_d184_d185']['rows'][0]['days'] += 1
    with pytest.raises(ValueError, match='transcription drift'):
        validate_calendar_evidence(broken, handoff)


def test_annual_arithmetic_never_selects_days_budget_or_full_cost(evidence):
    annual = evidence['calendar_accounting']
    assert annual['maximum_whole_identical_days_within_reference'] == 256
    scenarios = {c['identical_service_days']: c for c in annual['annual_commercial_comparisons']}
    assert scenarios[256]['commercial_km'] <= 111419 < scenarios[257]['commercial_km']
    assert scenarios[260]['commercial_km'] == pytest.approx(112833.79278108056)
    assert scenarios[303]['commercial_km'] == pytest.approx(131494.76620256697)
    assert not annual['annual_calendar_adopted']
    assert annual['actual_annual_service_day_count'] is None
    assert annual['annual_noncommercial_km'] is None and annual['full_annual_operating_cost'] is None
    for key in ('operating_plan_adopted', 'physical_vehicle_and_passenger_continuity_certified',
                'driver_duties_and_depot_plan_certified', 'network_selected',
                'primary_selection_authorised', 'runner_up_selection_authorised'):
        assert evidence[key] is False
    for key in ('decision_budget_km', 'uncertainty_band_min', 'missed_connection_probability',
                'demand_weighted_gjt_improvement_min'):
        assert evidence[key] is None
    with pytest.raises(ValueError, match='positive'):
        accounting(0, 111419, 303)
    text = render_brief(evidence)
    assert '+1,27%' in text and '+18,02%' in text and '256' in text


def test_published_artifact_reproduces_verified_sources(evidence):
    assert json.loads(OUTPUT.read_text(encoding='utf-8')) == evidence
