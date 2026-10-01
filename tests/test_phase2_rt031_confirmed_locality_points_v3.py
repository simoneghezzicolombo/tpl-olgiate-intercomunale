import copy
import csv
import json
from types import SimpleNamespace

import pytest

from scripts.phase2_audit_rt031_confirmed_locality_points_v3 import (
    ANCHORS, GEO, HANDOFF, OUTPUT, RAW_POINTS, pair_access, validate_points, validate_sites,
)


def test_four_points_match_native_id_coordinate_and_not_whole_locality():
    with ANCHORS.open(encoding='utf-8', newline='') as stream:
        anchors = list(csv.DictReader(stream))
    raw = json.loads(RAW_POINTS.read_text(encoding='utf-8'))
    points = validate_points(anchors, raw)
    assert len(points) == 4
    broken = copy.deepcopy(anchors)
    next(r for r in broken if r['name'] == 'Mondonico')['lat'] = '45.75'
    with pytest.raises(ValueError, match='source point drift'):
        validate_points(broken, raw)


def test_removed_inventory_point_is_not_one_of_27_confirmed_sites():
    handoff = json.loads(HANDOFF.read_text(encoding='utf-8'))
    geo = json.loads(GEO.read_text(encoding='utf-8'))
    assert len([f for f in geo['features'] if f['geometry']['type'] == 'Point']) == 28
    sites = validate_sites(handoff, geo)
    assert len(sites) == 27
    assert 'ASF::SANTA_MARIA_HOE_VIA_COMO' not in {s['site_id'] for s in sites}
    broken = copy.deepcopy(geo)
    next(f for f in broken['features'] if f['properties'].get('role') == 'REMOVED_FOR_EXCHANGE')['properties']['role'] = 'DESIGN_SITE'
    with pytest.raises(ValueError, match='27-site'):
        validate_sites(handoff, broken)


def test_directed_network_and_both_connectors_are_preserved():
    point = SimpleNamespace(status='REACHABLE', node_id='p', connector_distance_m=10)
    site = SimpleNamespace(status='REACHABLE', node_id='s', connector_distance_m=30)
    result = pair_access(None, point, site, {'s': 120}, {'s': 360})
    assert result['point_to_site_walk_min'] == 2
    assert result['site_to_point_walk_min'] == 5
    unreachable_return = pair_access(None, point, site, {'s': 120}, {})
    assert unreachable_return['site_to_point_walk_min'] is None
    point.status = 'UNREACHABLE'
    assert pair_access(None, point, site, {'s': 120}, {'s': 360})['point_to_site_walk_min'] is None


def test_committed_diagnostic_retains_gaps_and_occurrence_specific_bus_time():
    payload = json.loads(OUTPUT.read_text(encoding='utf-8'))
    assert payload['design_site_count_including_fs'] == 27
    assert payload['full_trip_count'] == 16
    assert payload['assumptions']['max_connector_m'] == 90
    assert payload['assumptions']['walk_metres_per_min'] == 80
    assert not payload['assumptions']['inventory_current_walk_min_and_old_node_ids_reused']
    for key in ('whole_locality_coverage_certified', 'physical_boarding_authorised',
                'accessible_pedestrian_paths_certified', 'locality_service_certified',
                'scheduled_total_journey_time_certified', 'new_service_policy_adopted',
                'passenger_od_downscaled', 'network_selected'):
        assert payload[key] is False
    handoff = json.loads(HANDOFF.read_text(encoding='utf-8'))
    site_map = {s['site_id']: s for s in handoff['design_stop_register']}
    for point in payload['points']:
        assert len(point['all_design_site_pairs']) == 27
        binding = point['closest_nonhub_site_diagnostic']
        if binding:
            assert binding['site_id'] != 'FROZEN::L00407'
            assert not binding['scheduled_best_journey_claim']
            source = {o['occurrence_id']: o for o in site_map[binding['site_id']]['ordered_occurrences']}
            for occurrence in binding['occurrences']:
                expected = source[occurrence['occurrence_id']]
                assert occurrence['nominal_site_to_next_fs_in_vehicle_min'] == expected['nominal_occurrence_to_next_fs_in_vehicle_min']
                assert occurrence['nominal_fs_to_site_in_vehicle_min'] == expected['nominal_fs_to_occurrence_in_vehicle_min']
    assert len(payload['remaining_locality_readiness']) == 6
