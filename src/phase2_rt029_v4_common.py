from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

CONTRACT = "RT029_E456_CANDIDATE_ACCESSIBILITY_PARETO_V4"
READINESS_CONTRACT = "RT029_E456_READINESS_WAITING_PASSENGER_STOP_REALIZATION_V4"
STRUCTURE_CONTRACT = "ABSTRACT_NETWORK_STRUCTURES_NOT_TERRITORIAL_RECOMMENDATIONS"
DECISION_SCENARIO = "GUARANTEED_PASSENGER_STOPS"
SCENARIOS = ("VERTEX_ONLY_DIAGNOSTIC", DECISION_SCENARIO, "POSSIBLE_PASSENGER_STOPS")
THRESHOLDS = (5.0, 8.0, 10.0, 12.0)
DIRECTIONS = ("A_TO_B", "B_TO_A")
CONVENTIONAL_CLASS = "CONVENTIONAL_TPL"
SPECIAL_CLASS = "SPECIAL_SERVICE"
EXPECTED_LAYER_COUNTS = {4: 88, 5: 4076, 6: 108679}
EXPECTED_TOTAL_STRUCTURES = sum(EXPECTED_LAYER_COUNTS.values())


class RT029V4ContractError(ValueError):
    """Fail-closed RT-029 E4+E5+E6 contract violation."""


@dataclass(frozen=True)
class WalkSubstrate:
    population_meta: pd.DataFrame
    conventional_stop_ids: tuple[str, ...]
    stop_index: Mapping[str, int]
    walk_time_matrix: np.ndarray
    service_map: Mapping[str, str]
    display_label_normalization_count: int


@dataclass(frozen=True)
class RT029V4Result:
    structure_stop_sets: pd.DataFrame
    unique_stop_sets: pd.DataFrame
    stop_set_accessibility: pd.DataFrame
    stop_set_municipality_accessibility: pd.DataFrame
    stop_set_equity: pd.DataFrame
    operating_envelope: pd.DataFrame
    candidate_decision_metrics: pd.DataFrame
    pareto_frontiers: pd.DataFrame
    pareto_shortlist: pd.DataFrame
    audit: dict[str, object]


def _required(df: pd.DataFrame, columns: Iterable[str], label: str) -> None:
    missing = sorted(set(columns) - set(df.columns))
    if missing:
        raise RT029V4ContractError(f"{label} missing required columns: {missing}")


def _text(value: object, label: str) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        raise RT029V4ContractError(f"{label} must be non-null")
    text = str(value).strip()
    if not text:
        raise RT029V4ContractError(f"{label} must be non-empty")
    return text


def _split_unique_ids(value: object, label: str) -> tuple[str, ...]:
    values = tuple(part.strip() for part in _text(value, label).split(";") if part.strip())
    if not values or len(values) != len(set(values)):
        raise RT029V4ContractError(
            f"{label} must contain unique non-empty semicolon-separated IDs"
        )
    return values


def _ordered_stop_ids(value: object, label: str) -> tuple[str, ...]:
    values = tuple(part.strip() for part in _text(value, label).split(";") if part.strip())
    if not values:
        raise RT029V4ContractError(f"{label} must contain at least one stop")
    if len(values) != len(set(values)):
        raise RT029V4ContractError(f"{label} contains a repeated passenger stop")
    return values


def _canonical_stop_string(stops: Iterable[str]) -> str:
    values = tuple(sorted(set(str(stop) for stop in stops)))
    if not values:
        raise RT029V4ContractError("candidate stop set cannot be empty")
    return ";".join(values)


def _stop_set_id(stop_string: str) -> str:
    digest = hashlib.sha256(stop_string.encode("utf-8")).hexdigest()[:20].upper()
    return f"RT029_STOPSET_{digest}"


def _canonical_sha256(df: pd.DataFrame, sort_cols: Sequence[str]) -> str:
    stable = df.sort_values(list(sort_cols), kind="mergesort").reset_index(drop=True)
    payload = stable.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _normalize_display_text(value: object) -> tuple[str, bool]:
    text = _text(value, "display text")
    suspicious = ("Ã", "Â", "â€", "ðŸ")
    if not any(token in text for token in suspicious):
        return text, False
    try:
        repaired = text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text, False
    before = sum(text.count(token) for token in suspicious)
    after = sum(repaired.count(token) for token in suspicious)
    if after < before:
        return repaired, True
    return text, False


def _assert_no_common_mojibake(df: pd.DataFrame, label: str) -> None:
    suspicious = ("Ã", "Â", "â€", "ðŸ")
    for column in df.select_dtypes(include=["object", "string"]).columns:
        series = df[column].dropna().astype(str)
        bad = series[series.map(lambda value: any(token in value for token in suspicious))]
        if not bad.empty:
            sample = bad.iloc[0]
            raise RT029V4ContractError(
                f"{label} contains probable mojibake in {column}: {sample!r}"
            )


def validate_structure_layers(
    layers: Mapping[int, pd.DataFrame],
    expected_layer_counts: Mapping[int, int] | None = EXPECTED_LAYER_COUNTS,
) -> pd.DataFrame:
    expected_edges = tuple(sorted((expected_layer_counts or layers).keys()))
    if set(layers) != set(expected_edges):
        raise RT029V4ContractError(
            f"structure layers must be exactly {list(expected_edges)}, got {sorted(layers)}"
        )
    frames: list[pd.DataFrame] = []
    for edge_count in expected_edges:
        source = layers[edge_count]
        _required(
            source,
            (
                "structure_id", "link_ids", "vertex_ids", "topology_class",
                "vertex_count", "edge_count", "cycle_rank", "contract",
            ),
            f"E{edge_count} structures",
        )
        frame = source.copy()
        if expected_layer_counts is not None:
            expected = int(expected_layer_counts[edge_count])
            if len(frame) != expected:
                raise RT029V4ContractError(
                    f"E{edge_count} expected exactly {expected} structures, got {len(frame)}"
                )
        if frame["structure_id"].astype(str).duplicated().any():
            raise RT029V4ContractError(f"duplicate structure_id within E{edge_count}")
        for row in frame.itertuples(index=False):
            sid = _text(row.structure_id, "structure_id")
            links = _split_unique_ids(row.link_ids, f"{sid} link_ids")
            vertices = _split_unique_ids(row.vertex_ids, f"{sid} vertex_ids")
            e = int(row.edge_count)
            v = int(row.vertex_count)
            rank = int(row.cycle_rank)
            if e != edge_count or len(links) != edge_count:
                raise RT029V4ContractError(f"{sid} does not belong to exact E{edge_count} layer")
            if len(vertices) != v:
                raise RT029V4ContractError(f"{sid} vertex_ids count disagrees with vertex_count")
            if rank != e - v + 1 or rank < 0:
                raise RT029V4ContractError(f"{sid} violates connected cycle-rank identity E-V+1")
            if _text(row.contract, f"{sid} contract") != STRUCTURE_CONTRACT:
                raise RT029V4ContractError(f"{sid} has unexpected structure contract")
        frame["structural_layer"] = f"E{edge_count}"
        frames.append(frame)
    structures = pd.concat(frames, ignore_index=True)
    if structures["structure_id"].astype(str).duplicated().any():
        raise RT029V4ContractError("structure IDs are not disjoint across E4/E5/E6")
    _assert_no_common_mojibake(structures, "structure layers")
    return structures.sort_values("structure_id", kind="mergesort").reset_index(drop=True)


def validate_rt023_realizations(
    realizations: pd.DataFrame,
    required_links: set[str],
) -> pd.DataFrame:
    _required(
        realizations,
        (
            "realization_id", "structural_link_id", "direction", "alternative_ordinal",
            "source_stop_place_id", "target_stop_place_id",
            "ordered_passenger_stop_place_ids", "distance_m", "running_minutes_model",
        ),
        "RT-023 realization catalog",
    )
    r = realizations.copy()
    if r["realization_id"].astype(str).duplicated().any():
        raise RT029V4ContractError("duplicate RT-023 realization_id")
    if r[["structural_link_id", "direction", "alternative_ordinal"]].astype(str).duplicated().any():
        raise RT029V4ContractError("duplicate RT-023 link-direction alternative ordinal")
    r["distance_m"] = pd.to_numeric(r["distance_m"], errors="coerce")
    r["running_minutes_model"] = pd.to_numeric(r["running_minutes_model"], errors="coerce")
    if r[["distance_m", "running_minutes_model"]].isna().any().any():
        raise RT029V4ContractError("RT-023 burden values must be numeric")
    if (r[["distance_m", "running_minutes_model"]] < 0).any().any():
        raise RT029V4ContractError("RT-023 burden values must be non-negative")
    missing_links = sorted(required_links - set(r["structural_link_id"].astype(str)))
    if missing_links:
        raise RT029V4ContractError(f"RT-023 is missing required structural links: {missing_links[:10]}")
    for link_id in sorted(required_links):
        subset = r[r["structural_link_id"].astype(str) == link_id]
        if set(subset["direction"].astype(str)) != set(DIRECTIONS):
            raise RT029V4ContractError(f"{link_id} must expose both A_TO_B and B_TO_A")
    extra_directions = sorted(set(r["direction"].astype(str)) - set(DIRECTIONS))
    if extra_directions:
        raise RT029V4ContractError(f"unexpected RT-023 directions: {extra_directions}")
    _assert_no_common_mojibake(r, "RT-023 realization catalog")
    return r.sort_values(
        ["structural_link_id", "direction", "alternative_ordinal"], kind="mergesort"
    ).reset_index(drop=True)
