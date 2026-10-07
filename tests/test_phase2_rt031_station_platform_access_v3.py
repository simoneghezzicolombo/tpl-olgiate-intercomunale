import copy
import hashlib
import json

import pytest

from scripts.phase2_audit_rt031_station_platform_access_v3 import (
    ACCESSIBILITY_REVIEW, BRIEF, DESIGN, GEO, HANDOFF, OUTPUT, RAIL, SOURCE, approach_path,
    canonical_sha256, dated_flows, parse_rfi, planned_platforms, render_brief, transfer_envelope,
    validate_accessibility_review,
)


def witness(way, highway='footway'):
    return [dict(osm_way_id=way, tags={'highway': highway})]


def rfi_fixture(platform='1', duplicate=False, heading='Binario programmato'):
    headers = ['Orario', 'Treno', 'Destinazione', heading, 'Classi', 'Impresa',
               'Prima', 'Dopo', 'Avvertenze']
    row = '<tr>'+''.join('<td>'+v+'</td>' for v in
                         ['00.03', '24886', 'LECCO', platform, '', 'TN', '', '', ''])+'</tr>'
    raw = ('OLGIATE-CALCO-BRIVIO ORARIO PROGRAMMATO 14 giugno 2026 - 12 dicembre 2026'
           '<table class="QOtab"><thead><tr>'+''.join('<th>'+h+'</th>' for h in headers)
           +'</tr></thead><tbody>'+row+(row if duplicate else '')+'</tbody></table>').encode('windows-1252')
    rail = dict(service_date='2026-10-01',
                source_sha256={'rfi_departures': hashlib.sha256(raw).hexdigest()},
                rfi=parse_rfi(raw, '2026-10-01'),
                events=[dict(train_number='24886', departure_min=1443, arrival_min=1442,
                             trip_id='dated-after-midnight', direction='LECCO', origin_axis='MILANO')])
    return raw, rail


def test_planned_platform_join_preserves_service_day_and_not_arrival_authority():
    raw, rail = rfi_fixture()
    rows = planned_platforms(raw, rail)
    assert rows[0]['departure_min'] == 1443
    assert rows[0]['planned_departure_platform'] == '1'
    assert not rows[0]['actual_departure_platform_certified']
    assert not rows[0]['arrival_platform_certified']
    broken = copy.deepcopy(rail)
    broken['events'][0]['train_number'] = 'wrong'
    with pytest.raises(ValueError, match='call set mismatch'):
        planned_platforms(raw, broken)
    with pytest.raises(ValueError, match='source drift'):
        planned_platforms(raw+b' ', rail)


@pytest.mark.parametrize('kwargs,error', [
    ({'platform': ''}, 'Missing or unsupported'),
    ({'platform': '3'}, 'Missing or unsupported'),
    ({'duplicate': True}, 'Duplicate'),
    ({'heading': 'Binario reale'}, 'column not identified'),
])
def test_unsupported_platform_source_fails_closed(kwargs, error):
    raw, rail = rfi_fixture(**kwargs)
    with pytest.raises(ValueError, match=error):
        planned_platforms(raw, rail)


def test_planned_platform_is_sourced_not_inferred_from_city():
    raw, rail = rfi_fixture(platform='2')
    assert planned_platforms(raw, rail)[0]['planned_departure_platform'] == '2'
    assert rail['events'][0]['direction'] == 'LECCO'


def test_access_uses_native_connected_interface_and_directed_path_not_centroid():
    graph = {'bus': [('stairs', 5), ('ramp', 15)], 'stairs': [('platform', 5)],
             'ramp': [('platform', 15)], 'platform': []}
    provenance = {('bus', 'stairs'): witness('steps1', 'steps'),
                  ('stairs', 'platform'): witness('foot1'),
                  ('bus', 'ramp'): witness('ramp1'), ('ramp', 'platform'): witness('ramp2')}
    ordinary = approach_path(graph, provenance, 'bus', {'platform'})
    no_steps = approach_path(graph, provenance, 'bus', {'platform'}, no_steps=True)
    assert ordinary['path_node_ids'] == ['bus', 'stairs', 'platform']
    assert ordinary['network_distance_m'] == 10 and ordinary['steps_distance_m'] == 5
    assert no_steps['network_distance_m'] == 30
    assert not no_steps['step_free_path_certified']
    assert approach_path(graph, provenance, 'platform', {'bus'}) is None
    assert approach_path(graph, provenance, 'bus', {'unconnected_rail_centroid'}) is None
    assert approach_path(graph, provenance, 'bus', set()) is None


def test_missing_step_free_access_is_not_zero_or_physical_impossibility():
    graph = {'bus': [('platform', 10)], 'platform': []}
    p = {('bus', 'platform'): witness('only-stairs', 'steps')}
    assert approach_path(graph, p, 'bus', {'platform'}, no_steps=True) is None
    with pytest.raises(ValueError, match='Finite positive'):
        approach_path({'bus': [('platform', float('nan'))]}, p, 'bus', {'platform'})


def test_two_independent_transfer_directions_not_uniform_average():
    separate = transfer_envelope(362, 416, 365, 47.7765936279, 3.5, 1)
    assert separate['baseline_inbound_residual_min'] == -.5
    assert separate['baseline_outbound_residual_min'] == pytest.approx(2.2234063721)
    assert separate['interval_width_min'] == pytest.approx(1.7234063721)
    empty = transfer_envelope(362, 416, 365, 50, 3, 3)
    assert not empty['interval_nonempty'] and empty['best_balanced_residual_min'] is None
    assert not separate['phase_selected'] and not separate['normative_margin_selected']
    with pytest.raises(ValueError, match='Finite nonnegative'):
        transfer_envelope(362, 416, 365, 47, float('nan'), 3)


def test_flow_pair_has_independent_paths_and_missing_evidence_not_imputed():
    train = dict(trip_id='t', train_number='1', direction='MILANO', origin_name='Lecco',
                 destination_name='Milano', arrival_min=60, departure_min=61,
                 ordinary_alighting_supported=True, ordinary_boarding_supported=True)
    rail = {'events': [train]}
    schedule = {'full_trips': [dict(first_fs_min=63, second_fs_min=80)]}
    offsets = {(1.1,.5): {'east_A': {'road_minutes': 1}, 'west_B': {'road_minutes': 1}}}
    bindings = [dict(trip_id='t', planned_departure_platform='2')]
    platform = {'2': dict(platform_to_bus={'approach_only_walk_model_min': 4},
                          bus_to_platform={'approach_only_walk_model_min': 1})}
    rows = dated_flows(schedule, offsets, rail, bindings, platform)
    assert rows[0]['rail_to_bus']['next_wing_departure_min'] is None
    assert rows[1]['rail_to_bus']['next_wing_departure_min'] == 80
    assert rows[0]['approach_inbound_walk_min'] == 4
    assert rows[0]['approach_outbound_walk_min'] == 1
    platform['2']['platform_to_bus'] = None
    with pytest.raises(ValueError, match='Cannot impute missing'):
        dated_flows(schedule, offsets, rail, bindings, platform)


@pytest.fixture(scope='module')
def saved():
    return json.loads(OUTPUT.read_text(encoding='utf-8'))


def test_saved_exact_proposal_and_source_binding(saved):
    for path in (HANDOFF, SOURCE, DESIGN, RAIL, ACCESSIBILITY_REVIEW):
        assert saved['source_canonical_sha256'][path.name] == canonical_sha256(json.loads(path.read_text(encoding='utf-8')))
    assert BRIEF.read_text(encoding='utf-8') == render_brief(saved)
    assert len(saved['planned_platform_bindings']) == 74
    assert {b['planned_departure_platform'] for b in saved['planned_platform_bindings'] if b['direction']=='MILANO'} == {'2'}
    assert {b['planned_departure_platform'] for b in saved['planned_platform_bindings'] if b['direction']=='LECCO'} == {'1'}
    assert len(saved['all_dated_rail_flows_approach_only']) == 148
    assert saved['transfer_flow_combinations_checked'] == 296
    assert len({(r['wing'],r['trip_id']) for r in saved['all_dated_rail_flows_approach_only']}) == 148


def test_official_access_provision_is_not_a_mapped_or_measured_bus_transfer(saved):
    review = saved['official_accessibility_review']
    validate_accessibility_review(review)
    assert review['reported_level_or_ramp_access_to_platforms'] == ['1', '2']
    assert not saved['native_graph_platform_approach_universe_complete']
    assert not saved['no_steps_result_proves_physical_impossibility']
    broken = copy.deepcopy(review)
    broken['bus_stop_to_accessible_entrance_connected_and_verified'] = True
    with pytest.raises(ValueError, match='cannot certify bus path'):
        validate_accessibility_review(broken)


def test_native_platform_approaches_and_return_witnesses(saved):
    p1, p2 = saved['platforms']['1'], saved['platforms']['2']
    assert p1['bus_to_platform']['network_distance_m'] == pytest.approx(108.15508329875198)
    assert p2['bus_to_platform']['network_distance_m'] == pytest.approx(76.22819320666318)
    for platform in (p1, p2):
        outgoing, incoming = platform['bus_to_platform'], platform['platform_to_bus']
        assert outgoing['path_node_ids'] == incoming['path_node_ids'][::-1]
        assert outgoing['approach_node_id'] in platform['local_surface_topology']['surface_access_node_ids']
        assert incoming['approach_node_id'] in platform['local_surface_topology']['surface_access_node_ids']
        for flow in ('bus_to_platform', 'platform_to_bus'):
            path = platform[flow]
            assert path['contains_steps'] and not path['observed_transfer_time']
            assert sum(e['length_m'] for e in path['path_edges']) == pytest.approx(path['network_distance_m'])
            assert path['approach_only_walk_model_min'] == pytest.approx(path['distance_including_connector_m']/80)
            assert not path['final_platform_walk_and_train_door_time_included']
            assert not path['slope_steps_congestion_penalty_included']
            assert platform[flow+'_excluding_steps'] is None
    geo = json.loads(GEO.read_text(encoding='utf-8'))
    assert len([f for f in geo['features'] if f['properties']['role']=='PLATFORM_APPROACH']) == 4
    assert any(f['properties']['role']=='BASEMAP' for f in geo['features'])


def test_budget_reveals_evidence_needed_not_a_silent_phase_choice(saved):
    assert len(saved['paired_AM_directional_envelopes']) == 5
    for pair in saved['paired_AM_directional_envelopes']:
        assert pair['inbound_planned_platform'] == '1' and pair['outbound_planned_platform'] == '2'
        assert pair['assumed_3min_each_side']['interval_width_min'] == pytest.approx(.2234063721)
        approach = pair['platform_approach_only_diagnostic']
        assert approach['baseline_inbound_residual_min'] == pytest.approx(1.6480614587655964)
        assert approach['baseline_outbound_residual_min'] > 2
        assert approach['interval_width_min'] > 2 and not approach['phase_selected']
        budgets = pair['measured_transfer_time_budgets']
        assert [b['maximum_inbound_transfer_plus_train_lateness_min'] for b in budgets] == [3,4,5]
        assert budgets[1]['maximum_outbound_transfer_plus_extra_bus_lateness_min'] == pytest.approx(2.2234063721)
        assert not any(b['timetable_change_adopted'] for b in budgets)
    for flag in ('normative_rail_priority_adopted', 'timetable_or_route_change_adopted',
                 'observed_transfer_time_available', 'step_free_access_certified',
                 'physical_operation_ready', 'rail_2027_certified', 'network_selected',
                 'primary_selection_authorised', 'runner_up_selection_authorised'):
        assert saved[flag] is False
    for key in ('decision_budget_km', 'uncertainty_band_min', 'missed_connection_probability',
                'demand_weighted_gjt_improvement_min'):
        assert saved[key] is None


def test_corrected_path_uses_both_platform_stairs_and_native_underpass(saved):
    path = saved['platforms']['1']['bus_to_platform']
    ways = [e['osm_way_id'] for e in path['path_edges']]
    assert ways[-4:] == ['1232462158', '1193795237', '784178060', '1193795239']
    assert path['modelled_platform_surface_distance_m'] == pytest.approx(5.9328590550144815)
    assert path['approach_node_id'] == '11081379902'
    assert '2964695553' not in saved['platforms']['1']['local_surface_topology']['surface_access_node_ids']
    previous = saved['superseded_boundary_only_approaches']['1']['bus_to_platform']
    assert previous['old_boundary_only_network_distance_m'] == pytest.approx(250.92180057208333)
    assert not previous['used_in_current_transfer_diagnostic']
    assert not saved['local_platform_area_edges_change_frozen_rt028_graph']
    assert not saved['geometry_reconstruction_is_observed_transfer_time']


def test_corrected_baseline_keeps_five_immediate_inbound_buses_only_in_diagnostic(saved):
    numbers = {p['arriving_train_number'] for p in saved['paired_AM_directional_envelopes']}
    rows = [r for r in saved['all_dated_rail_flows_approach_only'] if r['wing']=='east_A' and r['train_number'] in numbers]
    assert len(rows) == 5
    assert all(r['rail_to_bus']['wait_from_train_arrival_min'] == 3 for r in rows)
    assert all(not r['passenger_connection_certified'] for r in rows)
    assert saved['corrected_on'] == '2026-10-07'
