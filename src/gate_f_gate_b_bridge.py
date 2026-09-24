"""Scenario-specific Gate B coverage bridge using persisted validated Gate B graph artifacts.

The bridge reuses Gate B population-cell connectors and directional walk edges.
It does not use Euclidean catchment buffers, road multipliers or invented stops.
"""
from __future__ import annotations

import json
from pathlib import Path
import networkx as nx
import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree


ALLOWED_STOP_STATUSES = {"FACT", "DERIVED", "ESTIMATE", "RECONSTRUCTED", "MODEL OUTPUT", "FIELD CHECK"}


def load_policy(path: str | Path) -> dict[str, object]:
    try:
        policy = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read Gate B-to-F policy: {exc}") from exc
    required = {
        "schema_version", "comparison_id", "threshold_min", "max_stop_snap_m",
        "walk_connector_kmh", "territory_definition_id",
    }
    missing = required - set(policy)
    if missing:
        raise ValueError(f"Gate B-to-F policy missing fields: {sorted(missing)}")
    if policy["schema_version"] != 1:
        raise ValueError("Gate B-to-F policy schema_version must equal 1")
    threshold = float(policy["threshold_min"])
    snap = float(policy["max_stop_snap_m"])
    speed = float(policy["walk_connector_kmh"])
    if threshold <= 0 or snap <= 0 or speed <= 0:
        raise ValueError("Gate B-to-F threshold, snap limit and connector speed must be > 0")
    for key in ("comparison_id", "territory_definition_id"):
        if not str(policy[key]).strip():
            raise ValueError(f"Gate B-to-F policy {key} must be non-empty")
    return {
        "comparison_id": str(policy["comparison_id"]).strip(),
        "threshold_min": threshold,
        "max_stop_snap_m": snap,
        "walk_connector_kmh": speed,
        "territory_definition_id": str(policy["territory_definition_id"]).strip(),
    }


def load_candidate_stops(path: str | Path) -> pd.DataFrame:
    required = {
        "scenario_id", "stop_id", "stop_lat", "stop_lon", "territory_id",
        "epistemic_status", "source",
    }
    frame = pd.read_csv(path, dtype={"scenario_id": str, "stop_id": str, "territory_id": str})
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Candidate stop set missing columns: {missing}")
    if frame.empty:
        raise ValueError("Candidate stop set is empty")
    for col in ("scenario_id", "stop_id", "territory_id", "source"):
        if frame[col].isna().any() or frame[col].astype(str).str.strip().eq("").any():
            raise ValueError(f"Candidate stops require non-empty {col}")
    if frame.duplicated(["scenario_id", "stop_id"]).any():
        raise ValueError("Candidate stop_id must be unique within each scenario")
    status = frame["epistemic_status"].astype(str).str.strip().str.upper()
    if status.eq("ASSUMPTION").any():
        raise ValueError("ASSUMPTION candidate stops cannot feed Gate F production coverage")
    bad = sorted(set(status) - ALLOWED_STOP_STATUSES)
    if bad:
        raise ValueError(f"Unsupported candidate-stop epistemic status: {bad}")
    frame["epistemic_status"] = status
    lat = pd.to_numeric(frame["stop_lat"], errors="coerce")
    lon = pd.to_numeric(frame["stop_lon"], errors="coerce")
    if lat.isna().any() or lon.isna().any() or (~lat.between(-90, 90)).any() or (~lon.between(-180, 180)).any():
        raise ValueError("Candidate stop coordinates must be finite WGS84 degrees")
    frame["stop_lat"] = lat; frame["stop_lon"] = lon
    return frame


def load_gate_b_graph(nodes_path: str | Path, edges_path: str | Path) -> tuple[nx.DiGraph, pd.DataFrame, cKDTree]:
    nodes = pd.read_csv(nodes_path)
    edges = pd.read_csv(edges_path)
    node_required = {"node_id", "x_utm32", "y_utm32", "in_giant_component"}
    edge_required = {"u", "v", "walk_min_uv", "walk_min_vu", "in_giant_component"}
    if not node_required.issubset(nodes.columns) or not edge_required.issubset(edges.columns):
        raise ValueError("Gate B graph artifact schema is incomplete")
    giant_nodes = nodes.loc[nodes["in_giant_component"].astype(str).str.lower().isin({"true", "1"})].copy()
    giant_edges = edges.loc[edges["in_giant_component"].astype(str).str.lower().isin({"true", "1"})].copy()
    if giant_nodes.empty or giant_edges.empty:
        raise ValueError("Gate B graph giant component is empty")
    graph = nx.DiGraph()
    for _, row in giant_nodes.iterrows():
        graph.add_node(int(row["node_id"]), x=float(row["x_utm32"]), y=float(row["y_utm32"]))
    for _, row in giant_edges.iterrows():
        u, v = int(row["u"]), int(row["v"])
        if u in graph and v in graph:
            uv, vu = float(row["walk_min_uv"]), float(row["walk_min_vu"])
            if not np.isfinite([uv, vu]).all() or uv < 0 or vu < 0:
                raise ValueError("Gate B graph contains invalid walking time")
            graph.add_edge(u, v, walk_min=uv)
            graph.add_edge(v, u, walk_min=vu)
    ids = giant_nodes["node_id"].astype(int).to_numpy()
    xy = giant_nodes[["x_utm32", "y_utm32"]].to_numpy(dtype=float)
    return graph, giant_nodes, cKDTree(xy)


def load_population_access(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={"PRO_COM_T": str})
    required = {
        "cell_id", "PRO_COM_T", "COMUNE", "pop_calibrated_2025", "nearest_graph_node_id",
        "connector_walk_min", "connector_within_limit",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Gate B population accessibility artifact missing columns: {missing}")
    pop = pd.to_numeric(frame["pop_calibrated_2025"], errors="coerce")
    if pop.isna().any() or (pop < 0).any() or pop.sum() <= 0:
        raise ValueError("Gate B population accessibility contains invalid population")
    frame["pop_calibrated_2025"] = pop
    return frame


def evaluate_candidate_coverage(
    stops_path: str | Path,
    nodes_path: str | Path,
    edges_path: str | Path,
    population_access_path: str | Path,
    policy_path: str | Path,
    *,
    gate_b_commit: str,
) -> pd.DataFrame:
    if len(gate_b_commit) != 40 or any(ch not in "0123456789abcdef" for ch in gate_b_commit.lower()):
        raise ValueError("gate_b_commit must be a full 40-hex SHA")
    policy = load_policy(policy_path)
    stops = load_candidate_stops(stops_path)
    graph, nodes, tree = load_gate_b_graph(nodes_path, edges_path)
    cells = load_population_access(population_access_path)
    ids = nodes["node_id"].astype(int).to_numpy()
    transformer = Transformer.from_crs(4326, 32632, always_xy=True)
    connector_speed_m_per_min = float(policy["walk_connector_kmh"]) * 1000.0 / 60.0
    threshold = float(policy["threshold_min"])

    rows = []
    for scenario_id, scenario_stops in stops.groupby("scenario_id", sort=True):
        xs, ys = transformer.transform(
            scenario_stops["stop_lon"].to_numpy(dtype=float),
            scenario_stops["stop_lat"].to_numpy(dtype=float),
        )
        snap_dist, idx = tree.query(np.column_stack([xs, ys]), k=1)
        if (snap_dist > float(policy["max_stop_snap_m"])).any():
            bad = scenario_stops.loc[snap_dist > float(policy["max_stop_snap_m"]), "stop_id"].astype(str).tolist()
            raise ValueError(f"{scenario_id}: candidate stops exceed Gate B snap limit: {bad}")
        stop_nodes = ids[idx]
        reversed_graph = graph.reverse(copy=True)
        super_source = min(graph.nodes) - 1
        while super_source in reversed_graph:
            super_source -= 1
        reversed_graph.add_node(super_source)
        connector_by_node: dict[int, float] = {}
        for node, distance in zip(stop_nodes, snap_dist):
            node = int(node)
            connector = float(distance) / connector_speed_m_per_min
            connector_by_node[node] = min(connector_by_node.get(node, float("inf")), connector)
        for node, connector in connector_by_node.items():
            reversed_graph.add_edge(super_source, node, walk_min=connector)
        distances = nx.single_source_dijkstra_path_length(reversed_graph, super_source, weight="walk_min")

        nearest = cells["nearest_graph_node_id"].astype(int)
        network_min = nearest.map(lambda node: distances.get(int(node), np.nan)).astype(float)
        connector_ok = cells["connector_within_limit"].astype(str).str.lower().isin({"true", "1"})
        total_walk = network_min + pd.to_numeric(cells["connector_walk_min"], errors="coerce")
        covered = connector_ok & total_walk.notna() & total_walk.le(threshold)
        total_pop = float(cells["pop_calibrated_2025"].sum())
        covered_pop = float(cells.loc[covered, "pop_calibrated_2025"].sum())
        coverage_pct = covered_pop / total_pop * 100.0
        territories = int(scenario_stops["territory_id"].astype(str).nunique())
        stop_sources = sorted(set(scenario_stops["source"].astype(str)))
        source = (
            f"GateB:{gate_b_commit}:walk_graph_nodes+walk_graph_edges+population_accessibility;"
            f"candidate_stops={'|'.join(stop_sources)}"
        )
        basis = (
            f"{policy['comparison_id']}|GateB={gate_b_commit}|threshold={threshold:g}min"
            f"|max_stop_snap={float(policy['max_stop_snap_m']):g}m"
            f"|connector_speed={float(policy['walk_connector_kmh']):g}kmh"
        )
        rows.append({
            "scenario_id": str(scenario_id),
            "population_covered_pct": coverage_pct,
            "population_covered_pct__status": "MODEL OUTPUT",
            "population_covered_pct__source": source,
            "population_covered_pct__unit": "%",
            "population_covered_pct__semantics": "PERCENT_OF_DEFINED_POPULATION_DENOMINATOR",
            "population_covered_pct__comparison_basis": basis + "|population=GateB_calibrated_2025_core",
            "territories_served_count": territories,
            "territories_served_count__status": "DERIVED",
            "territories_served_count__source": source,
            "territories_served_count__unit": "count",
            "territories_served_count__semantics": "COUNT_OF_DEFINED_TERRITORIAL_UNITS",
            "territories_served_count__comparison_basis": (
                str(policy["comparison_id"]) + "|territory_definition=" + str(policy["territory_definition_id"])
            ),
            "population_covered": covered_pop,
            "population_denominator": total_pop,
            "candidate_stop_count": int(len(scenario_stops)),
        })
    return pd.DataFrame(rows)
