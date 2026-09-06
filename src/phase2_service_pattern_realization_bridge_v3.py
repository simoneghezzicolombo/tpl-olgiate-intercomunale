from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import pandas as pd


BRIDGE_CONTRACT = "RT023_TOPOLOGY_NEUTRAL_SERVICE_PATTERN_REALIZATION_BRIDGE_V3"
FRAGMENT_CONTRACT = "RT023_RT014_PATTERN_FRAGMENT_REQUIRES_DOWNSTREAM_SERVICE_PARAMETERS"
STRUCTURE_CONTRACT = "ABSTRACT_NETWORK_STRUCTURES_NOT_TERRITORIAL_RECOMMENDATIONS"


class RT023ContractError(ValueError):
    """Fail-closed contract violation at the RT-022 -> RT-023 interface."""


def _required_columns(df: pd.DataFrame, required: Iterable[str], label: str) -> None:
    missing = sorted(set(required) - set(df.columns))
    if missing:
        raise RT023ContractError(f"{label} missing required columns: {missing}")


def _as_bool(value: object, label: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    raise RT023ContractError(f"{label} must be boolean-like, got {value!r}")


def _nonnull_text(value: object, label: str) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        raise RT023ContractError(f"{label} must be non-null")
    text = str(value).strip()
    if not text:
        raise RT023ContractError(f"{label} must be non-empty")
    return text


def _stable_id(prefix: str, parts: Sequence[object]) -> str:
    payload = "\x1f".join(str(p) for p in parts).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(payload).hexdigest()[:20].upper()}"


def _canonical_sha256(df: pd.DataFrame, sort_cols: Sequence[str]) -> str:
    if df.empty:
        payload = b""
    else:
        stable = df.sort_values(list(sort_cols), kind="mergesort").reset_index(drop=True)
        payload = stable.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _split_ids(value: object, label: str) -> tuple[str, ...]:
    text = _nonnull_text(value, label)
    items = tuple(part.strip() for part in text.split(";") if part.strip())
    if not items:
        raise RT023ContractError(f"{label} contains no IDs")
    if len(items) != len(set(items)):
        raise RT023ContractError(f"{label} contains duplicate IDs")
    return items


@dataclass(frozen=True)
class BridgeResult:
    realization_catalog: pd.DataFrame
    structure_link_manifest: pd.DataFrame
    rt014_pattern_fragments: pd.DataFrame
    audit: dict[str, object]


def compile_rt023_bridge(
    *,
    reciprocal_links: pd.DataFrame,
    structures: pd.DataFrame,
    elementary_corridors: pd.DataFrame,
    corridor_stop_occurrences: pd.DataFrame,
    expected_graph_epoch_id: str | None = None,
    lineage: Mapping[str, str] | None = None,
) -> BridgeResult:
    """Compile RT-022 structural links into independent directed RT-021 realizations.

    This function does not enumerate, rank or select network topologies. All and
    only certified corridors marked both admitted and elementary are preserved.
    Passenger stops come only from the ordered frozen stop-occurrence evidence;
    technical graph nodes are never promoted to stops.
    """
    _required_columns(
        reciprocal_links,
        (
            "structural_link_id", "terminal_a", "terminal_b", "eligibility_status",
            "eligible_for_bidirectional_undirected_structure", "a_to_b_pair_id",
            "a_to_b_admitted_corridor_count", "b_to_a_pair_id",
            "b_to_a_admitted_corridor_count",
        ),
        "reciprocal_links",
    )
    _required_columns(structures, ("structure_id", "link_ids", "contract"), "structures")
    _required_columns(
        elementary_corridors,
        (
            "corridor_id", "pair_id", "source_stop_place_id", "target_stop_place_id",
            "path_node_ids", "path_geometry_sha256", "running_minutes_model", "distance_m",
            "edge_count", "graph_epoch_id", "admissible_for_corridor_pool",
            "elementary_for_structural_reduction",
        ),
        "elementary_corridors",
    )
    _required_columns(
        corridor_stop_occurrences,
        (
            "corridor_id", "stop_sequence", "path_node_position", "stop_place_id",
            "stop_occurrence_index", "service_class", "graph_node_id", "graph_epoch_id",
            "materialization_semantics",
        ),
        "corridor_stop_occurrences",
    )

    links = reciprocal_links.copy()
    structs = structures.copy()
    corridors = elementary_corridors.copy()
    occ = corridor_stop_occurrences.copy()

    if links["structural_link_id"].duplicated().any():
        raise RT023ContractError("duplicate structural_link_id")
    if structs["structure_id"].duplicated().any():
        raise RT023ContractError("duplicate structure_id")
    if corridors["corridor_id"].duplicated().any():
        raise RT023ContractError("duplicate corridor_id in elementary corridor evidence")

    for i, row in links.iterrows():
        if not _as_bool(
            row["eligible_for_bidirectional_undirected_structure"],
            f"link row {i} eligible_for_bidirectional_undirected_structure",
        ):
            raise RT023ContractError(
                f"structural link {row['structural_link_id']} is not reciprocal-eligible"
            )
        if _nonnull_text(row["eligibility_status"], "eligibility_status") != "RECIPROCAL_BIDIRECTIONAL_CORRIDOR_AVAILABLE":
            raise RT023ContractError(
                f"structural link {row['structural_link_id']} has unexpected eligibility_status"
            )

    bad_contracts = sorted(
        {
            _nonnull_text(v, "structure contract")
            for v in structs["contract"].tolist()
            if _nonnull_text(v, "structure contract") != STRUCTURE_CONTRACT
        }
    )
    if bad_contracts:
        raise RT023ContractError(f"unexpected RT-022 structure contracts: {bad_contracts}")

    graph_epochs = {
        _nonnull_text(v, "corridor graph_epoch_id")
        for v in corridors["graph_epoch_id"].dropna().tolist()
    }
    occ_epochs = {
        _nonnull_text(v, "occurrence graph_epoch_id")
        for v in occ["graph_epoch_id"].dropna().tolist()
    }
    if len(graph_epochs) != 1:
        raise RT023ContractError(
            f"corridor evidence must have exactly one graph epoch, got {sorted(graph_epochs)}"
        )
    if occ_epochs != graph_epochs:
        raise RT023ContractError(
            f"occurrence graph epochs {sorted(occ_epochs)} != corridor graph epochs {sorted(graph_epochs)}"
        )
    graph_epoch = next(iter(graph_epochs))
    if expected_graph_epoch_id is not None and graph_epoch != str(expected_graph_epoch_id):
        raise RT023ContractError(
            f"graph epoch mismatch: expected {expected_graph_epoch_id!r}, got {graph_epoch!r}"
        )

    admitted_mask = corridors.apply(
        lambda row: _as_bool(row["admissible_for_corridor_pool"], "admissible_for_corridor_pool")
        and _as_bool(row["elementary_for_structural_reduction"], "elementary_for_structural_reduction"),
        axis=1,
    )
    admitted = corridors.loc[admitted_mask].copy()
    if admitted.empty:
        raise RT023ContractError("no admitted elementary corridors")

    occurrences_by_corridor: dict[str, pd.DataFrame] = {}
    for corridor_id, group in occ.groupby("corridor_id", sort=False):
        ordered = group.sort_values(
            ["stop_sequence", "path_node_position", "stop_occurrence_index", "stop_place_id"],
            kind="mergesort",
        ).reset_index(drop=True)
        seq = [int(x) for x in ordered["stop_sequence"].tolist()]
        if seq != list(range(1, len(seq) + 1)):
            raise RT023ContractError(f"non-contiguous stop_sequence for corridor {corridor_id}")
        positions = [int(x) for x in ordered["path_node_position"].tolist()]
        if any(b < a for a, b in zip(positions, positions[1:])):
            raise RT023ContractError(f"decreasing path_node_position for corridor {corridor_id}")
        occurrences_by_corridor[str(corridor_id)] = ordered

    known_link_ids = set(links["structural_link_id"].astype(str))
    manifest_rows: list[dict[str, object]] = []
    for _, srow in structs.sort_values("structure_id", kind="mergesort").iterrows():
        structure_id = _nonnull_text(srow["structure_id"], "structure_id")
        link_ids = _split_ids(srow["link_ids"], f"link_ids for {structure_id}")
        unknown = sorted(set(link_ids) - known_link_ids)
        if unknown:
            raise RT023ContractError(f"structure {structure_id} references unknown links: {unknown}")
        for ordinal, link_id in enumerate(link_ids, start=1):
            manifest_rows.append(
                {
                    "structure_id": structure_id,
                    "structure_link_ordinal": ordinal,
                    "structural_link_id": link_id,
                    "composition_semantics": "LAZY_LINK_REFERENCE_NO_REALIZATION_CARTESIAN_PRODUCT",
                }
            )

    realization_rows: list[dict[str, object]] = []
    fragment_rows: list[dict[str, object]] = []

    def compile_direction(
        *,
        link_row: pd.Series,
        direction: str,
        pair_col: str,
        expected_count_col: str,
        source_col: str,
        target_col: str,
    ) -> None:
        link_id = _nonnull_text(link_row["structural_link_id"], "structural_link_id")
        pair_id = _nonnull_text(link_row[pair_col], f"{pair_col} for {link_id}")
        source = _nonnull_text(link_row[source_col], f"{source_col} for {link_id}")
        target = _nonnull_text(link_row[target_col], f"{target_col} for {link_id}")
        expected_count = int(link_row[expected_count_col])
        if expected_count <= 0:
            raise RT023ContractError(f"{link_id} {direction} expected corridor count must be positive")

        selected = admitted[admitted["pair_id"].astype(str) == pair_id].copy()
        selected = selected.sort_values(
            ["running_minutes_model", "distance_m", "corridor_id"], kind="mergesort"
        )
        if len(selected) != expected_count:
            raise RT023ContractError(
                f"{link_id} {direction} admitted corridor count mismatch: "
                f"RT-022={expected_count}, evidence={len(selected)}"
            )

        for alternative_ordinal, (_, crow) in enumerate(selected.iterrows(), start=1):
            cid = _nonnull_text(crow["corridor_id"], "corridor_id")
            if _nonnull_text(crow["source_stop_place_id"], f"source for {cid}") != source:
                raise RT023ContractError(
                    f"{link_id} {direction} corridor {cid} source does not match structural direction"
                )
            if _nonnull_text(crow["target_stop_place_id"], f"target for {cid}") != target:
                raise RT023ContractError(
                    f"{link_id} {direction} corridor {cid} target does not match structural direction"
                )
            path_node_ids = _nonnull_text(crow["path_node_ids"], f"path_node_ids for {cid}")
            if cid not in occurrences_by_corridor:
                raise RT023ContractError(f"corridor {cid} has no passenger stop occurrences")
            ordered_occ = occurrences_by_corridor[cid]
            passenger_stops = tuple(str(x) for x in ordered_occ["stop_place_id"].tolist())
            if len(passenger_stops) < 2:
                raise RT023ContractError(f"corridor {cid} has fewer than two passenger stops")
            if passenger_stops[0] != source or passenger_stops[-1] != target:
                raise RT023ContractError(
                    f"corridor {cid} ordered passenger boundaries do not match {source}->{target}"
                )
            if len(passenger_stops) != len(set(passenger_stops)):
                raise RT023ContractError(f"corridor {cid} repeats a passenger stop occurrence")
            classes = set(ordered_occ["service_class"].astype(str))
            if classes != {"CONVENTIONAL_TPL"}:
                raise RT023ContractError(
                    f"corridor {cid} contains non-conventional automatic passenger occurrences: {sorted(classes)}"
                )

            ordered_stops = ";".join(passenger_stops)
            realization_id = _stable_id(
                "RT023_REAL",
                (
                    link_id, direction, pair_id, cid,
                    _nonnull_text(crow["path_geometry_sha256"], f"path_geometry_sha256 for {cid}"),
                    ordered_stops,
                ),
            )
            fragment_id = _stable_id(
                "RT023_FRAG", (realization_id, ordered_stops, FRAGMENT_CONTRACT)
            )
            realization_rows.append(
                {
                    "realization_id": realization_id,
                    "structural_link_id": link_id,
                    "direction": direction,
                    "alternative_ordinal": alternative_ordinal,
                    "source_stop_place_id": source,
                    "target_stop_place_id": target,
                    "pair_id": pair_id,
                    "corridor_id": cid,
                    "path_node_ids": path_node_ids,
                    "path_geometry_sha256": _nonnull_text(
                        crow["path_geometry_sha256"], f"path_geometry_sha256 for {cid}"
                    ),
                    "running_minutes_model": float(crow["running_minutes_model"]),
                    "distance_m": float(crow["distance_m"]),
                    "edge_count": int(crow["edge_count"]),
                    "ordered_passenger_stop_place_ids": ordered_stops,
                    "passenger_stop_count": len(passenger_stops),
                    "graph_epoch_id": graph_epoch,
                    "realization_semantics": "INDEPENDENT_DIRECTED_FROZEN_CORRIDOR_NOT_REVERSED_FROM_OPPOSITE_DIRECTION",
                }
            )
            fragment_rows.append(
                {
                    "fragment_id": fragment_id,
                    "realization_id": realization_id,
                    "structural_link_id": link_id,
                    "direction": direction,
                    "ordered_passenger_stop_place_ids": ordered_stops,
                    "passenger_stop_count": len(passenger_stops),
                    "requires_pattern_id": True,
                    "requires_route_id": True,
                    "requires_service_id": True,
                    "requires_direction_id": True,
                    "requires_cumulative_times_sec": True,
                    "requires_departures_sec": True,
                    "contract": FRAGMENT_CONTRACT,
                }
            )

    for _, lrow in links.sort_values("structural_link_id", kind="mergesort").iterrows():
        compile_direction(
            link_row=lrow,
            direction="A_TO_B",
            pair_col="a_to_b_pair_id",
            expected_count_col="a_to_b_admitted_corridor_count",
            source_col="terminal_a",
            target_col="terminal_b",
        )
        compile_direction(
            link_row=lrow,
            direction="B_TO_A",
            pair_col="b_to_a_pair_id",
            expected_count_col="b_to_a_admitted_corridor_count",
            source_col="terminal_b",
            target_col="terminal_a",
        )

    realizations = pd.DataFrame(realization_rows).sort_values(
        ["structural_link_id", "direction", "alternative_ordinal", "corridor_id"], kind="mergesort"
    ).reset_index(drop=True)
    manifest = pd.DataFrame(manifest_rows).sort_values(
        ["structure_id", "structure_link_ordinal", "structural_link_id"], kind="mergesort"
    ).reset_index(drop=True)
    fragments = pd.DataFrame(fragment_rows).sort_values(
        ["structural_link_id", "direction", "realization_id"], kind="mergesort"
    ).reset_index(drop=True)

    if realizations["realization_id"].duplicated().any():
        raise RT023ContractError("realization_id collision")
    if fragments["fragment_id"].duplicated().any():
        raise RT023ContractError("fragment_id collision")
    if set(manifest["structural_link_id"]) - set(realizations["structural_link_id"]):
        raise RT023ContractError("structure manifest references a link with no realization")

    pair_expectation: dict[tuple[str, str], str] = {}
    for _, row in links.iterrows():
        pair_expectation[(str(row["structural_link_id"]), "A_TO_B")] = str(row["a_to_b_pair_id"])
        pair_expectation[(str(row["structural_link_id"]), "B_TO_A")] = str(row["b_to_a_pair_id"])
    for _, row in realizations.iterrows():
        key = (str(row["structural_link_id"]), str(row["direction"]))
        if str(row["pair_id"]) != pair_expectation[key]:
            raise RT023ContractError(f"directional pair drift for {key}")

    link_alt_counts = (
        realizations.groupby(["structural_link_id", "direction"]).size().rename("count").reset_index()
    )
    audit = {
        "status": "PASS",
        "contract": BRIDGE_CONTRACT,
        "graph_epoch_id": graph_epoch,
        "structural_link_count": int(len(links)),
        "structure_count": int(len(structs)),
        "structure_link_reference_count": int(len(manifest)),
        "realization_count": int(len(realizations)),
        "pattern_fragment_count": int(len(fragments)),
        "a_to_b_realization_count": int((realizations["direction"] == "A_TO_B").sum()),
        "b_to_a_realization_count": int((realizations["direction"] == "B_TO_A").sum()),
        "links_with_multiple_a_to_b_alternatives": int(
            ((link_alt_counts["direction"] == "A_TO_B") & (link_alt_counts["count"] > 1)).sum()
        ),
        "links_with_multiple_b_to_a_alternatives": int(
            ((link_alt_counts["direction"] == "B_TO_A") & (link_alt_counts["count"] > 1)).sum()
        ),
        "realization_catalog_sha256": _canonical_sha256(
            realizations, ["structural_link_id", "direction", "alternative_ordinal", "corridor_id"]
        ),
        "structure_link_manifest_sha256": _canonical_sha256(
            manifest, ["structure_id", "structure_link_ordinal", "structural_link_id"]
        ),
        "rt014_pattern_fragments_sha256": _canonical_sha256(
            fragments, ["structural_link_id", "direction", "realization_id"]
        ),
        "negative_assertions": {
            "enumerates_network_topologies": False,
            "selects_network_topology": False,
            "ranks_structures": False,
            "selects_primary_or_runner_up": False,
            "chooses_hub_or_figure_8": False,
            "chooses_service_areas": False,
            "chooses_terminals_as_service_policy": False,
            "chooses_frequencies_or_headways": False,
            "chooses_calendars": False,
            "chooses_departures_or_timetables": False,
            "creates_passenger_stops": False,
            "constructs_reverse_direction_by_path_reversal": False,
            "creates_structure_realization_cartesian_products": False,
        },
        "lineage": dict(sorted((lineage or {}).items())),
    }
    return BridgeResult(realizations, manifest, fragments, audit)


def build_rt014_service_pattern_from_fragment(
    fragment: Mapping[str, object],
    *,
    pattern_id: str,
    route_id: str,
    service_id: str,
    direction_id: int,
    cumulative_times_sec: Sequence[int],
    departures_sec: Sequence[int],
):
    """Adapt a fragment to RT-014 only with explicit downstream service inputs."""
    from phase2_candidate_gtfs_materializer_v3 import ServicePattern, StopCall

    stops = _split_ids(
        fragment["ordered_passenger_stop_place_ids"], "ordered_passenger_stop_place_ids"
    )
    if len(cumulative_times_sec) != len(stops):
        raise RT023ContractError(
            "cumulative_times_sec length must equal ordered passenger stop count"
        )
    calls = tuple(
        StopCall(
            stop_id=stop_id,
            stop_sequence=i,
            cumulative_time_sec=int(cumulative_times_sec[i - 1]),
        )
        for i, stop_id in enumerate(stops, start=1)
    )
    return ServicePattern(
        pattern_id=_nonnull_text(pattern_id, "pattern_id"),
        route_id=_nonnull_text(route_id, "route_id"),
        service_id=_nonnull_text(service_id, "service_id"),
        direction_id=int(direction_id),
        stop_calls=calls,
        departures_sec=tuple(int(x) for x in departures_sec),
    )


def write_bridge_result(result: BridgeResult, output_dir: str | Path) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    result.realization_catalog.to_csv(
        out / "link_realization_catalog.csv", index=False, lineterminator="\n"
    )
    result.structure_link_manifest.to_csv(
        out / "structure_link_manifest.csv", index=False, lineterminator="\n"
    )
    result.rt014_pattern_fragments.to_csv(
        out / "rt014_pattern_fragments.csv", index=False, lineterminator="\n"
    )
    (out / "rt023_service_pattern_realization_audit.json").write_text(
        json.dumps(result.audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
