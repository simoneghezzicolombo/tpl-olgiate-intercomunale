from __future__ import annotations

import math

import numpy as np
import pandas as pd

from phase2_rt029_v4_common import (
    DIRECTIONS, THRESHOLDS, RT029V4ContractError, WalkSubstrate, _split_unique_ids,
)

def build_operating_envelope(
    structures: pd.DataFrame,
    realizations: pd.DataFrame,
) -> pd.DataFrame:
    component = (
        realizations.groupby(["structural_link_id", "direction"], sort=True)
        .agg(
            min_distance_m=("distance_m", "min"),
            max_distance_m=("distance_m", "max"),
            min_runtime_min=("running_minutes_model", "min"),
            max_runtime_min=("running_minutes_model", "max"),
        )
        .reset_index()
    )
    links: dict[str, tuple[float, float, float, float]] = {}
    for link_id, group in component.groupby("structural_link_id", sort=True):
        if set(group["direction"].astype(str)) != set(DIRECTIONS):
            raise RT029V4ContractError(f"{link_id} missing a direction in operating envelope")
        links[str(link_id)] = (
            math.fsum(sorted(float(v) for v in group["min_distance_m"])),
            math.fsum(sorted(float(v) for v in group["max_distance_m"])),
            math.fsum(sorted(float(v) for v in group["min_runtime_min"])),
            math.fsum(sorted(float(v) for v in group["max_runtime_min"])),
        )
    rows: list[dict[str, object]] = []
    for row in structures.itertuples(index=False):
        sid = str(row.structure_id)
        link_ids = tuple(sorted(_split_unique_ids(row.link_ids, f"{sid} link_ids")))
        missing = sorted(set(link_ids) - set(links))
        if missing:
            raise RT029V4ContractError(f"{sid} uses links absent from RT-023: {missing}")
        rows.append(
            {
                "structure_id": sid,
                "structural_layer": str(row.structural_layer),
                "edge_count": int(row.edge_count),
                "topology_class": str(row.topology_class),
                "minimum_bidirectional_link_distance_m": math.fsum(
                    links[link_id][0] for link_id in link_ids
                ),
                "maximum_bidirectional_link_distance_m": math.fsum(
                    links[link_id][1] for link_id in link_ids
                ),
                "minimum_bidirectional_link_running_minutes_model": math.fsum(
                    links[link_id][2] for link_id in link_ids
                ),
                "maximum_bidirectional_link_running_minutes_model": math.fsum(
                    links[link_id][3] for link_id in link_ids
                ),
            }
        )
    return pd.DataFrame(rows).sort_values("structure_id", kind="mergesort").reset_index(drop=True)


def _batch_access_metrics(
    best: np.ndarray,
    weights: np.ndarray,
    *,
    include_quantiles: bool,
) -> dict[str, np.ndarray]:
    if best.ndim != 2:
        raise RT029V4ContractError("best-walk batch must be 2D")
    if len(weights) != best.shape[0]:
        raise RT029V4ContractError("weight vector length does not match batch rows")
    total = float(np.sum(weights))
    if not math.isfinite(total) or total <= 0:
        raise RT029V4ContractError("population slice has zero weight")
    weight_matrix = weights[:, None]
    reachable = np.isfinite(best)
    reachable_weight = np.sum(reachable * weight_matrix, axis=0, dtype=np.float64)
    result: dict[str, np.ndarray] = {
        "population_weight": np.full(best.shape[1], total, dtype=float),
        "reachable_population_weight": reachable_weight.astype(float),
        "reachable_population_share": (reachable_weight / total).astype(float),
        "unreachable_population_share": (1.0 - reachable_weight / total).astype(float),
    }
    for threshold in THRESHOLDS:
        inside_weight = np.sum(
            (reachable & (best <= threshold)) * weight_matrix,
            axis=0,
            dtype=np.float64,
        )
        result[f"share_le_{threshold:g}_min"] = (inside_weight / total).astype(float)
    safe = np.where(reachable, best, 0.0).astype(np.float64, copy=False)
    weighted_sum = np.sum(safe * weight_matrix, axis=0, dtype=np.float64)
    mean = np.full(best.shape[1], np.nan, dtype=float)
    positive = reachable_weight > 0
    mean[positive] = weighted_sum[positive] / reachable_weight[positive]
    result["reachable_weighted_mean_walk_min"] = mean
    if include_quantiles:
        order = np.argsort(best, axis=0, kind="stable")
        sorted_values = np.take_along_axis(best, order, axis=0)
        sorted_weights = weights[order]
        cumulative = np.cumsum(sorted_weights, axis=0, dtype=np.float64)
        columns = np.arange(best.shape[1])
        for quantile, name in (
            (0.50, "reachable_weighted_median_walk_min"),
            (0.90, "reachable_weighted_p90_walk_min"),
            (0.95, "reachable_weighted_p95_walk_min"),
        ):
            target = quantile * reachable_weight
            hits = cumulative >= target[None, :]
            positions = np.argmax(hits, axis=0)
            values = sorted_values[positions, columns].astype(float)
            values[~positive] = np.nan
            result[name] = values
    return result


def evaluate_unique_stop_sets(
    unique_stop_sets: pd.DataFrame,
    substrate: WalkSubstrate,
    *,
    batch_size: int = 256,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if batch_size <= 0:
        raise RT029V4ContractError("batch_size must be positive")
    meta = substrate.population_meta
    weights = meta["population_weight_2025"].to_numpy(dtype=float)
    scopes = meta["population_scope"].astype(str).to_numpy()
    municipality_codes = meta["population_municipality_code"].astype(str).to_numpy()
    municipality_names = meta["population_municipality_name"].astype(str).to_numpy()
    scope_masks = {
        "ALL": np.ones(len(meta), dtype=bool),
        "CORE": scopes == "core",
        "EXTERNAL": scopes == "external",
    }
    core_codes = tuple(sorted(set(municipality_codes[scopes == "core"])))
    municipality_masks = {
        code: (scopes == "core") & (municipality_codes == code)
        for code in core_codes
    }
    municipality_labels: dict[str, str] = {}
    for code in core_codes:
        labels = sorted(set(municipality_names[municipality_codes == code]))
        if len(labels) != 1:
            raise RT029V4ContractError(f"municipality code {code} has ambiguous display labels")
        municipality_labels[code] = labels[0]

    stop_index = substrate.stop_index
    stop_count = len(substrate.conventional_stop_ids)
    access_rows: list[dict[str, object]] = []
    municipality_rows: list[dict[str, object]] = []

    records = list(unique_stop_sets.itertuples(index=False))
    for offset in range(0, len(records), batch_size):
        batch = records[offset: offset + batch_size]
        membership = np.zeros((len(batch), stop_count), dtype=bool)
        for column, row in enumerate(batch):
            stop_ids = _split_unique_ids(row.ordered_stop_place_ids, f"{row.stop_set_id} stops")
            missing = sorted(set(stop_ids) - set(stop_index))
            if missing:
                raise RT029V4ContractError(
                    f"{row.stop_set_id} contains stops outside conventional RT-028 matrix: {missing}"
                )
            for stop_id in stop_ids:
                membership[column, stop_index[stop_id]] = True

        best = np.full((len(meta), len(batch)), np.inf, dtype=np.float32)
        for stop_position in range(stop_count):
            columns = np.flatnonzero(membership[:, stop_position])
            if len(columns) == 0:
                continue
            best[:, columns] = np.minimum(
                best[:, columns],
                substrate.walk_time_matrix[:, stop_position, None],
            )

        for scope, mask in scope_masks.items():
            if not mask.any():
                continue
            metrics = _batch_access_metrics(
                best[mask, :], weights[mask], include_quantiles=True
            )
            for column, row in enumerate(batch):
                access_rows.append(
                    {
                        "stop_set_id": str(row.stop_set_id),
                        "scope": scope,
                        **{name: float(values[column]) for name, values in metrics.items()},
                    }
                )

        for municipality_code, mask in municipality_masks.items():
            if not mask.any():
                raise RT029V4ContractError(
                    f"core municipality {municipality_code} has no population units"
                )
            metrics = _batch_access_metrics(
                best[mask, :], weights[mask], include_quantiles=False
            )
            for column, row in enumerate(batch):
                municipality_rows.append(
                    {
                        "stop_set_id": str(row.stop_set_id),
                        "municipality_code": municipality_code,
                        "municipality": municipality_labels[municipality_code],
                        **{name: float(values[column]) for name, values in metrics.items()},
                    }
                )

    access = pd.DataFrame(access_rows).sort_values(
        ["stop_set_id", "scope"], kind="mergesort"
    ).reset_index(drop=True)
    municipality = pd.DataFrame(municipality_rows).sort_values(
        ["stop_set_id", "municipality_code"], kind="mergesort"
    ).reset_index(drop=True)
    equity_rows: list[dict[str, object]] = []
    for stop_set_id, group in municipality.groupby("stop_set_id", sort=True):
        for threshold in THRESHOLDS:
            column = f"share_le_{threshold:g}_min"
            values = pd.to_numeric(group[column]).to_numpy(dtype=float)
            equity_rows.append(
                {
                    "stop_set_id": str(stop_set_id),
                    "threshold_min": threshold,
                    "minimum_core_municipality_share": float(values.min()),
                    "maximum_core_municipality_share": float(values.max()),
                    "core_municipality_share_gap": float(values.max() - values.min()),
                    "core_municipality_count": int(len(values)),
                }
            )
    equity = pd.DataFrame(equity_rows).sort_values(
        ["stop_set_id", "threshold_min"], kind="mergesort"
    ).reset_index(drop=True)
    return access, municipality, equity
