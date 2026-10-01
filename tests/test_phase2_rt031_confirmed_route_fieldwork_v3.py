import json
from pathlib import Path

from scripts.phase2_audit_rt031_confirmed_route_fieldwork_v3 import OUTPUT, audit_path


def test_immediate_return_is_detected_without_confusing_fs_boundary():
    edges = {
        'a': dict(u_node_id='FS', v_node_id='A', highway='residential', osm_way_id='1',
                  length_m='10', access_basis='generic_access', uncertainty_flags=''),
        'ar': dict(u_node_id='A', v_node_id='FS', highway='residential', osm_way_id='1',
                   length_m='10', access_basis='generic_access', uncertainty_flags=''),
        'b': dict(u_node_id='FS', v_node_id='B', highway='service', osm_way_id='2',
                  length_m='20', access_basis='generic_access', uncertainty_flags='missing_width'),
        'br': dict(u_node_id='B', v_node_id='FS', highway='service', osm_way_id='2',
                   length_m='20', access_basis='generic_access', uncertainty_flags='missing_width'),
    }
    nodes = {n: dict(lon=str(i), lat='45') for i, n in enumerate(('FS', 'A', 'B'))}
    loops = {
        'east_A': dict(edge_ids=['a', 'ar'], events=[], represented_via_node_path_verified=True),
        'west_B': dict(edge_ids=['b', 'br'], events=[], represented_via_node_path_verified=True),
    }
    audit = audit_path(loops, edges, 'FS', nodes)
    assert len(audit['immediate_edge_reversals']) == 2
    assert audit['checked_transition_count'] == 4
    assert audit['full_trip_node_sequence_including_fs'] == ['FS', 'A', 'FS', 'B', 'FS']
    assert len(audit['service_road_segments']) == 1
    assert audit['service_road_segments'][0]['length_m'] == 40


def test_published_current_audit_has_independent_node_witness_and_pending_fieldwork():
    audit = json.loads(OUTPUT.read_text(encoding='utf-8'))
    road = audit['current_route_audit']
    nodes = road['full_trip_node_sequence_including_fs']
    assert road['full_trip_directed_edge_count'] == road['checked_transition_count'] == 1435
    assert len(nodes) == 1436
    assert nodes[0] == nodes[718] == nodes[-1]
    assert all(a != c for a, _, c in zip(nodes, nodes[1:], nodes[2:]))
    assert nodes[-2] != nodes[1]  # repeated complete trips do not reverse at FS
    assert road['immediate_edge_reversals'] == []
    assert len(road['service_road_segments']) == 1
    segment = road['service_road_segments'][0]
    assert round(segment['length_m'], 2) == 85.68
    assert {e['site_id'] for e in segment['service_events_within_run']} == {'ASF::OLGIATE_MOLGORA_SCARPONE'}
    assert road['missing_osm_attribute_edge_counts']['missing_width'] == 1435
    sites = audit['stop_fieldwork_register']
    assert len(sites) == 27 and sum(len(s['service_occurrences']) for s in sites) == 28
    assert all(s['operator_fieldwork_outcome'] == 'PENDING' for s in sites)
    assert not audit['physical_bus_operation_authorised']
    assert not audit['primary_selection_authorised']
