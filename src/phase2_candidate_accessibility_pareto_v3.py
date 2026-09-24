from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import pandas as pd

CONTRACT = "RT029_88_CANDIDATE_ACCESSIBILITY_PARETO_V3"
STRUCTURE_CONTRACT = "ABSTRACT_NETWORK_STRUCTURES_NOT_TERRITORIAL_RECOMMENDATIONS"
DECISION_SCENARIO = "GUARANTEED_RT023"
SCENARIOS = ("VERTEX_ONLY", DECISION_SCENARIO, "POSSIBLE_RT023")
THRESHOLDS = (5.0, 8.0, 10.0, 12.0)
DIRECTIONS = ("A_TO_B", "B_TO_A")
CONVENTIONAL_CLASS = "CONVENTIONAL_TPL"
SPECIAL_CLASS = "SPECIAL_SERVICE"


class RT029ContractError(ValueError):
    """Fail-closed RT-029 contract violation."""


def _dominates(
    candidate_a: Mapping[str, object],
    candidate_b: Mapping[str, object],
    dimensions: Mapping[str, str],
) -> bool:
    no_worse_everywhere = True
    strictly_better_somewhere = False
    for name, direction in sorted(dimensions.items()):
        if direction not in {"min", "max"}:
            raise RT029ContractError("Pareto direction must be min or max")
        a = float(candidate_a[name])
        b = float(candidate_b[name])
        if not math.isfinite(a) or not math.isfinite(b):
            raise RT029ContractError(f"non-finite Pareto metric {name}")
        if direction == "min":
            no_worse = a <= b
            strict = a < b
        else:
            no_worse = a >= b
            strict = a > b
        no_worse_everywhere = no_worse_everywhere and no_worse
        strictly_better_somewhere = strictly_better_somewhere or strict
    return no_worse_everywhere and strictly_better_somewhere


def _pareto_front(
    candidates: Sequence[Mapping[str, object]],
    dimensions: Mapping[str, str],
) -> tuple[str, ...]:
    ids = [str(row.get("candidate_id", "")) for row in candidates]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise RT029ContractError("Pareto candidate IDs must be unique and non-empty")
    frontier = []
    for i, candidate in enumerate(candidates):
        if not any(
            _dominates(other, candidate, dimensions)
            for j, other in enumerate(candidates)
            if i != j
        ):
            frontier.append(str(candidate["candidate_id"]))
    return tuple(sorted(frontier))


@dataclass(frozen=True)
class RT029Result:
    stop_sets: pd.DataFrame
    accessibility_summary: pd.DataFrame
    municipality_accessibility: pd.DataFrame
    equity_summary: pd.DataFrame
    operating_envelope: pd.DataFrame
    pareto_frontiers: pd.DataFrame
    pareto_shortlist: pd.DataFrame
    audit: dict[str, object]


def _required(df: pd.DataFrame, columns: Iterable[str], label: str) -> None:
    missing = sorted(set(columns) - set(df.columns))
    if missing:
        raise RT029ContractError(f"{label} missing required columns: {missing}")


def _text(value: object, label: str) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        raise RT029ContractError(f"{label} must be non-null")
    text = str(value).strip()
    if not text:
        raise RT029ContractError(f"{label} must be non-empty")
    return text


def _split_ids(value: object, label: str) -> tuple[str, ...]:
    values = tuple(part.strip() for part in _text(value, label).split(";") if part.strip())
    if not values or len(values) != len(set(values)):
        raise RT029ContractError(f"{label} must contain unique non-empty semicolon-separated IDs")
    return values


def _canonical_sha256(df: pd.DataFrame, sort_cols: Sequence[str]) -> str:
    stable = df.sort_values(list(sort_cols), kind="mergesort").reset_index(drop=True)
    payload = stable.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _weighted_quantile(values: pd.Series, weights: pd.Series, quantile: float) -> float:
    if len(values) == 0:
        return math.nan
    frame = pd.DataFrame({"value": pd.to_numeric(values), "weight": pd.to_numeric(weights)})
    frame = frame.sort_values("value", kind="mergesort").reset_index(drop=True)
    total = float(frame["weight"].sum())
    if not math.isfinite(total) or total <= 0:
        return math.nan
    target = quantile * total
    cumulative = frame["weight"].cumsum()
    return float(frame.loc[cumulative >= target, "value"].iloc[0])


def _validate_structures(structures: pd.DataFrame, expected_structure_count: int | None) -> pd.DataFrame:
    _required(
        structures,
        (
            "structure_id", "link_ids", "vertex_ids", "topology_class",
            "vertex_count", "edge_count", "cycle_rank", "contract",
        ),
        "structures",
    )
    s = structures.copy()
    if s["structure_id"].astype(str).duplicated().any():
        raise RT029ContractError("duplicate structure_id")
    if expected_structure_count is not None and len(s) != int(expected_structure_count):
        raise RT029ContractError(
            f"expected exactly {expected_structure_count} structures, got {len(s)}"
        )
    for row in s.itertuples(index=False):
        sid = _text(row.structure_id, "structure_id")
        if _text(row.contract, f"{sid} contract") != STRUCTURE_CONTRACT:
            raise RT029ContractError(f"{sid} has unexpected structure contract")
        links = _split_ids(row.link_ids, f"{sid} link_ids")
        vertices = _split_ids(row.vertex_ids, f"{sid} vertex_ids")
        if len(links) != 4 or len(vertices) != 5:
            raise RT029ContractError(f"{sid} must contain exactly 4 links and 5 vertices")
        if int(row.vertex_count) != 5 or int(row.edge_count) != 4 or int(row.cycle_rank) != 0:
            raise RT029ContractError(f"{sid} is not a certified 5-vertex/4-edge tree")
    return s.sort_values("structure_id", kind="mergesort").reset_index(drop=True)


def _validate_manifest(structures: pd.DataFrame, manifest: pd.DataFrame) -> pd.DataFrame:
    _required(
        manifest,
        ("structure_id", "structure_link_ordinal", "structural_link_id"),
        "structure_link_manifest",
    )
    m = manifest.copy()
    if m[["structure_id", "structural_link_id"]].astype(str).duplicated().any():
        raise RT029ContractError("duplicate structure-link reference")
    expected: set[tuple[str, str]] = set()
    for row in structures.itertuples(index=False):
        for link_id in _split_ids(row.link_ids, f"{row.structure_id} link_ids"):
            expected.add((str(row.structure_id), link_id))
    got = set(
        zip(m["structure_id"].astype(str), m["structural_link_id"].astype(str))
    )
    if got != expected:
        missing = sorted(expected - got)[:10]
        extra = sorted(got - expected)[:10]
        raise RT029ContractError(
            f"RT-023 structure-link manifest mismatch; missing={missing}, extra={extra}"
        )
    return m.sort_values(
        ["structure_id", "structure_link_ordinal", "structural_link_id"], kind="mergesort"
    ).reset_index(drop=True)


def _validate_realizations(realizations: pd.DataFrame, required_links: set[str]) -> pd.DataFrame:
    _required(
        realizations,
        (
            "structural_link_id", "direction", "alternative_ordinal",
            "ordered_passenger_stop_place_ids", "distance_m", "running_minutes_model",
        ),
        "realization_catalog",
    )
    r = realizations.copy()
    if r[["structural_link_id", "direction", "alternative_ordinal"]].astype(str).duplicated().any():
        raise RT029ContractError("duplicate RT-023 link-direction alternative ordinal")
    r["distance_m"] = pd.to_numeric(r["distance_m"], errors="coerce")
    r["running_minutes_model"] = pd.to_numeric(r["running_minutes_model"], errors="coerce")
    if r[["distance_m", "running_minutes_model"]].isna().any().any():
        raise RT029ContractError("RT-023 realization burden values must be numeric")
    if (r[["distance_m", "running_minutes_model"]] < 0).any().any():
        raise RT029ContractError("RT-023 realization burden values must be non-negative")
    for link_id in sorted(required_links):
        subset = r[r["structural_link_id"].astype(str) == link_id]
        if set(subset["direction"].astype(str)) != set(DIRECTIONS):
            raise RT029ContractError(f"{link_id} must expose both A_TO_B and B_TO_A")
        for direction in DIRECTIONS:
            comp = subset[subset["direction"].astype(str) == direction]
            if comp.empty:
                raise RT029ContractError(f"{link_id} {direction} has no realization")
            for value in comp["ordered_passenger_stop_place_ids"]:
                if len(_split_ids(value, f"{link_id} {direction} stop sequence")) < 2:
                    raise RT029ContractError(f"{link_id} {direction} realization has <2 stops")
    extra_dirs = sorted(set(r["direction"].astype(str)) - set(DIRECTIONS))
    if extra_dirs:
        raise RT029ContractError(f"unexpected RT-023 directions: {extra_dirs}")
    return r.sort_values(
        ["structural_link_id", "direction", "alternative_ordinal"], kind="mergesort"
    ).reset_index(drop=True)


def _validate_walk_matrix(walk: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, str]]:
    _required(
        walk,
        (
            "population_unit_id", "population_weight_2025", "population_scope",
            "population_municipality_name", "stop_place_id", "stop_service_class",
            "walk_time_min", "reachability_status",
        ),
        "RT-028 walk matrix",
    )
    w = walk.copy()
    if w[["population_unit_id", "stop_place_id"]].astype(str).duplicated().any():
        raise RT029ContractError("duplicate RT-028 population-stop pair")
    if not w["reachability_status"].astype(str).isin({"REACHABLE", "UNREACHABLE"}).all():
        raise RT029ContractError("unexpected RT-028 reachability status")
    w["population_weight_2025"] = pd.to_numeric(w["population_weight_2025"], errors="coerce")
    if w["population_weight_2025"].isna().any() or (w["population_weight_2025"] < 0).any():
        raise RT029ContractError("population weights must be finite and non-negative")

    service = w[["stop_place_id", "stop_service_class"]].astype(str).drop_duplicates()
    if service["stop_place_id"].duplicated().any():
        raise RT029ContractError("stop service class drifts across RT-028 matrix")
    service_map = dict(zip(service["stop_place_id"], service["stop_service_class"]))
    if sum(v == CONVENTIONAL_CLASS for v in service_map.values()) != 35:
        raise RT029ContractError("RT-028 matrix must contain exactly 35 conventional stops")
    if sum(v == SPECIAL_CLASS for v in service_map.values()) != 1 or len(service_map) != 36:
        raise RT029ContractError("RT-028 matrix must preserve exact frozen 35+1 stop universe")

    meta_cols = (
        "population_unit_id", "population_weight_2025",
        "population_scope", "population_municipality_name",
    )
    meta = w[list(meta_cols)].drop_duplicates()
    if meta["population_unit_id"].astype(str).duplicated().any():
        raise RT029ContractError("population metadata drifts across RT-028 stop rows")
    if not set(meta["population_scope"].astype(str)).issubset({"core", "external"}):
        raise RT029ContractError("unexpected population_scope")
    if float(meta["population_weight_2025"].sum()) <= 0:
        raise RT029ContractError("population universe has zero total weight")

    reachable = w["reachability_status"].astype(str) == "REACHABLE"
    times = pd.to_numeric(w.loc[reachable, "walk_time_min"], errors="coerce")
    if times.isna().any() or (times < 0).any():
        raise RT029ContractError("reachable RT-028 rows need finite non-negative walk_time_min")
    w.loc[reachable, "walk_time_min"] = times
    return (
        w.sort_values(["population_unit_id", "stop_place_id"], kind="mergesort").reset_index(drop=True),
        meta.sort_values("population_unit_id", kind="mergesort").reset_index(drop=True),
        service_map,
    )


def _stop_set_rows(
    structures: pd.DataFrame,
    realizations: pd.DataFrame,
    service_map: Mapping[str, str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, object]] = []
    envelope_rows: list[dict[str, object]] = []
    for srow in structures.itertuples(index=False):
        sid = str(srow.structure_id)
        links = _split_ids(srow.link_ids, f"{sid} link_ids")
        vertices = set(_split_ids(srow.vertex_ids, f"{sid} vertex_ids"))
        guaranteed = set(vertices)
        possible = set(vertices)
        min_dist = max_dist = min_runtime = max_runtime = 0.0

        for link_id in links:
            link = realizations[realizations["structural_link_id"].astype(str) == link_id]
            for direction in DIRECTIONS:
                comp = link[link["direction"].astype(str) == direction]
                alternatives = [
                    set(_split_ids(v, f"{link_id} {direction} stops"))
                    for v in comp["ordered_passenger_stop_place_ids"]
                ]
                intersection = set.intersection(*alternatives)
                union = set.union(*alternatives)
                guaranteed.update(intersection)
                possible.update(union)
                min_dist += float(comp["distance_m"].min())
                max_dist += float(comp["distance_m"].max())
                min_runtime += float(comp["running_minutes_model"].min())
                max_runtime += float(comp["running_minutes_model"].max())

        unknown = sorted(possible - set(service_map))
        if unknown:
            raise RT029ContractError(f"{sid} references stops absent from RT-028: {unknown}")
        non_conventional = sorted(stop for stop in possible if service_map[stop] != CONVENTIONAL_CLASS)
        if non_conventional:
            raise RT029ContractError(
                f"{sid} automatic candidate stop set contains non-conventional stops: {non_conventional}"
            )
        if not vertices.issubset(guaranteed) or not guaranteed.issubset(possible):
            raise RT029ContractError(f"{sid} stop-set envelope is internally inconsistent")

        stop_sets = {
            "VERTEX_ONLY": vertices,
            DECISION_SCENARIO: guaranteed,
            "POSSIBLE_RT023": possible,
        }
        for scenario, stops in stop_sets.items():
            rows.append(
                {
                    "structure_id": sid,
                    "topology_class": str(srow.topology_class),
                    "scenario": scenario,
                    "stop_count": len(stops),
                    "ordered_stop_place_ids": ";".join(sorted(stops)),
                    "decision_eligible": scenario == DECISION_SCENARIO,
                }
            )
        envelope_rows.append(
            {
                "structure_id": sid,
                "topology_class": str(srow.topology_class),
                "vertex_stop_count": len(vertices),
                "guaranteed_stop_count": len(guaranteed),
                "possible_stop_count": len(possible),
                "optional_stop_count": len(possible - guaranteed),
                "minimum_bidirectional_link_distance_m": min_dist,
                "maximum_bidirectional_link_distance_m": max_dist,
                "minimum_bidirectional_link_running_minutes_model": min_runtime,
                "maximum_bidirectional_link_running_minutes_model": max_runtime,
            }
        )
    stop_sets_df = pd.DataFrame(rows).sort_values(
        ["structure_id", "scenario"], kind="mergesort"
    ).reset_index(drop=True)
    envelope_df = pd.DataFrame(envelope_rows).sort_values(
        "structure_id", kind="mergesort"
    ).reset_index(drop=True)
    return stop_sets_df, envelope_df


def _best_walk_for_stops(
    walk: pd.DataFrame,
    population_meta: pd.DataFrame,
    stops: set[str],
) -> pd.DataFrame:
    selected = walk[
        walk["stop_place_id"].astype(str).isin(stops)
        & (walk["reachability_status"].astype(str) == "REACHABLE")
    ].copy()
    if selected.empty:
        best = pd.DataFrame(columns=["population_unit_id", "best_walk_time_min"])
    else:
        selected["walk_time_min"] = pd.to_numeric(selected["walk_time_min"])
        best = (
            selected.groupby("population_unit_id", sort=False)["walk_time_min"]
            .min()
            .rename("best_walk_time_min")
            .reset_index()
        )
    units = population_meta.merge(best, on="population_unit_id", how="left", validate="one_to_one")
    units["candidate_reachable"] = units["best_walk_time_min"].notna()
    return units


def _summary_row(
    structure_id: str,
    topology_class: str,
    scenario: str,
    scope: str,
    units: pd.DataFrame,
) -> dict[str, object]:
    total = float(units["population_weight_2025"].sum())
    if total <= 0:
        raise RT029ContractError(f"{structure_id} {scenario} {scope} has zero population weight")
    reachable = units[units["candidate_reachable"]].copy()
    reachable_weight = float(reachable["population_weight_2025"].sum())
    result: dict[str, object] = {
        "structure_id": structure_id,
        "topology_class": topology_class,
        "scenario": scenario,
        "scope": scope,
        "population_weight": total,
        "reachable_population_weight": reachable_weight,
        "reachable_population_share": reachable_weight / total,
        "unreachable_population_share": 1.0 - reachable_weight / total,
    }
    for threshold in THRESHOLDS:
        inside = float(
            units.loc[
                units["candidate_reachable"]
                & (pd.to_numeric(units["best_walk_time_min"]) <= threshold),
                "population_weight_2025",
            ].sum()
        )
        result[f"share_le_{threshold:g}_min"] = inside / total
    if reachable_weight > 0:
        times = pd.to_numeric(reachable["best_walk_time_min"])
        weights = pd.to_numeric(reachable["population_weight_2025"])
        result["reachable_weighted_mean_walk_min"] = float((times * weights).sum() / reachable_weight)
        result["reachable_weighted_median_walk_min"] = _weighted_quantile(times, weights, 0.50)
        result["reachable_weighted_p90_walk_min"] = _weighted_quantile(times, weights, 0.90)
        result["reachable_weighted_p95_walk_min"] = _weighted_quantile(times, weights, 0.95)
    else:
        result["reachable_weighted_mean_walk_min"] = math.nan
        result["reachable_weighted_median_walk_min"] = math.nan
        result["reachable_weighted_p90_walk_min"] = math.nan
        result["reachable_weighted_p95_walk_min"] = math.nan
    return result


def compile_rt029(
    *,
    structures: pd.DataFrame,
    structure_link_manifest: pd.DataFrame,
    realizations: pd.DataFrame,
    walk_matrix: pd.DataFrame,
    expected_structure_count: int | None = 88,
    expected_core_municipality_count: int | None = 5,
    lineage: Mapping[str, str] | None = None,
) -> RT029Result:
    structures = _validate_structures(structures, expected_structure_count)
    _validate_manifest(structures, structure_link_manifest)
    required_links = set()
    for value in structures["link_ids"]:
        required_links.update(_split_ids(value, "link_ids"))
    realizations = _validate_realizations(realizations, required_links)
    walk, population_meta, service_map = _validate_walk_matrix(walk_matrix)

    stop_sets, operating = _stop_set_rows(structures, realizations, service_map)
    core_municipalities = sorted(
        set(
            population_meta.loc[
                population_meta["population_scope"].astype(str) == "core",
                "population_municipality_name",
            ].astype(str)
        )
    )
    if expected_core_municipality_count is not None and len(core_municipalities) != int(expected_core_municipality_count):
        raise RT029ContractError(
            f"expected {expected_core_municipality_count} core municipalities, got {len(core_municipalities)}"
        )

    access_rows: list[dict[str, object]] = []
    muni_rows: list[dict[str, object]] = []
    for row in stop_sets.itertuples(index=False):
        stops = set(_split_ids(row.ordered_stop_place_ids, f"{row.structure_id} {row.scenario} stops"))
        units = _best_walk_for_stops(walk, population_meta, stops)
        slices = {
            "ALL": units,
            "CORE": units[units["population_scope"].astype(str) == "core"],
            "EXTERNAL": units[units["population_scope"].astype(str) == "external"],
        }
        for scope, frame in slices.items():
            if not frame.empty:
                access_rows.append(
                    _summary_row(
                        str(row.structure_id), str(row.topology_class),
                        str(row.scenario), scope, frame.copy()
                    )
                )
        core_units = slices["CORE"]
        for municipality in core_municipalities:
            frame = core_units[
                core_units["population_municipality_name"].astype(str) == municipality
            ].copy()
            if frame.empty:
                raise RT029ContractError(f"core municipality {municipality} has no population units")
            mrow = _summary_row(
                str(row.structure_id), str(row.topology_class),
                str(row.scenario), "CORE_MUNICIPALITY", frame
            )
            mrow["municipality"] = municipality
            muni_rows.append(mrow)

    accessibility = pd.DataFrame(access_rows).sort_values(
        ["structure_id", "scenario", "scope"], kind="mergesort"
    ).reset_index(drop=True)
    municipality = pd.DataFrame(muni_rows).sort_values(
        ["structure_id", "scenario", "municipality"], kind="mergesort"
    ).reset_index(drop=True)

    equity_rows: list[dict[str, object]] = []
    for (sid, topology, scenario), group in municipality.groupby(
        ["structure_id", "topology_class", "scenario"], sort=True
    ):
        for threshold in THRESHOLDS:
            col = f"share_le_{threshold:g}_min"
            values = pd.to_numeric(group[col])
            equity_rows.append(
                {
                    "structure_id": sid,
                    "topology_class": topology,
                    "scenario": scenario,
                    "threshold_min": threshold,
                    "minimum_core_municipality_share": float(values.min()),
                    "maximum_core_municipality_share": float(values.max()),
                    "core_municipality_share_gap": float(values.max() - values.min()),
                    "core_municipality_count": int(len(group)),
                }
            )
    equity = pd.DataFrame(equity_rows).sort_values(
        ["structure_id", "scenario", "threshold_min"], kind="mergesort"
    ).reset_index(drop=True)

    core_decision = accessibility[
        (accessibility["scenario"] == DECISION_SCENARIO)
        & (accessibility["scope"] == "CORE")
    ].copy()
    if len(core_decision) != len(structures):
        raise RT029ContractError("missing guaranteed core accessibility row for one or more structures")

    frontier_rows: list[dict[str, object]] = []
    for threshold in THRESHOLDS:
        equity_t = equity[
            (equity["scenario"] == DECISION_SCENARIO)
            & (equity["threshold_min"] == threshold)
        ][["structure_id", "minimum_core_municipality_share", "core_municipality_share_gap"]]
        frame = (
            core_decision.merge(equity_t, on="structure_id", how="inner", validate="one_to_one")
            .merge(operating, on=["structure_id", "topology_class"], how="inner", validate="one_to_one")
        )
        threshold_col = f"share_le_{threshold:g}_min"
        required_numeric = [
            "reachable_population_share", threshold_col,
            "minimum_core_municipality_share",
            "reachable_weighted_p90_walk_min",
            "minimum_bidirectional_link_distance_m",
        ]
        if frame[required_numeric].isna().any().any():
            raise RT029ContractError(f"non-finite decision metric on {threshold:g}-minute frontier")
        records = []
        for r in frame.itertuples(index=False):
            records.append(
                {
                    "candidate_id": str(r.structure_id),
                    "reachable_population_share": float(r.reachable_population_share),
                    "threshold_share": float(getattr(r, threshold_col)),
                    "minimum_core_municipality_share": float(r.minimum_core_municipality_share),
                    "reachable_weighted_p90_walk_min": float(r.reachable_weighted_p90_walk_min),
                    "minimum_bidirectional_link_distance_m": float(r.minimum_bidirectional_link_distance_m),
                }
            )
        frontier_ids = set(
            _pareto_front(
                records,
                {
                    "reachable_population_share": "max",
                    "threshold_share": "max",
                    "minimum_core_municipality_share": "max",
                    "reachable_weighted_p90_walk_min": "min",
                    "minimum_bidirectional_link_distance_m": "min",
                },
            )
        )
        for _, r in frame[frame["structure_id"].astype(str).isin(frontier_ids)].sort_values(
            "structure_id", kind="mergesort"
        ).iterrows():
            frontier_rows.append(
                {
                    "threshold_min": threshold,
                    "structure_id": str(r["structure_id"]),
                    "topology_class": str(r["topology_class"]),
                    "core_reachable_population_share": float(r["reachable_population_share"]),
                    "core_threshold_share": float(r[threshold_col]),
                    "minimum_core_municipality_share": float(r["minimum_core_municipality_share"]),
                    "core_municipality_share_gap": float(r["core_municipality_share_gap"]),
                    "core_reachable_weighted_p90_walk_min": float(r["reachable_weighted_p90_walk_min"]),
                    "minimum_bidirectional_link_distance_m": float(r["minimum_bidirectional_link_distance_m"]),
                    "frontier_semantics": "NONDOMINATED_WITHIN_FROZEN_THRESHOLD_NO_WEIGHTED_COMPOSITE",
                }
            )

    frontiers = pd.DataFrame(frontier_rows).sort_values(
        ["threshold_min", "structure_id"], kind="mergesort"
    ).reset_index(drop=True)
    if frontiers.empty:
        raise RT029ContractError("Pareto frontier unexpectedly empty")

    shortlist_rows: list[dict[str, object]] = []
    for sid, group in frontiers.groupby("structure_id", sort=True):
        thresholds = sorted(float(x) for x in group["threshold_min"])
        topology_values = sorted(set(group["topology_class"].astype(str)))
        if len(topology_values) != 1:
            raise RT029ContractError(f"topology drift for shortlist structure {sid}")
        shortlist_rows.append(
            {
                "structure_id": str(sid),
                "topology_class": topology_values[0],
                "frontier_membership_count": len(thresholds),
                "frontier_thresholds_min": ";".join(f"{x:g}" for x in thresholds),
                "shortlist_semantics": "UNION_OF_THRESHOLD_SPECIFIC_PARETO_FRONTS_NOT_RANKED",
            }
        )
    shortlist = pd.DataFrame(shortlist_rows).sort_values(
        "structure_id", kind="mergesort"
    ).reset_index(drop=True)

    lineage_map = dict(sorted((lineage or {}).items()))
    audit = {
        "contract": CONTRACT,
        "status": "PASS",
        "structure_count": int(len(structures)),
        "scenario_count": len(SCENARIOS),
        "decision_scenario": DECISION_SCENARIO,
        "core_municipalities": core_municipalities,
        "thresholds_min": list(THRESHOLDS),
        "shortlist_count": int(len(shortlist)),
        "frontier_row_count": int(len(frontiers)),
        "stop_sets_sha256": _canonical_sha256(stop_sets, ["structure_id", "scenario"]),
        "accessibility_summary_sha256": _canonical_sha256(
            accessibility, ["structure_id", "scenario", "scope"]
        ),
        "municipality_accessibility_sha256": _canonical_sha256(
            municipality, ["structure_id", "scenario", "municipality"]
        ),
        "equity_summary_sha256": _canonical_sha256(
            equity, ["structure_id", "scenario", "threshold_min"]
        ),
        "operating_envelope_sha256": _canonical_sha256(operating, ["structure_id"]),
        "pareto_frontiers_sha256": _canonical_sha256(frontiers, ["threshold_min", "structure_id"]),
        "pareto_shortlist_sha256": _canonical_sha256(shortlist, ["structure_id"]),
        "lineage": lineage_map,
        "negative_assertions": {
            "uses_possible_union_for_pareto": False,
            "uses_special_service_stop": False,
            "uses_weighted_composite_score": False,
            "ranks_shortlist": False,
            "selects_primary_or_runner_up": False,
            "chooses_realization_alternative": False,
            "reruns_pedestrian_routing": False,
            "uses_euclidean_fallback": False,
            "drops_unreachable_population_from_threshold_denominator": False,
            "uses_random_search": False,
        },
    }
    return RT029Result(
        stop_sets=stop_sets,
        accessibility_summary=accessibility,
        municipality_accessibility=municipality,
        equity_summary=equity,
        operating_envelope=operating,
        pareto_frontiers=frontiers,
        pareto_shortlist=shortlist,
        audit=audit,
    )


def write_outputs(result: RT029Result, output_dir: str | Path) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    result.stop_sets.to_csv(out / "rt029_candidate_stop_sets_v3.csv", index=False, lineterminator="\n")
    result.accessibility_summary.to_csv(
        out / "rt029_candidate_accessibility_summary_v3.csv", index=False, lineterminator="\n"
    )
    result.municipality_accessibility.to_csv(
        out / "rt029_candidate_core_municipality_accessibility_v3.csv",
        index=False, lineterminator="\n",
    )
    result.equity_summary.to_csv(
        out / "rt029_candidate_core_equity_v3.csv", index=False, lineterminator="\n"
    )
    result.operating_envelope.to_csv(
        out / "rt029_candidate_operating_envelope_v3.csv", index=False, lineterminator="\n"
    )
    result.pareto_frontiers.to_csv(
        out / "rt029_pareto_frontiers_by_threshold_v3.csv", index=False, lineterminator="\n"
    )
    result.pareto_shortlist.to_csv(
        out / "rt029_pareto_shortlist_v3.csv", index=False, lineterminator="\n"
    )
    (out / "rt029_candidate_accessibility_pareto_audit_v3.json").write_text(
        json.dumps(result.audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
