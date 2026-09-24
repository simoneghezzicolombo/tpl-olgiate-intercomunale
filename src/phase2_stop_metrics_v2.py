from __future__ import annotations
import math
import numpy as np
import pandas as pd

from src.phase2_stop_core import (
    PRUNE_CANDIDATE_RADIUS_M,
    PRUNE_CATCHMENT_JACCARD,
    PRUNE_CATCHMENT_RADIUS_M,
    THRESHOLDS,
    cell_membership,
    walk_distances_to_stop_node,
)
from src.phase2_stop_sources import attach_point_to_walk_graph


def build_candidate_metrics(
    cands,
    cells,
    anchors,
    directed,
    ids,
    tree,
    transformer,
    nearest_stop_dist,
    nearest_stop_source,
    cluster_routes,
):
    cands = attach_point_to_walk_graph(pd.DataFrame(cands.drop(columns="geometry")), tree, ids, transformer)
    cands = cands[cands.walk_graph_snap_ok].copy().reset_index(drop=True)
    rows = []
    for _, row in cands.iterrows():
        node = int(row.walk_graph_node_id)
        distances = walk_distances_to_stop_node(
            directed,
            node,
            float(row.walk_graph_connector_min),
            cutoff=max(THRESHOLDS),
        )
        values = dict(row)
        for threshold in THRESHOLDS:
            mask, _ = cell_membership(cells, distances, threshold)
            reachable_population = float(cells.loc[mask, "pop_calibrated_2025"].sum())
            current = cells[f"covered_{threshold}min"].astype(str).str.lower().isin({"true", "1"})
            added = mask & ~current
            overlap = mask & current
            overlap_population = float(cells.loc[overlap, "pop_calibrated_2025"].sum())
            values[f"population_reachable_{threshold}min"] = reachable_population
            values[f"population_additional_{threshold}min"] = float(
                cells.loc[added, "pop_calibrated_2025"].sum()
            )
            values[f"existing_catchment_overlap_population_{threshold}min"] = overlap_population
            values[f"existing_catchment_overlap_pct_{threshold}min"] = (
                overlap_population / reachable_population * 100.0 if reachable_population > 0 else 0.0
            )

        network_distance = nearest_stop_dist.get(node, float("inf")) + float(row.walk_graph_connector_m)
        values["nearest_official_stop_walk_network_m"] = float(network_distance)
        values["nearest_official_stop_cluster_id"] = nearest_stop_source.get(node, "")
        routes = cluster_routes.get(values["nearest_official_stop_cluster_id"], set())
        values["nearby_official_routes"] = "|".join(sorted(routes))
        values["nearby_official_route_count"] = len(routes)

        for anchor_type in ("SETTLEMENT", "DESTINATION"):
            total_covered = 0
            additionally_covered = 0
            added_names = []
            for anchor in anchors[anchors.anchor_type.eq(anchor_type)].itertuples(index=False):
                if not bool(anchor.walk_graph_snap_ok):
                    continue
                network = distances.get(int(anchor.walk_graph_node_id), np.nan)
                walk_minutes = (
                    float(network) + float(anchor.walk_graph_connector_min)
                    if np.isfinite(network)
                    else np.nan
                )
                if np.isfinite(walk_minutes) and walk_minutes <= 10:
                    total_covered += 1
                    if not np.isfinite(anchor.current_walk_min) or float(anchor.current_walk_min) > 10:
                        additionally_covered += 1
                        added_names.append(str(anchor.name))
            key = anchor_type.lower()
            values[f"{key}_coverage_10min_count"] = total_covered
            values[f"{key}_additional_10min_count"] = additionally_covered
            values[f"{key}_additional_10min_names"] = "|".join(sorted(set(added_names)))
        rows.append(values)
    return pd.DataFrame(rows)


def geometric_overlap_prune(metrics: pd.DataFrame, cellsets: dict[int, set[str]]):
    """Spatial/catchment compression with stable pre-sort cellset keys.

    Coordinate ordering is used only for deterministic pruning. It is not a utility
    ranking. Cellsets remain attached to their original pre-prune rows even after the
    coordinate sort, preventing a silent Jaccard-index mismatch.
    """
    if metrics.empty:
        return metrics.copy(), pd.DataFrame()
    ordered = metrics.copy()
    ordered["_cellset_key"] = ordered.index.astype(int)
    ordered = ordered.sort_values(["y_utm32", "x_utm32", "osm_way_id", "sample_index"]).reset_index(drop=True)

    kept = []
    audit = []
    for index, row in ordered.iterrows():
        x, y = float(row.x_utm32), float(row.y_utm32)
        source_key = int(row["_cellset_key"])
        source_cells = cellsets.get(source_key, set())
        redundant_with = None
        reason = None
        distance_used = np.nan
        jaccard_used = np.nan
        for kept_index in kept:
            other = ordered.loc[kept_index]
            distance = math.hypot(x - float(other.x_utm32), y - float(other.y_utm32))
            other_key = int(other["_cellset_key"])
            other_cells = cellsets.get(other_key, set())
            if distance < PRUNE_CANDIDATE_RADIUS_M:
                redundant_with = kept_index
                reason = "CANDIDATE_SPACING_REDUNDANCY"
                distance_used = distance
                break
            if distance < PRUNE_CATCHMENT_RADIUS_M:
                union = source_cells | other_cells
                jaccard = len(source_cells & other_cells) / len(union) if union else 1.0
                if jaccard >= PRUNE_CATCHMENT_JACCARD:
                    redundant_with = kept_index
                    reason = "TEN_MIN_CATCHMENT_REDUNDANCY"
                    distance_used = distance
                    jaccard_used = jaccard
                    break
        if redundant_with is None:
            kept.append(index)
            audit.append(
                {
                    "preprune_row": source_key,
                    "representative_preprune_row": source_key,
                    "pruned": False,
                    "reason": "RETAINED_SPATIAL_ORDER",
                    "distance_m": np.nan,
                    "catchment_jaccard": np.nan,
                }
            )
        else:
            audit.append(
                {
                    "preprune_row": source_key,
                    "representative_preprune_row": int(ordered.loc[redundant_with, "_cellset_key"]),
                    "pruned": True,
                    "reason": reason,
                    "distance_m": distance_used,
                    "catchment_jaccard": jaccard_used,
                }
            )
    return (
        ordered.iloc[kept].drop(columns="_cellset_key").copy().reset_index(drop=True),
        pd.DataFrame(audit),
    )
