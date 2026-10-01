import copy
import json

import pytest

from scripts.phase2_package_rt031_confirmed_design_handoff_v3 import (
    AUTHORITY, DESIGN, GEO, RAIL, SOURCE, build, canonical_sha256,
    render_brief, validate_authority,
)
from scripts.phase2_package_rt031_current_16_trip_proposal_v3 import build as review_build


@pytest.fixture(scope='module')
def package():
    return build()


def test_confirmation_closes_only_design_not_operational_or_tournament_authority(package):
    assert package['caller_confirmed_design_timetable_basis']
    assert package['detailed_timetable_adopted_for_design']
    assert package['transition_extension_adopted_for_design']
    assert package['exact_peak_phases_adopted_for_design']
    assert not package['exact_peak_phases_require_caller_confirmation']
    for key in ('public_operating_timetable_authorised', 'physical_boarding_authorised',
                'physical_passenger_continuity_certified', 'calendar_adopted',
                'fleet_or_operator_availability_certified', 'full_history_road_legality_certified',
                'funding_secured', 'network_selected', 'primary_selection_authorised',
                'runner_up_selection_authorised', 'adopted_new_bidirectional_service'):
        assert package[key] is False
    for key in ('decision_budget_km', 'uncertainty_band_min', 'annual_noncommercial_km',
                'annual_full_operating_cost', 'physical_platform_count',
                'missed_connection_probability', 'demand_weighted_gjt_improvement_min'):
        assert package[key] is None
    old = review_build()
    assert not old['transition_extension_adopted']
    assert old['exact_peak_phases_require_caller_confirmation']


def test_exact_schedule_and_registry_not_renamed_wing_trips(package):
    assert package['full_trip_count'] == len(package['full_trips']) == 16
    sites = package['design_stop_register']
    assert len(sites) == len({s['site_id'] for s in sites}) == 27
    assert sum(s['proposed_new_site'] for s in sites) == 4
    assert package['inventory_design_site_count_including_fs'] == 23
    assert sum(len(s['ordered_occurrences']) for s in sites) == 28
    assert len(package['all_current_rail_flows']) == 148
    assert package['old_22_target_compatibility']['distinct_event_matching_count'] == 19
    calco = next(s for s in sites if s['site_id'].startswith('RT031::CALCO_CENTRE'))
    assert calco['coordinates_lon_lat'] == [9.4180371, 45.7250958]
    assert len(calco['ordered_occurrences']) == 1
    assert calco['ordered_occurrences'][0]['path_node_index'] == 520
    assert 'ASF::SANTA_MARIA_HOE_VIA_COMO' not in {s['site_id'] for s in sites}
    assert 'FROZEN::300782' in {s['site_id'] for s in sites}


def test_directional_guarantees_are_not_collapsed_to_stop_identity(package):
    for sid in ('PROXY::SAN_ZENO_VIA_CANTU_ROAD_NODE', 'RT031::P2V2S_0031_PROJECTED_ROAD_POINT'):
        site = next(s for s in package['design_stop_register'] if s['site_id'] == sid)
        a, b = site['ordered_occurrences']
        assert a['occurrence_id'] != b['occurrence_id']
        assert a['ordered_nonhub_event_number'] < b['ordered_nonhub_event_number']
        assert a['nominal_occurrence_to_next_fs_in_vehicle_min'] > 30
        assert b['nominal_occurrence_to_next_fs_in_vehicle_min'] < 6
        assert not a['physical_boarding_authorised'] and not b['physical_boarding_authorised']
        for occurrence in (a, b):
            oid = occurrence['occurrence_id']
            events = [next(e for e in t['events'] if e.get('occurrence_id') == oid)
                      for t in package['ordered_stop_event_ledger_nominal']]
            assert occurrence['first_board_event_min'] == min(e['board_event_min'] for e in events)
            assert occurrence['last_alight_event_min'] == max(e['alight_event_min'] for e in events)


def test_caller_source_drift_and_unsupported_authority_fail_closed():
    authority = json.loads(AUTHORITY.read_text(encoding='utf-8'))
    sources = {p.name: json.loads(p.read_text(encoding='utf-8')) for p in (SOURCE, DESIGN, RAIL, GEO)}
    validate_authority(authority, sources)
    broken = copy.deepcopy(sources)
    broken[SOURCE.name]['full_trips'][0]['first_fs_min'] -= 1
    with pytest.raises(ValueError, match='source drift'):
        validate_authority(authority, broken)
    broken_auth = copy.deepcopy(authority)
    broken_auth['ready_windows_min'][1][1] = 960
    with pytest.raises(ValueError, match='readiness windows'):
        validate_authority(broken_auth, sources)
    for key in ('primary_selection_authorised', 'public_operating_timetable_authorised', 'annual_calendar_adopted'):
        broken_auth = copy.deepcopy(authority); broken_auth[key] = True
        with pytest.raises(ValueError, match='cannot certify'):
            validate_authority(broken_auth, sources)
    broken_auth = copy.deepcopy(authority); broken_auth['decision_budget_km'] = 112834
    with pytest.raises(ValueError, match='No new Decision Contract'):
        validate_authority(broken_auth, sources)


def test_readiness_and_brief_carry_forward_evidence_gaps(package):
    rows = {r['input']: r for r in package['requirements_readiness']}
    assert rows['h30_peak_banks']['state'] == 'CALLER_CONFIRMED_DESIGN_ONLY'
    assert rows['offpeak_transition']['state'] == 'CALLER_CONFIRMED_DESIGN_ONLY'
    assert rows['annual_service_days']['state'] == '260_DAY_COMPARISON_ONLY'
    assert rows['missed_connection_probability']['state'] == 'UNSUPPORTED_NULL'
    assert len(package['best_practice_current_assessment']) == 12
    assert len(package['remaining_external_validations']) == 3
    assert package['commercial_km_per_comparison_day'] == pytest.approx(433.9761260810791)
    assert package['annual_service_km_260_day_comparison'] == pytest.approx(112833.79278108056)
    assert package['coverage_percent']['97012']['5'] == pytest.approx(41.10164913528678)
    text = render_brief(package)
    assert 'Calco Centro' in text and 'Calco |' in text
    assert '16:20' in text and '07:26' in text and '33 minuti' in text
    assert 'non passeggeri previsti' in text
    assert canonical_sha256(package) == canonical_sha256(build())
