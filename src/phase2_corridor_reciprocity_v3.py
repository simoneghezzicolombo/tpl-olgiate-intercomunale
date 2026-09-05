"""Directional corridor evidence -> reciprocal undirected structural links.

This adapter is deliberately semantic, not geographic. RT-006 corridor evidence
is directional, while RT-007/008 consume simple undirected structural links.
The adapter never infers reciprocity from a single tested direction and never
interprets an unrequested reverse direction as infeasible.
"""
from __future__ import annotations

import hashlib
from typing import Iterable

import pandas as pd


CONTRACT = "RECIPROCAL_BIDIRECTIONAL_STRUCTURAL_LINK_INTERFACE_NOT_NETWORK_SELECTION"


def _as_bool(value, *, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if value in (0, 1):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    raise ValueError(f"invalid boolean for {field}: {value!r}")


def structural_link_id(terminal_a: str, terminal_b: str) -> str:
    a, b = sorted((str(terminal_a), str(terminal_b)))
    if not a or not b or a == b:
        raise ValueError("structural link requires two distinct non-empty terminals")
    payload = f"{a}|{b}".encode("utf-8")
    return "STRUCT_LINK_" + hashlib.sha256(payload).hexdigest()[:16].upper()


def _validate_pair_records(pairs: pd.DataFrame) -> pd.DataFrame:
    required = {
        "pair_id",
        "source_routing_terminal_id",
        "target_routing_terminal_id",
        "gate_d_route_found",
    }
    missing = required - set(pairs.columns)
    if missing:
        raise ValueError(f"pair evidence missing columns: {sorted(missing)}")

    frame = pairs.copy().fillna("")
    for col in ["pair_id", "source_routing_terminal_id", "target_routing_terminal_id"]:
        frame[col] = frame[col].astype(str).str.strip()
        if frame[col].eq("").any():
            raise ValueError(f"blank {col}")
    if frame["pair_id"].duplicated().any():
        raise ValueError("pair_id must be unique")
    if frame["source_routing_terminal_id"].eq(frame["target_routing_terminal_id"]).any():
        raise ValueError("self-pairs are not allowed")

    directed_keys = list(
        zip(
            frame["source_routing_terminal_id"],
            frame["target_routing_terminal_id"],
        )
    )
    if len(directed_keys) != len(set(directed_keys)):
        raise ValueError("each ordered terminal pair may be requested only once")

    frame["gate_d_route_found"] = [
        _as_bool(value, field="gate_d_route_found")
        for value in frame["gate_d_route_found"]
    ]
    return frame.sort_values(
        ["source_routing_terminal_id", "target_routing_terminal_id", "pair_id"],
        kind="mergesort",
    ).reset_index(drop=True)


def _validate_corridor_records(
    corridors: pd.DataFrame,
    known_pair_ids: set[str],
) -> pd.DataFrame:
    required = {"pair_id", "corridor_id", "admissible_for_corridor_pool"}
    missing = required - set(corridors.columns)
    if missing:
        raise ValueError(f"corridor evidence missing columns: {sorted(missing)}")

    frame = corridors.copy().fillna("")
    if frame.empty:
        return frame
    for col in ["pair_id", "corridor_id"]:
        frame[col] = frame[col].astype(str).str.strip()
        if frame[col].eq("").any():
            raise ValueError(f"blank {col}")
    unknown = sorted(set(frame["pair_id"]) - known_pair_ids)
    if unknown:
        raise ValueError(f"corridors reference unknown pair_id values: {unknown}")
    if frame["corridor_id"].duplicated().any():
        raise ValueError("corridor_id must be globally unique")
    frame["admissible_for_corridor_pool"] = [
        _as_bool(value, field="admissible_for_corridor_pool")
        for value in frame["admissible_for_corridor_pool"]
    ]
    return frame.sort_values(["pair_id", "corridor_id"], kind="mergesort").reset_index(drop=True)


def _direction_summary(
    pair_row: dict | None,
    admitted_by_pair: dict[str, pd.DataFrame],
) -> dict:
    if pair_row is None:
        return {
            "requested": False,
            "pair_id": "",
            "gate_d_route_found": False,
            "admitted_corridor_count": 0,
            "min_running_minutes_model": None,
            "min_distance_m": None,
        }

    pair_id = str(pair_row["pair_id"])
    admitted = admitted_by_pair.get(pair_id)
    count = 0 if admitted is None else len(admitted)

    min_runtime = None
    min_distance = None
    if admitted is not None and not admitted.empty:
        if "running_minutes_model" in admitted.columns:
            values = pd.to_numeric(admitted["running_minutes_model"], errors="coerce").dropna()
            if not values.empty:
                min_runtime = float(values.min())
        if "distance_m" in admitted.columns:
            values = pd.to_numeric(admitted["distance_m"], errors="coerce").dropna()
            if not values.empty:
                min_distance = float(values.min())

    return {
        "requested": True,
        "pair_id": pair_id,
        "gate_d_route_found": bool(pair_row["gate_d_route_found"]),
        "admitted_corridor_count": int(count),
        "min_running_minutes_model": min_runtime,
        "min_distance_m": min_distance,
    }


def build_reciprocal_structural_links(
    pairs: pd.DataFrame,
    corridors: pd.DataFrame,
) -> dict[str, pd.DataFrame | dict]:
    """Build audited reciprocal undirected links from directional evidence.

    The full `pair_audit` retains every unordered terminal pair encountered in
    the directional request table. `structural_links` contains only pairs for
    which both directions were explicitly requested, both had Gate-D routes and
    both have at least one admitted RT-006 corridor.
    """
    pair_frame = _validate_pair_records(pairs)
    corridor_frame = _validate_corridor_records(corridors, set(pair_frame["pair_id"]))

    admitted = corridor_frame[corridor_frame["admissible_for_corridor_pool"]].copy()
    admitted_by_pair = {
        str(pair_id): group.reset_index(drop=True)
        for pair_id, group in admitted.groupby("pair_id", sort=True)
    }
    directed = {
        (str(row.source_routing_terminal_id), str(row.target_routing_terminal_id)): row._asdict()
        for row in pair_frame.itertuples(index=False)
    }

    unordered_pairs = sorted(
        {
            tuple(sorted((source, target)))
            for source, target in directed
        }
    )

    audit_rows: list[dict] = []
    eligible_rows: list[dict] = []

    for terminal_a, terminal_b in unordered_pairs:
        a_to_b = _direction_summary(
            directed.get((terminal_a, terminal_b)), admitted_by_pair
        )
        b_to_a = _direction_summary(
            directed.get((terminal_b, terminal_a)), admitted_by_pair
        )

        if not a_to_b["requested"] or not b_to_a["requested"]:
            status = "UNTESTED_DIRECTION"
        elif not a_to_b["gate_d_route_found"] or not b_to_a["gate_d_route_found"]:
            status = "NO_GATE_D_ROUTE_IN_DIRECTION"
        elif (
            a_to_b["admitted_corridor_count"] < 1
            or b_to_a["admitted_corridor_count"] < 1
        ):
            status = "NO_ADMITTED_CORRIDOR_IN_DIRECTION"
        else:
            status = "RECIPROCAL_BIDIRECTIONAL_CORRIDOR_AVAILABLE"

        eligible = status == "RECIPROCAL_BIDIRECTIONAL_CORRIDOR_AVAILABLE"
        row = {
            "structural_link_id": structural_link_id(terminal_a, terminal_b),
            "terminal_a": terminal_a,
            "terminal_b": terminal_b,
            "eligibility_status": status,
            "eligible_for_bidirectional_undirected_structure": eligible,
            "a_to_b_requested": a_to_b["requested"],
            "a_to_b_pair_id": a_to_b["pair_id"],
            "a_to_b_gate_d_route_found": a_to_b["gate_d_route_found"],
            "a_to_b_admitted_corridor_count": a_to_b["admitted_corridor_count"],
            "a_to_b_min_running_minutes_model": a_to_b["min_running_minutes_model"],
            "a_to_b_min_distance_m": a_to_b["min_distance_m"],
            "b_to_a_requested": b_to_a["requested"],
            "b_to_a_pair_id": b_to_a["pair_id"],
            "b_to_a_gate_d_route_found": b_to_a["gate_d_route_found"],
            "b_to_a_admitted_corridor_count": b_to_a["admitted_corridor_count"],
            "b_to_a_min_running_minutes_model": b_to_a["min_running_minutes_model"],
            "b_to_a_min_distance_m": b_to_a["min_distance_m"],
            "scope": CONTRACT,
        }
        audit_rows.append(row)
        if eligible:
            eligible_rows.append(row)

    pair_audit = pd.DataFrame(audit_rows)
    structural_links = pd.DataFrame(eligible_rows)
    metadata = {
        "contract": CONTRACT,
        "directional_absence_semantics": "NOT_REQUESTED_IS_UNKNOWN_NOT_INFEASIBLE",
        "eligibility_semantics": "BOTH_DIRECTIONS_TESTED_AND_ADMITTED_REQUIRED",
        "directional_only_service_authorized": False,
        "automatic_topology_selection": False,
        "weighted_composite_score": False,
        "unordered_pairs_audited": len(pair_audit),
        "eligible_structural_links": len(structural_links),
    }
    return {
        "pair_audit": pair_audit,
        "structural_links": structural_links,
        "metadata": metadata,
    }
