from scripts.phase2_build_current_service_continuity_v2 import (
    derive_current_lower_bound,
    scenario_continuity,
)


def current_validation(clusters, localized_rows):
    return {
        "localized_unique_physical_clusters": clusters,
        "localized_unique_physical_cluster_count": len(clusters),
        "localized_rows": localized_rows,
    }


def test_unresolved_current_row_breaks_corridor_adjacency():
    rows = [
        {"route_id": "D184", "source_page": "1", "stop_sequence_on_page": "1", "v2_physical_cluster_id": "EX_011", "localization_status": "LOCALIZED_EXACT_RESOLVED_GTFS_ID_TO_V2_CLUSTER"},
        {"route_id": "D184", "source_page": "1", "stop_sequence_on_page": "2", "v2_physical_cluster_id": "", "localization_status": "UNRESOLVED_IDENTITY_NOT_SPATIALLY_USED"},
        {"route_id": "D184", "source_page": "1", "stop_sequence_on_page": "3", "v2_physical_cluster_id": "EX_023", "localization_status": "LOCALIZED_EXACT_RESOLVED_GTFS_ID_TO_V2_CLUSTER"},
    ]
    clusters, by_route, directed, undirected = derive_current_lower_bound(
        rows, current_validation(["EX_011", "EX_023"], 2)
    )
    assert clusters == ["EX_011", "EX_023"]
    assert by_route["D184"] == {"EX_011", "EX_023"}
    assert directed == []
    assert undirected == []


def test_only_immediately_consecutive_localized_rows_create_corridor_pair():
    rows = [
        {"route_id": "D184", "source_page": "1", "stop_sequence_on_page": "1", "v2_physical_cluster_id": "EX_011", "localization_status": "LOCALIZED_EXACT_RESOLVED_GTFS_ID_TO_V2_CLUSTER"},
        {"route_id": "D184", "source_page": "1", "stop_sequence_on_page": "2", "v2_physical_cluster_id": "EX_023", "localization_status": "LOCALIZED_EXACT_RESOLVED_GTFS_ID_TO_V2_CLUSTER"},
        {"route_id": "D184", "source_page": "1", "stop_sequence_on_page": "3", "v2_physical_cluster_id": "EX_026", "localization_status": "LOCALIZED_EXACT_RESOLVED_GTFS_ID_TO_V2_CLUSTER"},
    ]
    _, _, directed, undirected = derive_current_lower_bound(
        rows, current_validation(["EX_011", "EX_023", "EX_026"], 3)
    )
    assert directed == [("EX_011", "EX_023"), ("EX_023", "EX_026")]
    assert undirected == [("EX_011", "EX_023"), ("EX_023", "EX_026")]


def test_project_hub_does_not_count_as_historical_station_retention():
    out = scenario_continuity(
        scenario_id="S1",
        topology_family="test",
        route_ids=["R1"],
        route_anchors={"R1": ("rail:S01514", "existing:EX_023", "rail:S01514")},
        current_clusters=["EX_011", "EX_023"],
        cluster_anchor={"EX_011": "existing:EX_011", "EX_023": "existing:EX_023"},
        route_current_clusters={"D184": {"EX_011", "EX_023"}, "D185": {"EX_011"}},
        current_directed_pairs=[("EX_011", "EX_023")],
        current_undirected_pairs=[("EX_011", "EX_023")],
    )
    assert out["retained_current_localizable_clusters_json"] == '["EX_023"]'
    assert out["historical_station_cluster_EX_011_retained"] == "false"
    assert out["project_station_bridge_EX_039_counts_as_current_continuity"] == "false"


def test_exact_current_anchor_retains_stop_and_directed_pair():
    out = scenario_continuity(
        scenario_id="S2",
        topology_family="test",
        route_ids=["R1"],
        route_anchors={"R1": ("rail:S01514", "existing:EX_011", "existing:EX_023", "P2V2S_0001")},
        current_clusters=["EX_011", "EX_023", "EX_026"],
        cluster_anchor={
            "EX_011": "existing:EX_011",
            "EX_023": "existing:EX_023",
            "EX_026": "existing:EX_026",
        },
        route_current_clusters={"D184": {"EX_011", "EX_023", "EX_026"}, "D185": {"EX_011"}},
        current_directed_pairs=[("EX_011", "EX_023"), ("EX_023", "EX_026")],
        current_undirected_pairs=[("EX_011", "EX_023"), ("EX_023", "EX_026")],
    )
    assert out["retained_current_localizable_cluster_count"] == 2
    assert out["retained_current_localizable_directed_adjacent_pair_count"] == 1
    assert out["retained_current_localizable_undirected_adjacent_pair_count"] == 1
    assert out["historical_station_cluster_EX_011_retained"] == "true"


def test_reverse_candidate_corridor_counts_undirected_but_not_directed():
    out = scenario_continuity(
        scenario_id="S3",
        topology_family="test",
        route_ids=["R1"],
        route_anchors={"R1": ("rail:S01514", "existing:EX_023", "existing:EX_011")},
        current_clusters=["EX_011", "EX_023"],
        cluster_anchor={"EX_011": "existing:EX_011", "EX_023": "existing:EX_023"},
        route_current_clusters={"D184": {"EX_011", "EX_023"}, "D185": {"EX_011"}},
        current_directed_pairs=[("EX_011", "EX_023")],
        current_undirected_pairs=[("EX_011", "EX_023")],
    )
    assert out["retained_current_localizable_directed_adjacent_pair_count"] == 0
    assert out["retained_current_localizable_undirected_adjacent_pair_count"] == 1


def test_nearby_proposed_anchor_never_counts_as_exact_current_stop():
    out = scenario_continuity(
        scenario_id="S4",
        topology_family="test",
        route_ids=["R1"],
        route_anchors={"R1": ("rail:S01514", "P2V2S_9999")},
        current_clusters=["EX_011"],
        cluster_anchor={"EX_011": "existing:EX_011"},
        route_current_clusters={"D184": {"EX_011"}, "D185": {"EX_011"}},
        current_directed_pairs=[],
        current_undirected_pairs=[],
    )
    assert out["retained_current_localizable_cluster_count"] == 0
    assert out["proximity_used_as_stop_retention"] == "false"
