"""Physical-stop cluster walking catchments for Phase 2."""
from __future__ import annotations

import networkx as nx
import pandas as pd

from src.phase2_stop_core import WALK_CONNECTOR_KMH


def walk_distances_to_stop_records(
    directed: nx.DiGraph,
    records: pd.DataFrame,
    *,
    cutoff: float = 12.0,
) -> dict[int, float]:
    """Return minimum walk minutes to any snapped GTFS record in one physical cluster.

    A physical stop can contain multiple official GTFS records, for example opposite
    sides of a road. Each snapped record is therefore a source with its own connector
    time. Using one representative record would understate accessibility from the
    other side and is not equivalent to the Gate B stop universe.
    """
    required = {"graph_node_id", "snap_distance_m", "snap_ok"}
    missing = required - set(records.columns)
    if missing:
        raise ValueError(f"Physical stop records missing columns: {sorted(missing)}")
    snapped = records.loc[records["snap_ok"].astype(str).str.lower().isin({"true", "1"})].copy()
    if snapped.empty:
        return {}

    reversed_graph = directed.reverse(copy=True)
    super_source = min(reversed_graph.nodes) - 1
    while super_source in reversed_graph:
        super_source -= 1
    reversed_graph.add_node(super_source)

    speed_m_per_min = WALK_CONNECTOR_KMH * 1000.0 / 60.0
    best_connector_by_node: dict[int, float] = {}
    for row in snapped.itertuples(index=False):
        node = int(row.graph_node_id)
        connector = float(row.snap_distance_m) / speed_m_per_min
        best_connector_by_node[node] = min(best_connector_by_node.get(node, float("inf")), connector)
    for node, connector in best_connector_by_node.items():
        reversed_graph.add_edge(super_source, node, walk_min=connector)

    distances = nx.single_source_dijkstra_path_length(
        reversed_graph,
        super_source,
        cutoff=float(cutoff),
        weight="walk_min",
    )
    distances.pop(super_source, None)
    return {int(node): float(minutes) for node, minutes in distances.items()}
