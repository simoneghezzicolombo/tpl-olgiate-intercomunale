import copy
import json

import pytest

from scripts.phase2_materialise_rt031_weekday_calendar_2027_v3 import (
    AUTHORITY, HANDOFF, OUTPUT, PDB, TIMETABLE_AUTHORITY, build,
    materialise_dates, render_brief, validate_authority,
)


@pytest.fixture(scope='module')
def calendar():
    return build()


def test_dated_2027_weekday_base_has_no_invented_school_or_august_cuts(calendar):
    days = calendar['date_ledger']
    assert len(days) == len({d['date'] for d in days}) == 365
    assert days[0]['date'] == '2027-01-01' and days[-1]['date'] == '2027-12-31'
    assert calendar['weekdays_before_national_holiday_exclusions'] == 261
    assert calendar['weekday_base_day_count_before_local_exceptions'] == 254
    assert calendar['weekday_base_complete_trip_count'] == 4064
    assert sum(calendar['monthly_weekday_base_day_counts'].values()) == 254
    by_date = {d['date']: d for d in days}
    for key in ('2027-01-04', '2027-04-26', '2027-08-16', '2027-12-24', '2027-12-31'):
        assert by_date[key]['weekday_component_complete_trips'] == 16
    assert calendar['weekday_base_commercial_km'] == pytest.approx(110229.9360245941)
    assert calendar['arithmetic_margin_vs_reference_km'] == pytest.approx(1189.0639754059)
    assert calendar['whole_extra_complete_trips_within_reference'] == 43


def test_holidays_are_not_double_subtracted_and_new_national_holiday_is_present(calendar):
    excluded = calendar['excluded_weekday_national_holiday_dates']
    assert excluded == ['2027-01-01', '2027-01-06', '2027-03-29', '2027-06-02',
                        '2027-10-04', '2027-11-01', '2027-12-08']
    assert '2027-03-28' not in excluded and '2027-12-25' not in excluded
    by_date = {d['date']: d for d in calendar['date_ledger']}
    assert by_date['2027-10-04']['weekday_component_complete_trips'] == 0
    # Suppressed historical holidays / Rome-only patron must not become closures.
    for key in ('2027-03-19', '2027-06-29', '2027-11-04'):
        assert by_date[key]['weekday_component_complete_trips'] == 16


def test_saturday_is_pending_not_zero_or_16_and_sensitivity_is_not_a_timetable(calendar):
    saturday = [d for d in calendar['date_ledger'] if d['weekday_iso_number'] == 6]
    assert len(saturday) == 52
    assert calendar['saturday_nonholiday_date_count'] == 50
    assert all(d['complete_line_day_trip_count'] is None for d in saturday)
    assert not calendar['saturday_service_policy_adopted']
    assert calendar['saturday_trip_count'] is None
    for case in calendar['saturday_sensitivity_count_only']:
        assert case['additional_complete_trips'] == 50*case['hypothetical_full_trips_per_nonholiday_saturday']
        assert case['additional_commercial_km'] == pytest.approx(case['additional_complete_trips']*calendar['complete_trip_commercial_km'])
        for flag in ('departure_times_selected', 'timetable_feasibility_certified',
                     'h30_peak_promise_inferable', 'policy_adopted'):
            assert case[flag] is False
    assert not calendar['extra_trip_capacity_is_service_recommendation']


def test_only_weekday_design_authority_is_added_not_operating_funding_or_2027_rail(calendar):
    assert calendar['weekday_calendar_declared_for_design']
    for key in ('complete_annual_operating_calendar_adopted', 'local_exception_policy_certified',
                'rail_connections_for_2027_certified', 'observed_runtime_for_2027_certified',
                'actual_d184_d185_annual_calendar_certified', 'reference_funding_transfer_certified',
                'physical_boarding_authorised', 'public_operating_timetable_authorised',
                'funding_secured', 'network_selected', 'primary_selection_authorised',
                'runner_up_selection_authorised'):
        assert calendar[key] is False
    for key in ('complete_line_annual_commercial_km', 'annual_noncommercial_km',
                'full_annual_operating_cost', 'decision_budget_km', 'uncertainty_band_min',
                'missed_connection_probability', 'demand_weighted_gjt_improvement_min',
                'local_patronal_or_other_extra_exclusions'):
        assert calendar[key] is None


def test_source_drift_or_silent_policy_change_fails_closed():
    auth = json.loads(AUTHORITY.read_text(encoding='utf-8'))
    sources = {p.name: json.loads(p.read_text(encoding='utf-8'))
               for p in (PDB, HANDOFF, TIMETABLE_AUTHORITY)}
    validate_authority(auth, sources)
    changed = copy.deepcopy(sources)
    changed[HANDOFF.name]['full_trips'][0]['first_fs_min'] -= 1
    with pytest.raises(ValueError, match='source drift'):
        validate_authority(auth, changed)
    for key, value in [('saturday_trips_per_day', 0), ('saturday_trips_per_day', 16),
                       ('local_patronal_or_other_extra_exclusions', []), ('decision_budget_km', 111419),
                       ('primary_selection_authorised', True), ('school_vacation_or_bridge_day_cuts_authorised', True)]:
        changed_auth = copy.deepcopy(auth); changed_auth[key] = value
        with pytest.raises(ValueError):
            validate_authority(changed_auth, sources)
    changed_auth = copy.deepcopy(auth)
    changed_auth['national_holiday_dates_2027'] = [r for r in changed_auth['national_holiday_dates_2027'] if r['date'] != '2027-10-04']
    with pytest.raises(ValueError, match='holiday dates drift'):
        validate_authority(changed_auth, sources)


def test_published_calendar_and_brief_are_reproducible(calendar):
    assert json.loads(OUTPUT.read_text(encoding='utf-8')) == calendar
    text = render_brief(calendar)
    assert '110.229,936' in text and '254' in text
    assert 'non certificano i treni 2027' in text
    assert materialise_dates(json.loads(AUTHORITY.read_text(encoding='utf-8'))) == calendar['date_ledger']
