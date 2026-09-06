from __future__ import annotations

from typing import Mapping

import numpy as np
import pandas as pd

from phase2_rt029_v4_common import (
    CONVENTIONAL_CLASS, DECISION_SCENARIO, DIRECTIONS, SPECIAL_CLASS, RT029V4ContractError, WalkSubstrate,
    _assert_no_common_mojibake, _canonical_stop_string, _ordered_stop_ids, _required,
    _split_unique_ids, _stop_set_id, _text, _normalize_display_text,
)

def validate_walk_matrix(
    walk: pd.DataFrame,
    expected_population_units: int | None = 10230,
    expected_stop_count: int | None = 36,
) -> WalkSubstrate:
    _required(
        walk,
        (
            "population_unit_id", "population_weight_2025", "population_scope",
            "population_municipality_code", "population_municipality_name",
            "stop_place_id", "stop_service_class",
            "walk_time_min", "reachability_status",
        ),
        "RT-028 walk matrix",
    )
    w = walk.copy()
    if w[["population_unit_id", "stop_place_id"]].astype(str).duplicated().any():
        raise RT029V4ContractError("duplicate RT-028 population-stop pair")
    if not w["reachability_status"].astype(str).isin({"REACHABLE", "UNREACHABLE"}).all():
        raise RT029V4ContractError("unexpected RT-028 reachability status")
    w["population_weight_2025"] = pd.to_numeric(w["population_weight_2025"], errors="coerce")
    if w["population_weight_2025"].isna().any() or (w["population_weight_2025"] < 0).any():
        raise RT029V4ContractError("population weights must be finite and non-negative")

    service = w[["stop_place_id", "stop_service_class"]].astype(str).drop_duplicates()
    if service["stop_place_id"].duplicated().any():
        raise RT029V4ContractError("stop service class drifts across RT-028 rows")
    service_map = dict(zip(service["stop_place_id"], service["stop_service_class"]))
    if expected_stop_count is not None and len(service_map) != int(expected_stop_count):
        raise RT029V4ContractError(
            f"RT-028 expected {expected_stop_count} stops, got {len(service_map)}"
        )
    if sum(v == CONVENTIONAL_CLASS for v in service_map.values()) != 35:
        raise RT029V4ContractError("RT-028 must contain exactly 35 conventional stops")
    if sum(v == SPECIAL_CLASS for v in service_map.values()) != 1:
        raise RT029V4ContractError("RT-028 must contain exactly one SPECIAL_SERVICE stop")

    meta_cols = [
        "population_unit_id", "population_weight_2025",
        "population_scope", "population_municipality_code", "population_municipality_name",
    ]
    meta = w[meta_cols].drop_duplicates()
    if meta["population_unit_id"].astype(str).duplicated().any():
        raise RT029V4ContractError("population metadata drifts across stop rows")
    if expected_population_units is not None and len(meta) != int(expected_population_units):
        raise RT029V4ContractError(
            f"RT-028 expected {expected_population_units} population units, got {len(meta)}"
        )
    if not set(meta["population_scope"].astype(str)).issubset({"core", "external"}):
        raise RT029V4ContractError("unexpected population_scope")
    meta["population_municipality_code"] = meta["population_municipality_code"].astype(str)
    raw_name_counts = meta.groupby("population_municipality_code")["population_municipality_name"].nunique()
    if (raw_name_counts != 1).any():
        raise RT029V4ContractError("municipality code maps to multiple raw population labels")
    normalized = meta["population_municipality_name"].map(_normalize_display_text)
    meta["population_municipality_name"] = normalized.map(lambda pair: pair[0])
    display_label_normalization_count = int(normalized.map(lambda pair: pair[1]).sum())
    normalized_name_counts = meta.groupby("population_municipality_code")["population_municipality_name"].nunique()
    if (normalized_name_counts != 1).any():
        raise RT029V4ContractError("municipality code maps to multiple normalized display labels")
    _assert_no_common_mojibake(meta, "normalized population municipality labels")
    if float(meta["population_weight_2025"].sum()) <= 0:
        raise RT029V4ContractError("population universe has zero total weight")

    if len(w) != len(meta) * len(service_map):
        raise RT029V4ContractError("RT-028 matrix is not a complete population-unit × stop product")

    conventional_stop_ids = tuple(
        sorted(stop for stop, cls in service_map.items() if cls == CONVENTIONAL_CLASS)
    )
    stop_index = {stop: index for index, stop in enumerate(conventional_stop_ids)}
    meta = meta.copy()
    meta["population_unit_id"] = meta["population_unit_id"].astype(str)
    meta = meta.sort_values("population_unit_id", kind="mergesort").reset_index(drop=True)
    population_index = {
        population_id: index for index, population_id in enumerate(meta["population_unit_id"])
    }
    matrix = np.full(
        (len(meta), len(conventional_stop_ids)), np.inf, dtype=np.float32
    )
    reachable = w[
        (w["stop_place_id"].astype(str).isin(conventional_stop_ids))
        & (w["reachability_status"].astype(str) == "REACHABLE")
    ].copy()
    reachable["walk_time_min"] = pd.to_numeric(reachable["walk_time_min"], errors="coerce")
    if reachable["walk_time_min"].isna().any() or (reachable["walk_time_min"] < 0).any():
        raise RT029V4ContractError("reachable RT-028 rows need finite non-negative walk time")
    pop_pos = reachable["population_unit_id"].astype(str).map(population_index)
    stop_pos = reachable["stop_place_id"].astype(str).map(stop_index)
    if pop_pos.isna().any() or stop_pos.isna().any():
        raise RT029V4ContractError("RT-028 matrix indexing failed")
    matrix[pop_pos.to_numpy(dtype=int), stop_pos.to_numpy(dtype=int)] = (
        reachable["walk_time_min"].to_numpy(dtype=np.float32)
    )
    return WalkSubstrate(
        population_meta=meta,
        conventional_stop_ids=conventional_stop_ids,
        stop_index=stop_index,
        walk_time_matrix=matrix,
        service_map=service_map,
        display_label_normalization_count=display_label_normalization_count,
    )


def normalize_passenger_patterns(
    passenger_patterns: pd.DataFrame,
    rt023_realizations: pd.DataFrame,
) -> pd.DataFrame:
    patterns = passenger_patterns.copy()
    if "ordered_passenger_stop_ids" in patterns.columns and "ordered_passenger_stop_place_ids" not in patterns.columns:
        patterns = patterns.rename(
            columns={"ordered_passenger_stop_ids": "ordered_passenger_stop_place_ids"}
        )
    _required(
        patterns,
        (
            "realization_id", "structural_link_id", "direction", "alternative_ordinal",
            "ordered_passenger_stop_place_ids",
        ),
        "passenger-stop realization artifact",
    )
    if patterns["realization_id"].astype(str).duplicated().any():
        raise RT029V4ContractError("passenger-stop artifact must contain one row per realization_id")
    keys = ["realization_id", "structural_link_id", "direction", "alternative_ordinal"]
    expected = rt023_realizations[
        keys + ["source_stop_place_id", "target_stop_place_id"]
    ].copy()

    payload_cols = keys + ["ordered_passenger_stop_place_ids"]
    if "passenger_stop_count" in patterns.columns:
        payload_cols.append("passenger_stop_count")
    pattern_payload = patterns[payload_cols].copy()

    merged = expected.merge(
        pattern_payload,
        on=keys,
        how="outer",
        indicator=True,
        validate="one_to_one",
    )
    if not (merged["_merge"] == "both").all():
        missing = merged.loc[merged["_merge"] == "left_only", "realization_id"].astype(str).tolist()[:10]
        extra = merged.loc[merged["_merge"] == "right_only", "realization_id"].astype(str).tolist()[:10]
        raise RT029V4ContractError(
            f"passenger-stop artifact does not exactly match RT-023 realizations; missing={missing}, extra={extra}"
        )
    merged = merged.drop(columns=["_merge"])
    for row in merged.itertuples(index=False):
        rid = str(row.realization_id)
        stops = _ordered_stop_ids(
            row.ordered_passenger_stop_place_ids, f"{rid} ordered passenger stops"
        )
        if stops[0] != str(row.source_stop_place_id) or stops[-1] != str(row.target_stop_place_id):
            raise RT029V4ContractError(
                f"{rid} passenger pattern must preserve certified source and target endpoints"
            )
        if hasattr(row, "passenger_stop_count"):
            count = getattr(row, "passenger_stop_count")
            if not pd.isna(count) and int(count) != len(stops):
                raise RT029V4ContractError(f"{rid} passenger_stop_count disagrees with sequence")
    _assert_no_common_mojibake(merged, "passenger-stop realization artifact")
    return merged.sort_values(
        ["structural_link_id", "direction", "alternative_ordinal"], kind="mergesort"
    ).reset_index(drop=True)


def _component_stop_sets(patterns: pd.DataFrame) -> dict[tuple[str, str], tuple[frozenset[str], frozenset[str]]]:
    result: dict[tuple[str, str], tuple[frozenset[str], frozenset[str]]] = {}
    for (link_id, direction), group in patterns.groupby(
        ["structural_link_id", "direction"], sort=True
    ):
        alternatives = [
            set(_ordered_stop_ids(value, f"{link_id} {direction} passenger stops"))
            for value in group["ordered_passenger_stop_place_ids"]
        ]
        if not alternatives:
            raise RT029V4ContractError(f"{link_id} {direction} has no passenger-stop realization")
        guaranteed = set.intersection(*alternatives)
        possible = set.union(*alternatives)
        if not guaranteed:
            raise RT029V4ContractError(f"{link_id} {direction} has empty guaranteed passenger stop set")
        result[(str(link_id), str(direction))] = (frozenset(guaranteed), frozenset(possible))
    return result


def derive_structure_stop_sets(
    structures: pd.DataFrame,
    passenger_patterns: pd.DataFrame,
    service_map: Mapping[str, str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    components = _component_stop_sets(passenger_patterns)
    rows: list[dict[str, object]] = []
    for srow in structures.itertuples(index=False):
        sid = str(srow.structure_id)
        links = _split_unique_ids(srow.link_ids, f"{sid} link_ids")
        vertices = set(_split_unique_ids(srow.vertex_ids, f"{sid} vertex_ids"))
        guaranteed: set[str] = set()
        possible: set[str] = set()
        for link_id in links:
            for direction in DIRECTIONS:
                key = (link_id, direction)
                if key not in components:
                    raise RT029V4ContractError(f"missing passenger-stop component {key}")
                guaranteed_component, possible_component = components[key]
                guaranteed.update(guaranteed_component)
                possible.update(possible_component)
        if not vertices.issubset(guaranteed):
            missing = sorted(vertices - guaranteed)
            raise RT029V4ContractError(
                f"{sid} structural endpoints are not guaranteed by passenger patterns: {missing}"
            )
        if not guaranteed.issubset(possible):
            raise RT029V4ContractError(f"{sid} guaranteed stop set is not subset of possible set")
        for stop in sorted(possible | vertices):
            if stop not in service_map:
                raise RT029V4ContractError(f"{sid} references stop absent from RT-028: {stop}")
            if service_map[stop] != CONVENTIONAL_CLASS:
                raise RT029V4ContractError(
                    f"{sid} passenger stop set contains non-conventional stop: {stop}"
                )
        scenario_sets = {
            "VERTEX_ONLY_DIAGNOSTIC": vertices,
            DECISION_SCENARIO: guaranteed,
            "POSSIBLE_PASSENGER_STOPS": possible,
        }
        for scenario, stops in scenario_sets.items():
            stop_string = _canonical_stop_string(stops)
            rows.append(
                {
                    "structure_id": sid,
                    "structural_layer": str(srow.structural_layer),
                    "edge_count": int(srow.edge_count),
                    "topology_class": str(srow.topology_class),
                    "scenario": scenario,
                    "stop_set_id": _stop_set_id(stop_string),
                    "stop_count": len(set(stops)),
                    "ordered_stop_place_ids": stop_string,
                    "decision_eligible": scenario == DECISION_SCENARIO,
                }
            )
    mapping = pd.DataFrame(rows).sort_values(
        ["structure_id", "scenario"], kind="mergesort"
    ).reset_index(drop=True)
    collision = mapping.groupby("stop_set_id")["ordered_stop_place_ids"].nunique()
    if (collision > 1).any():
        raise RT029V4ContractError("stop_set_id hash collision detected")
    unique = (
        mapping[["stop_set_id", "stop_count", "ordered_stop_place_ids"]]
        .drop_duplicates()
        .sort_values("stop_set_id", kind="mergesort")
        .reset_index(drop=True)
    )
    return mapping, unique
