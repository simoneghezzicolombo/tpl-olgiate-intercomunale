from __future__ import annotations

from typing import Mapping

import numpy as np
import pandas as pd

from phase2_rt029_v4_common import DECISION_SCENARIO, THRESHOLDS, RT029V4ContractError

def build_candidate_decision_metrics(
    structures: pd.DataFrame,
    stop_mapping: pd.DataFrame,
    accessibility: pd.DataFrame,
    equity: pd.DataFrame,
    operating: pd.DataFrame,
) -> pd.DataFrame:
    decision = stop_mapping[stop_mapping["scenario"] == DECISION_SCENARIO][
        ["structure_id", "stop_set_id", "stop_count"]
    ]
    if len(decision) != len(structures):
        raise RT029V4ContractError("one decision stop-set mapping is required per structure")
    core = accessibility[accessibility["scope"] == "CORE"].copy()
    wide_equity = equity.pivot(
        index="stop_set_id", columns="threshold_min", values="minimum_core_municipality_share"
    ).reset_index()
    wide_equity.columns = [
        "stop_set_id" if name == "stop_set_id" else f"minimum_core_municipality_share_le_{float(name):g}_min"
        for name in wide_equity.columns
    ]
    metrics = (
        decision.merge(core, on="stop_set_id", how="left", validate="many_to_one")
        .merge(wide_equity, on="stop_set_id", how="left", validate="many_to_one")
        .merge(operating, on="structure_id", how="left", validate="one_to_one")
    )
    required = [
        "reachable_population_share", "reachable_weighted_p90_walk_min",
        "minimum_bidirectional_link_distance_m",
    ]
    required += [f"share_le_{threshold:g}_min" for threshold in THRESHOLDS]
    required += [f"minimum_core_municipality_share_le_{threshold:g}_min" for threshold in THRESHOLDS]
    if metrics[required].isna().any().any():
        raise RT029V4ContractError("candidate decision metrics contain missing values")
    return metrics.sort_values("structure_id", kind="mergesort").reset_index(drop=True)


def _dominates_vector(a: np.ndarray, b: np.ndarray) -> bool:
    return bool(np.all(a <= b) and np.any(a < b))


def pareto_front_fast(
    frame: pd.DataFrame,
    dimensions: Mapping[str, str],
) -> tuple[str, ...]:
    if frame["structure_id"].astype(str).duplicated().any():
        raise RT029V4ContractError("Pareto structure_id must be unique")
    columns = list(dimensions)
    matrix = frame[columns].to_numpy(dtype=float, copy=True)
    if not np.isfinite(matrix).all():
        raise RT029V4ContractError("non-finite Pareto metric")
    for index, column in enumerate(columns):
        direction = dimensions[column]
        if direction == "max":
            matrix[:, index] *= -1.0
        elif direction != "min":
            raise RT029V4ContractError("Pareto direction must be min or max")
    ids = frame["structure_id"].astype(str).to_numpy()
    order = sorted(
        range(len(frame)),
        key=lambda i: tuple(matrix[i].tolist()) + (ids[i],),
    )
    frontier_indices: list[int] = []
    frontier_matrix = np.empty((0, matrix.shape[1]), dtype=float)
    for index in order:
        candidate = matrix[index]
        if len(frontier_indices):
            dominated_by_frontier = np.all(frontier_matrix <= candidate, axis=1) & np.any(
                frontier_matrix < candidate, axis=1
            )
            if dominated_by_frontier.any():
                continue
            candidate_dominates = np.all(candidate <= frontier_matrix, axis=1) & np.any(
                candidate < frontier_matrix, axis=1
            )
            if candidate_dominates.any():
                keep = ~candidate_dominates
                frontier_matrix = frontier_matrix[keep]
                frontier_indices = [
                    old_index for old_index, retained in zip(frontier_indices, keep) if retained
                ]
        frontier_matrix = np.vstack((frontier_matrix, candidate))
        frontier_indices.append(index)
    return tuple(sorted(ids[frontier_indices].tolist()))


def build_pareto_outputs(
    candidate_metrics: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    min_distance = candidate_metrics.groupby("stop_set_id")[
        "minimum_bidirectional_link_distance_m"
    ].transform("min")
    reduced = candidate_metrics[
        candidate_metrics["minimum_bidirectional_link_distance_m"] == min_distance
    ].copy()
    if reduced["stop_set_id"].nunique() != candidate_metrics["stop_set_id"].nunique():
        raise RT029V4ContractError("exact stop-set dominance reduction lost a stop set")
    frontier_rows: list[dict[str, object]] = []
    for threshold in THRESHOLDS:
        threshold_col = f"share_le_{threshold:g}_min"
        equity_col = f"minimum_core_municipality_share_le_{threshold:g}_min"
        frontier_ids = set(
            pareto_front_fast(
                reduced,
                {
                    "reachable_population_share": "max",
                    threshold_col: "max",
                    equity_col: "max",
                    "reachable_weighted_p90_walk_min": "min",
                    "minimum_bidirectional_link_distance_m": "min",
                },
            )
        )
        selected = reduced[reduced["structure_id"].astype(str).isin(frontier_ids)].sort_values(
            "structure_id", kind="mergesort"
        )
        for row in selected.itertuples(index=False):
            frontier_rows.append(
                {
                    "threshold_min": threshold,
                    "structure_id": str(row.structure_id),
                    "structural_layer": str(row.structural_layer),
                    "edge_count": int(row.edge_count),
                    "topology_class": str(row.topology_class),
                    "stop_set_id": str(row.stop_set_id),
                    "passenger_stop_count": int(row.stop_count),
                    "core_reachable_population_share": float(row.reachable_population_share),
                    "core_threshold_share": float(getattr(row, threshold_col)),
                    "minimum_core_municipality_share": float(getattr(row, equity_col)),
                    "core_reachable_weighted_p90_walk_min": float(
                        row.reachable_weighted_p90_walk_min
                    ),
                    "minimum_bidirectional_link_distance_m": float(
                        row.minimum_bidirectional_link_distance_m
                    ),
                    "frontier_semantics": (
                        "NONDOMINATED_WITHIN_COMPLETE_E4_E5_E6_DOMAIN_NO_WEIGHTED_COMPOSITE"
                    ),
                }
            )
    frontiers = pd.DataFrame(frontier_rows).sort_values(
        ["threshold_min", "structure_id"], kind="mergesort"
    ).reset_index(drop=True)
    if frontiers.empty:
        raise RT029V4ContractError("Pareto frontier unexpectedly empty")
    shortlist_rows: list[dict[str, object]] = []
    for structure_id, group in frontiers.groupby("structure_id", sort=True):
        first = group.iloc[0]
        thresholds = sorted(float(value) for value in group["threshold_min"])
        shortlist_rows.append(
            {
                "structure_id": str(structure_id),
                "structural_layer": str(first["structural_layer"]),
                "edge_count": int(first["edge_count"]),
                "topology_class": str(first["topology_class"]),
                "stop_set_id": str(first["stop_set_id"]),
                "passenger_stop_count": int(first["passenger_stop_count"]),
                "frontier_membership_count": len(thresholds),
                "frontier_thresholds_min": ";".join(f"{value:g}" for value in thresholds),
                "shortlist_semantics": (
                    "UNION_OF_THRESHOLD_PARETO_FRONTS_COMPLETE_THROUGH_E6_NOT_FINAL_WITHOUT_STOPPING_RULE"
                ),
            }
        )
    shortlist = pd.DataFrame(shortlist_rows).sort_values(
        "structure_id", kind="mergesort"
    ).reset_index(drop=True)
    diagnostics = {
        "pre_pareto_structure_count": int(len(candidate_metrics)),
        "post_exact_stop_set_dominance_reduction_count": int(len(reduced)),
        "decision_stop_set_count": int(candidate_metrics["stop_set_id"].nunique()),
    }
    return frontiers, shortlist, diagnostics
