import networkx as nx
import pandas as pd

from src.phase2_stop_cluster import walk_distances_to_stop_records
from src.phase2_stop_metrics_v2 import geometric_overlap_prune


def test_physical_cluster_catchment_uses_all_gtfs_records():
    graph = nx.DiGraph()
    graph.add_edge(1, 2, walk_min=1.0)
    graph.add_edge(2, 1, walk_min=1.0)
    graph.add_edge(2, 3, walk_min=1.0)
    graph.add_edge(3, 2, walk_min=1.0)
    records = pd.DataFrame(
        [
            {"graph_node_id": 1, "snap_distance_m": 0.0, "snap_ok": True},
            {"graph_node_id": 3, "snap_distance_m": 0.0, "snap_ok": True},
        ]
    )
    distances = walk_distances_to_stop_records(graph, records, cutoff=5)
    assert distances[1] == 0.0
    assert distances[3] == 0.0
    assert distances[2] == 1.0


def test_geometric_pruning_keeps_cellsets_attached_after_coordinate_sort():
    metrics = pd.DataFrame(
        [
            {"x_utm32": 400.0, "y_utm32": 0.0, "osm_way_id": "b", "sample_index": 0},
            {"x_utm32": 0.0, "y_utm32": 0.0, "osm_way_id": "a", "sample_index": 0},
            {"x_utm32": 450.0, "y_utm32": 0.0, "osm_way_id": "c", "sample_index": 0},
        ]
    )
    cellsets = {0: {"RIGHT"}, 1: {"LEFT"}, 2: {"RIGHT"}}
    kept, audit = geometric_overlap_prune(metrics, cellsets)
    assert len(kept) == 2
    pruned = audit[audit["pruned"]]
    assert len(pruned) == 1
    assert int(pruned.iloc[0]["preprune_row"]) == 2
    assert int(pruned.iloc[0]["representative_preprune_row"]) == 0
