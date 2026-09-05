"""Technical pair-query anchors and elementary corridor reduction for Phase 2 V3.

A pair-query routing anchor is an exhaustive road-routing query endpoint only.
It is not a passenger-service terminus/capolinea and does not prescribe route
topology. The final service termini, if any, are a downstream service-design
property.

After RT-006 corridor generation and RT-018 exact stop-occurrence
materialization, admitted directional corridors are classified as elementary
only when no third conventional stop place occurs strictly between the source
and target boundary nodes. Decomposable corridors remain evidence but are not
primitive structural links. RT-009 reciprocity is then applied to the filtered
elementary corridor pool.
"""
from __future__ import annotations

from typing import Iterable, Sequence

import pandas as pd

from src.phase2_corridor_reciprocity_v3 import build_reciprocal_structural_links


CONTRACT = (
    "TECHNICAL_PAIR_QUERY_ANCHORS_AND_ELEMENTARY_CORRIDOR_INTERFACE_"
    "NOT_SERVICE_TERMINAL_SELECTION"
)
PAIR_QUERY_SOURCE_KIND = "FINAL_OPERATIONAL_STOP_PLACE_TECHNICAL_PAIR_QUERY_ANCHOR"
PAIR_QUERY_EVIDENCE_STATUS = "TECHNICAL_QUERY_ANCHOR_NOT_SERVICE_TERMINUS"
DEFAULT_CONVENTIONAL_SERVICE_CLASSES = ("CONVENTIONAL_TPL",)


def _as_bool(value: object, *, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if value in (0, 1):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    raise ValueError(f"invalid boolean for {field}: {value!r}")


def _require_columns(frame: pd.DataFrame, required: Iterable[str], label: str) -> None:
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise ValueError(f"{label} missing columns: {missing}")


def build_pair_query_anchor_table(
    attachments: pd.DataFrame,
    *,
    allowed_service_classes: Sequence[str] = DEFAULT_CONVENTIONAL_SERVICE_CLASSES,
) -> pd.DataFrame:
    """Build graph-bound technical query anchors from RT-018 attachments.

    Every allowed-service-class stop must be route-ready. Otherwise the function
    fails closed instead of silently shrinking the complete pair universe.
    Non-allowed service classes remain outside this conventional-service query
    manifest and are not reclassified.
    """
    required = {
        "stop_place_id",
        "stop_name",
        "municipality",
        "service_class",
        "graph_node_id",
        "route_ready",
        "attachment_status",
        "graph_epoch_id",
    }
    _require_columns(attachments, required, "stop attachments")
    frame = attachments.copy().fillna("")
    for column in (
        "stop_place_id",
        "stop_name",
        "municipality",
        "service_class",
        "graph_node_id",
        "attachment_status",
        "graph_epoch_id",
    ):
        frame[column] = frame[column].astype(str).str.strip()
    if frame["stop_place_id"].eq("").any():
        raise ValueError("blank stop_place_id in stop attachments")
    if frame["stop_place_id"].duplicated().any():
        raise ValueError("stop_place_id must be unique in stop attachments")

    allowed = {str(value).strip() for value in allowed_service_classes}
    if not allowed or "" in allowed:
        raise ValueError("allowed_service_classes must contain non-empty values")

    frame["route_ready"] = [
        _as_bool(value, field="route_ready") for value in frame["route_ready"]
    ]
    candidate = frame[frame["service_class"].isin(allowed)].copy()
    if candidate.empty:
        raise ValueError("no stops match the allowed conventional service classes")

    blocked = candidate[~candidate["route_ready"]]
    if not blocked.empty:
        ids = sorted(blocked["stop_place_id"].astype(str))
        raise ValueError(
            "conventional pair-query anchors must all be route-ready; "
            f"blocked={ids}"
        )
    if candidate["graph_node_id"].eq("").any():
        raise ValueError("route-ready pair-query anchor has blank graph_node_id")

    epochs = sorted(set(candidate["graph_epoch_id"].astype(str)))
    if len(epochs) != 1 or not epochs[0]:
        raise ValueError(
            "pair-query anchors must be bound to exactly one non-empty graph epoch"
        )

    out = pd.DataFrame(
        {
            "routing_terminal_id": candidate["stop_place_id"].astype(str),
            "stop_place_id": candidate["stop_place_id"].astype(str),
            "stop_name": candidate["stop_name"].astype(str),
            "municipality": candidate["municipality"].astype(str),
            "service_class": candidate["service_class"].astype(str),
            "graph_node_id": candidate["graph_node_id"].astype(str),
            "attachment_status": candidate["attachment_status"].astype(str),
            "graph_epoch_id": candidate["graph_epoch_id"].astype(str),
            "terminal_source_kind": PAIR_QUERY_SOURCE_KIND,
            "terminal_evidence_status": PAIR_QUERY_EVIDENCE_STATUS,
            "pair_query_anchor": True,
            "service_terminal_status_claimed": False,
            "scope": CONTRACT,
        }
    )
    return out.sort_values("routing_terminal_id", kind="mergesort").reset_index(drop=True)


def _parse_path_nodes(value: object) -> tuple[str, ...]:
    if isinstance(value, (tuple, list)):
        nodes = tuple(str(part).strip() for part in value if str(part).strip())
    else:
        nodes = tuple(part.strip() for part in str(value).split(";") if part.strip())
    if len(nodes) < 2:
        raise ValueError("corridor path_node_ids must contain at least two nodes")
    return nodes


def classify_elementary_corridors(
    corridors: pd.DataFrame,
    occurrences: pd.DataFrame,
    *,
    allowed_service_classes: Sequence[str] = DEFAULT_CONVENTIONAL_SERVICE_CLASSES,
) -> pd.DataFrame:
    """Classify each directional corridor alternative from exact stop occurrences.

    A third allowed-class stop occurrence is intermediate only when its
    `path_node_position` is strictly inside the corridor path. Source/target
    stop IDs are never counted as third stops, even if a loop revisits them.
    Endpoint stop occurrences are required at the actual path boundaries.
    """
    corridor_required = {
        "corridor_id",
        "pair_id",
        "source_routing_terminal_id",
        "target_routing_terminal_id",
        "path_node_ids",
        "admissible_for_corridor_pool",
    }
    occurrence_required = {
        "corridor_id",
        "stop_sequence",
        "path_node_position",
        "stop_place_id",
        "service_class",
    }
    _require_columns(corridors, corridor_required, "corridor evidence")
    _require_columns(occurrences, occurrence_required, "stop occurrences")

    c = corridors.copy().fillna("")
    o = occurrences.copy().fillna("")
    for column in (
        "corridor_id",
        "pair_id",
        "source_routing_terminal_id",
        "target_routing_terminal_id",
    ):
        c[column] = c[column].astype(str).str.strip()
        if c[column].eq("").any():
            raise ValueError(f"blank {column} in corridor evidence")
    if c["corridor_id"].duplicated().any():
        raise ValueError("corridor_id must be globally unique")
    if c["source_routing_terminal_id"].eq(c["target_routing_terminal_id"]).any():
        raise ValueError("self corridor endpoints are not allowed")
    c["admissible_for_corridor_pool"] = [
        _as_bool(value, field="admissible_for_corridor_pool")
        for value in c["admissible_for_corridor_pool"]
    ]

    if not o.empty:
        for column in ("corridor_id", "stop_place_id", "service_class"):
            o[column] = o[column].astype(str).str.strip()
            if o[column].eq("").any():
                raise ValueError(f"blank {column} in stop occurrences")
        o["stop_sequence"] = pd.to_numeric(o["stop_sequence"], errors="raise").astype(int)
        o["path_node_position"] = pd.to_numeric(
            o["path_node_position"], errors="raise"
        ).astype(int)
        unknown = sorted(set(o["corridor_id"]) - set(c["corridor_id"]))
        if unknown:
            raise ValueError(f"stop occurrences reference unknown corridors: {unknown}")
        if o.duplicated(["corridor_id", "stop_sequence"]).any():
            raise ValueError("stop_sequence must be unique within each corridor")

    allowed = {str(value).strip() for value in allowed_service_classes}
    if not allowed or "" in allowed:
        raise ValueError("allowed_service_classes must contain non-empty values")
    o = o[o["service_class"].isin(allowed)].copy()
    grouped = {
        str(corridor_id): group.sort_values(
            ["path_node_position", "stop_sequence", "stop_place_id"],
            kind="mergesort",
        ).reset_index(drop=True)
        for corridor_id, group in o.groupby("corridor_id", sort=True)
    }

    rows: list[dict[str, object]] = []
    for corridor in c.sort_values("corridor_id", kind="mergesort").itertuples(index=False):
        corridor_id = str(corridor.corridor_id)
        source = str(corridor.source_routing_terminal_id)
        target = str(corridor.target_routing_terminal_id)
        nodes = _parse_path_nodes(corridor.path_node_ids)
        final_position = len(nodes) - 1
        group = grouped.get(corridor_id, pd.DataFrame(columns=o.columns))

        source_boundary_present = bool(
            ((group["stop_place_id"] == source) & (group["path_node_position"] == 0)).any()
        )
        target_boundary_present = bool(
            ((group["stop_place_id"] == target) & (group["path_node_position"] == final_position)).any()
        )
        interior = group[
            (group["path_node_position"] > 0) & (group["path_node_position"] < final_position)
        ]
        via_occurrences = [
            str(stop_id)
            for stop_id in interior["stop_place_id"].astype(str).tolist()
            if str(stop_id) not in {source, target}
        ]
        via_unique: list[str] = []
        seen: set[str] = set()
        for stop_id in via_occurrences:
            if stop_id not in seen:
                seen.add(stop_id)
                via_unique.append(stop_id)

        admitted = bool(corridor.admissible_for_corridor_pool)
        endpoint_complete = source_boundary_present and target_boundary_present
        if not admitted:
            status = "NOT_ADMITTED_NOT_STRUCTURAL_CANDIDATE"
            elementary = False
        elif not endpoint_complete:
            status = "BLOCKED_ENDPOINT_OCCURRENCE_MISSING"
            elementary = False
        elif via_occurrences:
            status = "DECOMPOSABLE_VIA_INTERMEDIATE_CONVENTIONAL_STOP"
            elementary = False
        else:
            status = "ELEMENTARY_NO_INTERMEDIATE_CONVENTIONAL_STOP"
            elementary = True

        rows.append(
            {
                "corridor_id": corridor_id,
                "pair_id": str(corridor.pair_id),
                "source_routing_terminal_id": source,
                "target_routing_terminal_id": target,
                "admissible_for_corridor_pool": admitted,
                "source_boundary_occurrence_present": source_boundary_present,
                "target_boundary_occurrence_present": target_boundary_present,
                "endpoint_occurrence_contract_pass": endpoint_complete,
                "strict_intermediate_occurrence_count": len(via_occurrences),
                "strict_intermediate_unique_stop_count": len(via_unique),
                "via_stop_place_occurrences": "|".join(via_occurrences),
                "via_stop_place_ids_ordered_unique": "|".join(via_unique),
                "elementary_status": status,
                "elementary_for_structural_reduction": elementary,
                "scope": CONTRACT,
            }
        )
    return pd.DataFrame(rows).sort_values("corridor_id", kind="mergesort").reset_index(drop=True)


def build_directional_elementary_availability(
    classification: pd.DataFrame,
) -> pd.DataFrame:
    """Summarize whether each requested direction has any elementary alternative."""
    required = {
        "pair_id",
        "source_routing_terminal_id",
        "target_routing_terminal_id",
        "admissible_for_corridor_pool",
        "elementary_for_structural_reduction",
        "corridor_id",
    }
    _require_columns(classification, required, "elementary corridor classification")
    frame = classification.copy().fillna("")
    if frame["corridor_id"].astype(str).duplicated().any():
        raise ValueError("classification corridor_id must be unique")

    frame["admissible_for_corridor_pool"] = [
        _as_bool(value, field="admissible_for_corridor_pool")
        for value in frame["admissible_for_corridor_pool"]
    ]
    frame["elementary_for_structural_reduction"] = [
        _as_bool(value, field="elementary_for_structural_reduction")
        for value in frame["elementary_for_structural_reduction"]
    ]
    rows: list[dict[str, object]] = []
    keys = ["pair_id", "source_routing_terminal_id", "target_routing_terminal_id"]
    for key, group in frame.groupby(keys, sort=True):
        pair_id, source, target = (str(part) for part in key)
        admitted = group[group["admissible_for_corridor_pool"]]
        elementary = admitted[admitted["elementary_for_structural_reduction"]]
        rows.append(
            {
                "pair_id": pair_id,
                "source_routing_terminal_id": source,
                "target_routing_terminal_id": target,
                "admitted_corridor_count": int(len(admitted)),
                "elementary_admitted_corridor_count": int(len(elementary)),
                "elementary_corridor_ids": "|".join(
                    sorted(elementary["corridor_id"].astype(str))
                ),
                "has_elementary_admitted_corridor": not elementary.empty,
                "service_terminal_status_claimed": False,
                "scope": CONTRACT,
            }
        )
    return pd.DataFrame(rows).sort_values(keys, kind="mergesort").reset_index(drop=True)


def filter_elementary_corridors_for_reciprocity(
    corridors: pd.DataFrame,
    classification: pd.DataFrame,
) -> pd.DataFrame:
    """Preserve all corridor rows but expose only elementary admitted paths to RT-009."""
    _require_columns(
        corridors,
        {"corridor_id", "pair_id", "admissible_for_corridor_pool"},
        "corridor evidence",
    )
    _require_columns(
        classification,
        {"corridor_id", "elementary_for_structural_reduction"},
        "elementary corridor classification",
    )
    c = corridors.copy()
    k = classification[["corridor_id", "elementary_for_structural_reduction"]].copy()
    if c["corridor_id"].astype(str).duplicated().any():
        raise ValueError("corridor_id must be globally unique")
    if k["corridor_id"].astype(str).duplicated().any():
        raise ValueError("classification corridor_id must be unique")
    merged = c.merge(k, on="corridor_id", how="left", validate="one_to_one")
    if merged["elementary_for_structural_reduction"].isna().any():
        missing = sorted(
            merged.loc[
                merged["elementary_for_structural_reduction"].isna(), "corridor_id"
            ].astype(str)
        )
        raise ValueError(f"corridors missing elementary classification: {missing}")
    original_admitted = [
        _as_bool(value, field="admissible_for_corridor_pool")
        for value in merged["admissible_for_corridor_pool"]
    ]
    elementary = [
        _as_bool(value, field="elementary_for_structural_reduction")
        for value in merged["elementary_for_structural_reduction"]
    ]
    merged["original_admissible_for_corridor_pool"] = original_admitted
    merged["admissible_for_corridor_pool"] = [
        admitted and is_elementary
        for admitted, is_elementary in zip(original_admitted, elementary)
    ]
    merged["elementary_reciprocity_filter_semantics"] = (
        "ALL_EVIDENCE_RETAINED_ONLY_ELEMENTARY_ADMITTED_PATHS_EXPOSED_TO_RT009"
    )
    return merged.sort_values(["pair_id", "corridor_id"], kind="mergesort").reset_index(drop=True)


def build_reciprocal_elementary_structural_links(
    pairs: pd.DataFrame,
    corridors: pd.DataFrame,
    occurrences: pd.DataFrame,
) -> dict[str, object]:
    """Classify corridor alternatives and delegate reciprocal link eligibity to RT-009."""
    classification = classify_elementary_corridors(corridors, occurrences)
    directional = build_directional_elementary_availability(classification)
    filtered = filter_elementary_corridors_for_reciprocity(corridors, classification)
    reciprocal = build_reciprocal_structural_links(pairs, filtered)
    metadata = dict(reciprocal["metadata"])
    metadata.update(
        {
            "rt019_contract": CONTRACT,
            "corridor_elementarity_semantics": (
                "PER_ALTERNATIVE_EXACT_ORDERED_STOP_OCCURRENCES"
            ),
            "decomposable_corridors_deleted_from_evidence": False,
            "service_terminal_status_claimed": False,
            "special_service_auto_included": False,
            "rt017_rebind_required_before_territorial_use": True,
        }
    )
    return {
        "classification": classification,
        "directional_availability": directional,
        "filtered_corridors_for_rt009": filtered,
        "pair_audit": reciprocal["pair_audit"],
        "structural_links": reciprocal["structural_links"],
        "metadata": metadata,
    }
