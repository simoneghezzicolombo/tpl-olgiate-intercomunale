"""Normalize passenger-stop evidence for the independent Phase 2 Alpha search.

The adapter deliberately separates stop evidence from network design. It can
consume the current V3 passenger-stop foundation today and a later master stop
inventory without changing the routing/search contract.

Alpha's first canonical design universe is conservative:
- existing official physical stop clusters only;
- human-readable identity required;
- frozen Gate-D road snap must be route-ready;
- stop must belong to one of the five policy municipalities.

Reference-period official stops are allowed as infrastructure reuse candidates
even when they are not on the current D184/D185 pattern. Proposed stops remain
outside the canonical first-run universe until separately validated.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable

import pandas as pd

STUDY_MUNICIPALITIES = (
    "Olgiate Molgora",
    "Calco",
    "Brivio",
    "Santa Maria Hoè",
    "La Valletta Brianza",
)


def _key(value: object) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", text.lower())


_MUNICIPALITY_BY_KEY = {_key(value): value for value in STUDY_MUNICIPALITIES}
# Tolerate the historical mojibake present in a few derived CSVs.
_MUNICIPALITY_BY_KEY[_key("Santa Maria Hoe")] = "Santa Maria Hoè"
_MUNICIPALITY_BY_KEY[_key("Santa Maria HoÃ¨")] = "Santa Maria Hoè"


def canonical_municipality(value: object) -> str:
    return _MUNICIPALITY_BY_KEY.get(_key(value), str(value).strip())


def _bool(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _require(frame: pd.DataFrame, columns: Iterable[str], label: str) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"{label} missing columns: {missing}")


def build_alpha_stop_inventory(
    foundation: pd.DataFrame,
    routing_membership: pd.DataFrame,
) -> pd.DataFrame:
    """Return one normalized row per passenger-stop foundation record.

    No stop is selected for a route here. ``alpha_design_eligible`` means only
    that the record is epistemically admissible for the first independent Alpha
    search universe.
    """
    _require(
        foundation,
        {
            "stop_foundation_id",
            "physical_cluster_id",
            "stop_class",
            "human_label",
            "municipality",
            "lat",
            "lon",
            "evidence_status",
            "field_check_status",
            "current_d184_d185_physical_stop",
            "current_routes",
            "human_identity_ready",
            "source_lineage",
        },
        "passenger stop foundation",
    )
    _require(
        routing_membership,
        {
            "source_anchor_id",
            "graph_node_id",
            "snap_distance_m",
            "snap_status",
            "route_ready",
            "physical_status",
            "candidate_status",
            "epoch_id",
        },
        "routing anchor membership",
    )

    f = foundation.copy()
    r = routing_membership.copy()
    f["stop_foundation_id"] = f["stop_foundation_id"].astype(str)
    r["source_anchor_id"] = r["source_anchor_id"].astype(str)
    if f["stop_foundation_id"].duplicated().any():
        raise ValueError("stop_foundation_id must be unique")
    if r["source_anchor_id"].duplicated().any():
        raise ValueError("source_anchor_id must be unique")

    routing_cols = [
        "source_anchor_id",
        "graph_node_id",
        "snap_distance_m",
        "snap_status",
        "route_ready",
        "physical_status",
        "candidate_status",
        "epoch_id",
    ]
    merged = f.merge(
        r[routing_cols],
        how="left",
        left_on="stop_foundation_id",
        right_on="source_anchor_id",
        validate="one_to_one",
    )
    merged["municipality_canonical"] = merged["municipality"].map(canonical_municipality)
    merged["existing_official"] = merged["stop_class"].astype(str).eq("EXISTING_OFFICIAL")
    merged["human_identity_ready_bool"] = merged["human_identity_ready"].map(_bool)
    merged["route_ready_bool"] = merged["route_ready"].map(_bool)
    merged["current_d184_d185_bool"] = merged["current_d184_d185_physical_stop"].map(_bool)
    merged["in_study_area"] = merged["municipality_canonical"].isin(STUDY_MUNICIPALITIES)
    merged["routing_membership_present"] = merged["source_anchor_id"].notna()

    merged["alpha_design_eligible"] = (
        merged["existing_official"]
        & merged["human_identity_ready_bool"]
        & merged["route_ready_bool"]
        & merged["in_study_area"]
        & merged["routing_membership_present"]
    )

    def reason(row: pd.Series) -> str:
        failures: list[str] = []
        if not bool(row["existing_official"]):
            failures.append("NOT_EXISTING_OFFICIAL")
        if not bool(row["human_identity_ready_bool"]):
            failures.append("HUMAN_IDENTITY_NOT_READY")
        if not bool(row["routing_membership_present"]):
            failures.append("NO_FROZEN_ROUTING_MEMBERSHIP")
        elif not bool(row["route_ready_bool"]):
            failures.append("NOT_ROUTE_READY_LE_75M")
        if not bool(row["in_study_area"]):
            failures.append("OUTSIDE_FIVE_MUNICIPALITY_POLICY_AREA")
        return "ELIGIBLE_EXISTING_OFFICIAL_INFRASTRUCTURE" if not failures else ";".join(failures)

    merged["alpha_eligibility_reason"] = merged.apply(reason, axis=1)
    merged["infrastructure_reuse_scope"] = merged.apply(
        lambda row: (
            "CURRENT_D184_D185_OFFICIAL_STOP"
            if bool(row["current_d184_d185_bool"])
            else (
                "REFERENCE_PERIOD_OFFICIAL_STOP_REUSE_CANDIDATE"
                if bool(row["existing_official"])
                else "PROPOSED_OR_OTHER_NOT_CANONICAL_FIRST_RUN"
            )
        ),
        axis=1,
    )

    out = pd.DataFrame(
        {
            "alpha_stop_id": merged["stop_foundation_id"],
            "physical_cluster_id": merged["physical_cluster_id"],
            "human_label": merged["human_label"],
            "municipality": merged["municipality_canonical"],
            "lat": pd.to_numeric(merged["lat"], errors="coerce"),
            "lon": pd.to_numeric(merged["lon"], errors="coerce"),
            "graph_node_id": merged["graph_node_id"].fillna(""),
            "snap_distance_m": pd.to_numeric(merged["snap_distance_m"], errors="coerce"),
            "snap_status": merged["snap_status"].fillna(""),
            "stop_class": merged["stop_class"],
            "evidence_status": merged["evidence_status"],
            "physical_status": merged["physical_status"].fillna(""),
            "candidate_status": merged["candidate_status"].fillna(""),
            "field_check_status": merged["field_check_status"],
            "current_routes": merged["current_routes"].fillna(""),
            "current_d184_d185": merged["current_d184_d185_bool"],
            "existing_official": merged["existing_official"],
            "human_identity_ready": merged["human_identity_ready_bool"],
            "route_ready": merged["route_ready_bool"],
            "in_study_area": merged["in_study_area"],
            "alpha_design_eligible": merged["alpha_design_eligible"],
            "alpha_eligibility_reason": merged["alpha_eligibility_reason"],
            "infrastructure_reuse_scope": merged["infrastructure_reuse_scope"],
            "source_lineage": merged["source_lineage"],
            "epoch_id": merged["epoch_id"].fillna(""),
        }
    )
    return out.sort_values(
        ["alpha_design_eligible", "municipality", "alpha_stop_id"],
        ascending=[False, True, True],
        kind="mergesort",
    ).reset_index(drop=True)
