import json
import math
import pytest
from scripts.phase2_closure_resources_20261007 import BASE, audit, comparison, exclusion_effect, verify_sources


@pytest.fixture
def calendar():
    return json.loads((BASE / 'caller_confirmed_weekday_calendar_2027.json').read_text(encoding='utf-8'))


def test_duplicate_local_exception_and_already_absent_days(calendar):
    result = exclusion_effect(calendar, ['2027-01-04', '2027-01-04', '2027-01-01', '2027-01-02'])
    assert result['removed_full_trips'] == 16
    assert result['removed_weekday_dates'] == ['2027-01-04']
    assert len(result['already_outside_weekday_base']) == 2
    assert math.isclose(result['commercial_km_reduction'], 433.9761260810791)
    assert result['local_exception_policy_certified'] is False


def test_outside_year_cannot_remove_work(calendar):
    with pytest.raises(ValueError):
        exclusion_effect(calendar, ['2026-01-04'])


def test_unknown_deadhead_is_not_zero_or_budget(calendar):
    result = comparison(calendar)
    assert result['weekday_operating_km'] is None
    assert result['decision_budget_km'] is None
    assert result['full_line_annual_km'] is None
    hypothetical = comparison(calendar, 2000)
    assert hypothetical['operating_minus_reference_km'] > 0
    assert hypothetical['reference_is_secured_funding'] is False


@pytest.mark.parametrize('invalid', [-1, float('nan'), float('inf'), True, '12', [], {}])
def test_invalid_deadhead_rejected(calendar, invalid):
    with pytest.raises(ValueError):
        comparison(calendar, invalid)


@pytest.mark.parametrize('tamper', ['ledger', 'gap'])
def test_whole_source_drift_rejected(calendar, tamper):
    pack = json.loads((BASE / 'operating_closure_working_pack_20261002.json').read_text(encoding='utf-8'))
    if tamper == 'ledger':
        calendar['date_ledger'][3]['weekday_component_complete_trips'] = 15
    else:
        pack['weekday_bill_of_quantities']['nominal']['blocks'][0]['uncommitted_gaps_after_recovery'][0]['duration_min'] += 1
    with pytest.raises(ValueError, match='source drift'):
        verify_sources(calendar, pack)


def test_resource_sources_reconcile_without_operating_approval():
    result = audit()
    assert len(result['open_items']) == 5
    for case in result['vehicle_model'].values():
        assert case['maximum_simultaneous_model_vehicles'] == 4
        assert case['payable_driver_hours'] is None
