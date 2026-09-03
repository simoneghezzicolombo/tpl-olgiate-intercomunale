#!/usr/bin/env python3
"""Persistent red-team diagnostics for Gate B spatial outputs.

This script does not create the primary model. It attempts to falsify or stress-test
outputs produced by ``audit_02_real_spatial.py`` and writes a compact JSON record
for audit history.
"""

from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd

from scripts.audit_02_real_spatial import (
    ACCESS_CELLS,
    CORE_STOPS,
    GRAPH_EDGES,
    OUT_DIR,
    POP_CELLS,
    THRESHOLDS_MIN,
    WALK_CONNECTOR_KMH,
    tobler_walk_minutes,
)

OUT = OUT_DIR / "redteam_summary.json"


def _coverage_from_mask(acc: pd.DataFrame, mask: pd.Series) -> float:
    total = float(acc["pop_calibrated_2025"].sum())
    return 100.0 * float(acc.loc[mask, "pop_calibrated_2025"].sum()) / total


def calibration_diagnostics(pop: pd.DataFrame) -> list[dict]:
    grouped = (
        pop.groupby(["PRO_COM_T", "COMUNE"], as_index=False)
        .agg(
            worldpop_2020_sum=("worldpop_2020_raw", "sum"),
            calibrated_2025=("pop_calibrated_2025", "sum"),
            calibration_factor=("calibration_factor_2025", "first"),
            populated_cells=("cell_id", "count"),
        )
        .sort_values("PRO_COM_T")
    )
    return grouped.to_dict(orient="records")


def connector_sensitivity(acc: pd.DataFrame) -> dict:
    q = acc["connector_distance_m"].quantile([0, 0.5, 0.9, 0.95, 0.99, 1.0])
    result = {
        "distance_quantiles_m": {
            "min": float(q.loc[0.0]),
            "p50": float(q.loc[0.5]),
            "p90": float(q.loc[0.9]),
            "p95": float(q.loc[0.95]),
            "p99": float(q.loc[0.99]),
            "max": float(q.loc[1.0]),
        },
        "coverage_pct_by_cap": {},
    }
    for cap in (100, 200, 300):
        by_threshold = {}
        for threshold in THRESHOLDS_MIN:
            mask = (
                (acc["connector_distance_m"] <= cap)
                & acc["walk_min_to_nearest_gtfs_stop"].notna()
                & (acc["walk_min_to_nearest_gtfs_stop"] <= threshold)
            )
            by_threshold[str(threshold)] = _coverage_from_mask(acc, mask)
        result["coverage_pct_by_cap"][str(cap)] = by_threshold
    return result


def stop_snap_diagnostics(stops: pd.DataFrame) -> dict:
    ordered = stops.sort_values("snap_distance_m", ascending=False)
    failures = ordered.loc[~ordered["snap_ok"], [
        "stop_id", "stop_name", "COMUNE", "snap_distance_m"
    ]]
    return {
        "total": int(len(stops)),
        "snap_ok": int(stops["snap_ok"].sum()),
        "snap_failed": int((~stops["snap_ok"]).sum()),
        "failed_stops": failures.to_dict(orient="records"),
        "largest_snap_m": float(ordered["snap_distance_m"].max()),
        "largest_accepted_snap_m": float(
            ordered.loc[ordered["snap_ok"], "snap_distance_m"].max()
        ),
    }


def slope_diagnostics(edges: pd.DataFrame) -> dict:
    values = (
        edges.loc[edges["in_giant_component"], "slope_uv"]
        .abs()
        .replace([np.inf, -np.inf], np.nan)
        .dropna()
    )
    q = values.quantile([0.5, 0.9, 0.95, 0.99, 0.999, 1.0])
    return {
        "n_edges": int(len(values)),
        "abs_slope_quantiles": {
            "p50": float(q.loc[0.5]),
            "p90": float(q.loc[0.9]),
            "p95": float(q.loc[0.95]),
            "p99": float(q.loc[0.99]),
            "p999": float(q.loc[0.999]),
            "max": float(q.loc[1.0]),
        },
        "edges_abs_slope_gt_030": int((values > 0.30).sum()),
        "share_abs_slope_gt_030": float((values > 0.30).mean()),
        "edges_abs_slope_gt_050": int((values > 0.50).sum()),
        "share_abs_slope_gt_050": float((values > 0.50).mean()),
    }


def flat_walk_sensitivity(
    acc: pd.DataFrame, stops: pd.DataFrame, edges: pd.DataFrame
) -> dict:
    """Compare slope-adjusted coverage with a flat-speed network counterfactual.

    Geometry, cell connectors, stop connectors and graph topology stay identical;
    only edge walking time is recomputed with zero grade. This is a sensitivity
    diagnostic, not an alternative factual result.
    """
    usable = stops[stops["snap_ok"]].copy()
    giant_edges = edges[edges["in_giant_component"]].copy()
    G = nx.Graph()
    for row in giant_edges.itertuples(index=False):
        weight = tobler_walk_minutes(float(row.length_m), 0.0)
        u, v = int(row.u), int(row.v)
        if G.has_edge(u, v):
            if weight < G[u][v]["flat_walk_min"]:
                G[u][v]["flat_walk_min"] = weight
        else:
            G.add_edge(u, v, flat_walk_min=weight)

    super_source = 0
    while super_source in G:
        super_source -= 1
    G.add_node(super_source)
    rate_m_per_min = WALK_CONNECTOR_KMH * 1000.0 / 60.0
    stop_costs: dict[int, float] = {}
    for row in usable.itertuples(index=False):
        node = int(row.graph_node_id)
        cost = float(row.snap_distance_m) / rate_m_per_min
        stop_costs[node] = min(stop_costs.get(node, float("inf")), cost)
    for node, cost in stop_costs.items():
        if node in G:
            G.add_edge(super_source, node, flat_walk_min=cost)

    dist = nx.single_source_dijkstra_path_length(G, super_source, weight="flat_walk_min")
    flat_total = np.array(
        [dist.get(int(node), np.nan) for node in acc["nearest_graph_node_id"]],
        dtype=float,
    ) + acc["connector_walk_min"].to_numpy(dtype=float)
    flat_total[~acc["connector_within_limit"].astype(bool).to_numpy()] = np.nan

    result = {"coverage_pct": {}, "slope_minus_flat_percentage_points": {}}
    total_pop = float(acc["pop_calibrated_2025"].sum())
    for threshold in THRESHOLDS_MIN:
        flat_mask = np.isfinite(flat_total) & (flat_total <= threshold)
        flat_pct = (
            100.0
            * float(acc.loc[flat_mask, "pop_calibrated_2025"].sum())
            / total_pop
        )
        slope_mask = (
            acc["walk_min_to_nearest_gtfs_stop"].notna()
            & (acc["walk_min_to_nearest_gtfs_stop"] <= threshold)
        )
        slope_pct = _coverage_from_mask(acc, slope_mask)
        result["coverage_pct"][str(threshold)] = {
            "slope_adjusted": slope_pct,
            "flat_counterfactual": flat_pct,
        }
        result["slope_minus_flat_percentage_points"][str(threshold)] = slope_pct - flat_pct
    return result


def main() -> None:
    required = [POP_CELLS, ACCESS_CELLS, CORE_STOPS, GRAPH_EDGES]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise FileNotFoundError("Run Gate B pipeline before red-team: " + ", ".join(missing))

    pop = pd.read_csv(POP_CELLS, dtype={"PRO_COM_T": str})
    acc = pd.read_csv(ACCESS_CELLS, dtype={"PRO_COM_T": str})
    stops = pd.read_csv(CORE_STOPS, dtype={"stop_id": str})
    edges = pd.read_csv(GRAPH_EDGES)

    payload = {
        "epistemic_status": "MODEL_OUTPUT_DIAGNOSTIC",
        "core_population_calibrated_2025": float(pop["pop_calibrated_2025"].sum()),
        "calibration": calibration_diagnostics(pop),
        "cell_connector": connector_sensitivity(acc),
        "stop_snap": stop_snap_diagnostics(stops),
        "dsm_slope": slope_diagnostics(edges),
        "flat_walk_sensitivity": flat_walk_sensitivity(acc, stops, edges),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
