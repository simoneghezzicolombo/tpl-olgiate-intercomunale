#!/usr/bin/env python3
"""Validate current/future Arriva service evidence against the stop master.

This gate validates *stop-place service crosswalks*, not boarding-point identity and not
routing eligibility. It intentionally preserves unresolved official timetable places so
missing coordinates cannot silently disappear from the inventory.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import pandas as pd

AS_OF = date(2026, 9, 5)
RESOLVED_PLACE_DECISIONS = {"SAME_STOP_PLACE_CONFIRMED", "SAME_STOP_PLACE_STRONG"}
UNRESOLVED_PLACE_DECISIONS = {
    "UNRESOLVED_HISTORICAL_PLACE_CROSSWALK",
    "OFFICIAL_STOP_PLACE_COORDINATE_UNRESOLVED",
    "AMBIGUOUS_GENERIC_TIMETABLE_PLACE",
}


def _split_ids(value: str) -> list[str]:
    if pd.isna(value) or not str(value).strip():
        return []
    return [part.strip() for part in str(value).split("|") if part.strip()]


def validate(args: argparse.Namespace) -> None:
    evidence = pd.read_csv(args.stop_service_evidence, dtype=str)
    temporal = pd.read_csv(args.line_temporal_evidence, dtype=str)
    crosswalk = pd.read_csv(args.crosswalk, dtype=str)
    master = pd.read_csv(args.master_identity_evidence, dtype=str)
    asf_places = pd.read_csv(args.asf_named_places, dtype=str)

    required_evidence = {
        "evidence_id", "line_id", "timetable_stop_name", "validity_start",
        "validity_end", "temporal_status_as_of_2026_09_05", "epistemic_status",
    }
    required_crosswalk = {
        "crosswalk_id", "evidence_id", "line_id", "timetable_stop_name",
        "target_operator_named_stop_place_id", "target_source_records",
        "stop_place_decision", "boarding_point_decision", "epistemic_status",
    }
    for frame, required, label in [
        (evidence, required_evidence, "service evidence"),
        (crosswalk, required_crosswalk, "service crosswalk"),
    ]:
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"{label} missing columns: {sorted(missing)}")

    if evidence["evidence_id"].duplicated().any():
        raise ValueError("Stop-service evidence IDs must be unique")
    if crosswalk["crosswalk_id"].duplicated().any() or crosswalk["evidence_id"].duplicated().any():
        raise ValueError("Crosswalk IDs and evidence IDs must be one-to-one and unique")

    evidence_ids = set(evidence["evidence_id"])
    crosswalk_ids = set(crosswalk["evidence_id"])
    if evidence_ids != crosswalk_ids:
        raise ValueError(
            f"Every stop-service evidence row requires exactly one crosswalk row; missing={sorted(evidence_ids-crosswalk_ids)} extra={sorted(crosswalk_ids-evidence_ids)}"
        )

    joined = evidence.merge(
        crosswalk,
        on=["evidence_id", "line_id", "timetable_stop_name"],
        how="inner",
        validate="one_to_one",
        suffixes=("_service", "_crosswalk"),
    )
    if len(joined) != len(evidence):
        raise ValueError("Crosswalk join changed stop-service evidence row count")

    # Every detailed timetable row currently in this layer is a published future row as
    # of 2026-09-05. This prevents silently calling the 2026/27 D148 and D184 PDFs current.
    starts = pd.to_datetime(joined["validity_start"], errors="raise").dt.date
    if not (starts > AS_OF).all():
        raise ValueError("Detailed 2026/27 Arriva stop evidence must start after audit as-of date")
    if not joined["temporal_status_as_of_2026_09_05"].eq("PUBLISHED_FUTURE_TIMETABLE").all():
        raise ValueError("Detailed 2026/27 stop rows must remain PUBLISHED_FUTURE_TIMETABLE")
    if not joined["epistemic_status_service"].eq("FACT").all():
        raise ValueError("Official timetable stop-name evidence must remain FACT")

    master_ids = set(master["master_source_record_id"])
    place_ids = set(asf_places["operator_named_stop_place_id"])
    bad_source_targets: list[dict] = []
    bad_place_targets: list[dict] = []
    for row in crosswalk.itertuples(index=False):
        for source_id in _split_ids(row.target_source_records):
            if source_id not in master_ids:
                bad_source_targets.append({"crosswalk_id": row.crosswalk_id, "source_id": source_id})
        if pd.notna(row.target_operator_named_stop_place_id) and str(row.target_operator_named_stop_place_id).strip():
            place_id = str(row.target_operator_named_stop_place_id).strip()
            if place_id not in place_ids:
                bad_place_targets.append({"crosswalk_id": row.crosswalk_id, "stop_place_id": place_id})
    if bad_source_targets:
        raise ValueError(f"Crosswalk references unknown master source records: {bad_source_targets}")
    if bad_place_targets:
        raise ValueError(f"Crosswalk references unknown ASF named stop places: {bad_place_targets}")

    allowed = RESOLVED_PLACE_DECISIONS | UNRESOLVED_PLACE_DECISIONS
    unknown_decisions = set(crosswalk["stop_place_decision"]) - allowed
    if unknown_decisions:
        raise ValueError(f"Unknown stop-place decision states: {sorted(unknown_decisions)}")

    unresolved = crosswalk[crosswalk["stop_place_decision"].isin(UNRESOLVED_PLACE_DECISIONS)].copy()
    resolved = crosswalk[crosswalk["stop_place_decision"].isin(RESOLVED_PLACE_DECISIONS)].copy()

    # An unresolved official location must not carry a target stop-place/source unless the
    # unresolved state is specifically the historical Centro/Paese review. This keeps
    # coordinate gaps visible rather than filling them by proximity or route sequence.
    coordinate_gaps = crosswalk[crosswalk["stop_place_decision"].eq("OFFICIAL_STOP_PLACE_COORDINATE_UNRESOLVED")]
    if coordinate_gaps["target_operator_named_stop_place_id"].fillna("").str.strip().ne("").any():
        raise ValueError("Coordinate-unresolved official stops cannot receive operator stop-place targets")
    if coordinate_gaps["target_source_records"].fillna("").str.strip().ne("").any():
        raise ValueError("Coordinate-unresolved official stops cannot receive master source targets")

    if crosswalk["boarding_point_decision"].str.contains("FINAL", case=False, na=False).any():
        raise ValueError("Service crosswalk must not finalize boarding-point identity")
    if not master["final_boarding_point_id"].fillna("").eq("").all():
        raise ValueError("Service crosswalk gate cannot consume a master with finalized boarding points")
    if not master["routing_terminal_eligibility_status"].eq("NOT_EVALUATED").all():
        raise ValueError("Service crosswalk gate must not select routing terminals")

    # Line-level temporal evidence must preserve the current-vs-future distinction.
    temporal_by_line_status = set(zip(temporal["line_id"], temporal["status"]))
    required_temporal = {
        ("D184", "LISTED_ON_CURRENT_SUMMER_2026_TIMETABLE_PAGE"),
        ("D185", "LISTED_ON_CURRENT_SUMMER_2026_TIMETABLE_PAGE"),
        ("D148", "NOT_LISTED_ON_CURRENT_SUMMER_2026_PAGE"),
        ("D184", "PUBLISHED_FOR_NEXT_WINTER_WINDOW"),
        ("D148", "PUBLISHED_FOR_NEXT_WINTER_WINDOW"),
        ("D185", "LISTED_ON_NEXT_WINTER_2026_27_INDEX"),
    }
    if not required_temporal.issubset(temporal_by_line_status):
        raise ValueError("Arriva line-level current/future temporal evidence is incomplete")

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    joined.to_csv(out / "arriva_stop_place_service_crosswalk_validated_gpt_v4.csv", index=False)
    unresolved.to_csv(out / "arriva_unresolved_official_stop_places_gpt_v4.csv", index=False)

    validation = {
        "status": "PASS_ARRIVA_SERVICE_STOP_PLACE_CROSSWALK",
        "as_of_date": AS_OF.isoformat(),
        "official_future_timing_point_rows": int(len(evidence)),
        "resolved_or_strong_stop_place_crosswalks": int(len(resolved)),
        "unresolved_stop_place_crosswalks": int(len(unresolved)),
        "official_coordinate_unresolved_count": int(len(coordinate_gaps)),
        "official_coordinate_unresolved_names": sorted(coordinate_gaps["timetable_stop_name"].tolist()),
        "boarding_point_finalizations_performed": 0,
        "routing_terminal_selected_count": 0,
        "line_current_summer_index_facts": sorted(
            temporal.loc[temporal["status"].eq("LISTED_ON_CURRENT_SUMMER_2026_TIMETABLE_PAGE"), "line_id"].tolist()
        ),
        "epistemic_note": (
            "Official timetable names are FACT service evidence. Cross-operator stop-place links are DERIVED unless explicitly unresolved. "
            "No timetable-name crosswalk finalizes a physical boarding point or routing terminal."
        ),
    }
    (out / "arriva_service_stop_crosswalk_validation_gpt_v4.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    audit = "outputs/phase2/network_design_method_audit_v3"
    base = f"{audit}/master_stop_inventory_gpt_v3"
    parser.add_argument("--stop-service-evidence", default=f"{audit}/arriva_published_stop_service_evidence_gpt_v4.csv")
    parser.add_argument("--line-temporal-evidence", default=f"{audit}/arriva_line_temporal_evidence_gpt_v4.csv")
    parser.add_argument("--crosswalk", default=f"{audit}/arriva_stop_place_service_crosswalk_gpt_v4.csv")
    parser.add_argument("--master-identity-evidence", default=f"{base}/master_stop_identity_evidence_gpt_v3.csv")
    parser.add_argument("--asf-named-places", default=f"{base}/asf_operator_named_stop_places_gpt_v3.csv")
    parser.add_argument("--output-dir", default=base)
    return parser.parse_args()


if __name__ == "__main__":
    validate(parse_args())
