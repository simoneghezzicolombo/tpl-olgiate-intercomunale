from scripts.phase2_audit_rt031_local_stop_siting_v3 import (
    haversine_m, nearest_node_distance_m, sha256,
)


def test_haversine_is_symmetric_and_zero_on_identical_location():
    assert haversine_m(45.735, 9.407, 45.735, 9.407) == 0
    assert haversine_m(45.735, 9.407, 45.734, 9.398) == (
        haversine_m(45.734, 9.398, 45.735, 9.407))


def test_nearest_route_node_distance_is_only_straight_line():
    nodes = {
        "a": {"lat": "45.735", "lon": "9.407"},
        "b": {"lat": "45.730", "lon": "9.400"},
    }
    assert nearest_node_distance_m(nodes, {"a", "b"}, 45.735, 9.407) == 0
    assert nearest_node_distance_m(nodes, {"b"}, 45.735, 9.407) > 0


def test_repo_text_digest_normalizes_line_endings(tmp_path):
    source = tmp_path / "source.csv"
    source.write_bytes(b"a,b\r\n1,2\r\n")
    digest = sha256(source, normalize_newlines=True)
    source.write_bytes(b"a,b\n1,2\n")
    assert sha256(source, normalize_newlines=True) == digest
