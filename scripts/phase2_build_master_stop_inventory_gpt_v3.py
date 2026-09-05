#!/usr/bin/env python3
"""Build a source-preserving Phase-2 master stop inventory.

This builder deliberately does NOT choose routing terminals, merge boarding points by
distance, or reinterpret legacy 40 m clusters as physical-stop identity.

Inputs are evidence layers:
- frozen Arriva/LineeLecco routing/context stop universe;
- current ASF C146 OTP directional stop records;
- separately classified special-service boarding-point evidence;
- optional manual verification file used only as review evidence.

Outputs are neutral upstream artifacts for the stop-inventory workstream.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd


CORE_MUNICIPALITIES = {
    "Brivio",
    "Calco",
    "La Valletta Brianza",
    "Olgiate Molgora",
    "Santa Maria Hoè",
}


def _text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _slug(value: str) -> str:
    value = value.upper()
    value = (
        value.replace("À", "A")
        .replace("È", "E")
        .replace("É", "E")
        .replace("Ì", "I")
        .replace("Ò", "O")
        .replace("Ù", "U")
    )
    value = re.sub(r"[^A-Z0-9]+", "_", value).strip("_")
    return value or "UNNAMED"


def _frozen_rows(frame: pd.DataFrame) -> list[dict]:
    required = {
        "stop_id",
        "stop_name",
        "stop_lat",
        "stop_lon",
        "PRO_COM_T",
        "COMUNE",
        "physical_cluster_id",
        "epistemic_status",
        "source",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Frozen stop universe missing columns: {sorted(missing)}")

    rows: list[dict] = []
    for r in frame.itertuples(index=False):
        native_id = _text(r.stop_id)
        rows.append(
            {
                "master_source_record_id": f"FROZEN_GTFS::{native_id}",
                "source_family": "FROZEN_GTFS_REFERENCE",
                "source_record_native_id": native_id,
                "operator": "ARRIVA_LINEELECCO_REFERENCE_UNIVERSE",
                "route_id": _text(getattr(r, "official_routes_reference_gtfs", "")),
                "source_stop_name": _text(r.stop_name),
                "lat": float(r.stop_lat),
                "lon": float(r.stop_lon),
                "municipality_reported": _text(r.COMUNE),
                "physical_municipality_exact": "",
                "analysis_context_role": "FROZEN_ROUTING_CONTEXT_UNIVERSE",
                "source_temporal_status": "REFERENCE_PERIOD_2025_26_NOT_CURRENT_SERVICE",
                "service_class": "CONVENTIONAL_TPL_REFERENCE",
                "legacy_physical_cluster_id": _text(r.physical_cluster_id),
                "legacy_pro_com_t": _text(r.PRO_COM_T),
                "source_provenance_status": _text(r.epistemic_status),
                "boarding_point_id_candidate": f"BP_SRC_FROZEN_{_slug(native_id)}",
                "boarding_point_assignment_status": "SOURCE_PRESERVED_IDENTITY_NOT_CONFLATED",
                "stop_place_id_candidate": "",
                "stop_place_assignment_status": "NOT_ASSIGNED_FROM_LEGACY_40M_CLUSTER",
                "routing_terminal_eligibility_status": "NOT_EVALUATED",
                "notes": (
                    "Legacy physical_cluster_id retained only as provenance/candidate-neighbourhood "
                    "information. PRO_COM_T is not strict municipality truth."
                ),
            }
        )
    return rows


def _asf_rows(frame: pd.DataFrame) -> list[dict]:
    required = {
        "route_id",
        "stop_code",
        "stop_name",
        "lat",
        "lon",
        "municipality_exact",
        "source_status",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"ASF evidence missing columns: {sorted(missing)}")

    rows: list[dict] = []
    for r in frame.itertuples(index=False):
        code = _text(r.stop_code)
        stop_name = _text(r.stop_name)
        municipality = _text(r.municipality_exact)
        if municipality and municipality not in CORE_MUNICIPALITIES:
            raise ValueError(f"Unexpected ASF municipality_exact={municipality!r} for {code}")
        rows.append(
            {
                "master_source_record_id": f"ASF_OTP::{code}",
                "source_family": "ASF_OPERATOR_OTP",
                "source_record_native_id": code,
                "operator": "ASF_AUTOLINEE",
                "route_id": _text(r.route_id),
                "source_stop_name": stop_name,
                "lat": float(r.lat),
                "lon": float(r.lon),
                "municipality_reported": municipality,
                "physical_municipality_exact": municipality,
                "analysis_context_role": "CORE_CURRENT_OPERATOR_STOP",
                "source_temporal_status": "CURRENT_2026_OPERATOR_OTP",
                "service_class": "CONVENTIONAL_TPL_CURRENT_OPERATOR",
                "legacy_physical_cluster_id": "",
                "legacy_pro_com_t": "",
                "source_provenance_status": _text(r.source_status),
                "boarding_point_id_candidate": f"BP_SRC_ASF_{_slug(code)}",
                "boarding_point_assignment_status": "DIRECTIONAL_OPERATOR_RECORD_DISTINCT_CANDIDATE",
                "stop_place_id_candidate": f"SP_CAND_ASF_{_slug(stop_name)}",
                "stop_place_assignment_status": "OPERATOR_NAME_GROUP_CANDIDATE_NOT_BOARDING_IDENTITY",
                "routing_terminal_eligibility_status": "NOT_EVALUATED",
                "notes": (
                    "A/R operator rows remain distinct boarding-point candidates even when close. "
                    "Stop-place candidate is name-based and non-decisional."
                ),
            }
        )
    return rows


def _special_rows(frame: pd.DataFrame) -> list[dict]:
    required = {
        "service_id",
        "stop_name",
        "stop_class",
        "municipality",
        "lat",
        "lon",
        "coordinate_provenance",
        "service_status",
        "epistemic_status",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Special-service evidence missing columns: {sorted(missing)}")

    rows: list[dict] = []
    for idx, r in enumerate(frame.itertuples(index=False), start=1):
        service_id = _text(r.service_id)
        stop_name = _text(r.stop_name)
        native_id = f"{service_id}::{idx:03d}"
        rows.append(
            {
                "master_source_record_id": f"SPECIAL_SERVICE::{native_id}",
                "source_family": "SPECIAL_SERVICE_EVIDENCE",
                "source_record_native_id": native_id,
                "operator": _text(getattr(r, "service_authority", "")),
                "route_id": service_id,
                "source_stop_name": stop_name,
                "lat": float(r.lat),
                "lon": float(r.lon),
                "municipality_reported": _text(r.municipality),
                "physical_municipality_exact": "",
                "analysis_context_role": "SPECIAL_SERVICE_SEPARATE_CLASS",
                "source_temporal_status": _text(r.service_status),
                "service_class": _text(r.stop_class),
                "legacy_physical_cluster_id": "",
                "legacy_pro_com_t": "",
                "source_provenance_status": _text(r.epistemic_status),
                "boarding_point_id_candidate": f"BP_SRC_SPECIAL_{_slug(native_id)}",
                "boarding_point_assignment_status": "SOURCE_PRESERVED_SPECIAL_SERVICE_CANDIDATE",
                "stop_place_id_candidate": f"SP_CAND_SPECIAL_{_slug(stop_name)}",
                "stop_place_assignment_status": "SPECIAL_SERVICE_LOCATION_CANDIDATE",
                "routing_terminal_eligibility_status": "NOT_EVALUATED",
                "notes": (
                    f"Coordinate provenance={_text(r.coordinate_provenance)}. "
                    "Do not reinterpret as standard TPL infrastructure without separate evidence."
                ),
            }
        )
    return rows


def build(args: argparse.Namespace) -> None:
    frozen = pd.read_csv(args.frozen_existing, dtype={"stop_id": str, "PRO_COM_T": str})
    asf = pd.read_csv(args.asf_c146, dtype=str)
    special = pd.read_csv(args.special_service, dtype=str)

    rows = _frozen_rows(frozen) + _asf_rows(asf) + _special_rows(special)
    master = pd.DataFrame(rows)

    if master["master_source_record_id"].duplicated().any():
        dup = master.loc[
            master["master_source_record_id"].duplicated(keep=False),
            "master_source_record_id",
        ].tolist()
        raise ValueError(f"Duplicate master source-record IDs: {dup}")

    if master[["lat", "lon"]].isna().any().any():
        raise ValueError("Master source records contain null coordinates")

    if not master["routing_terminal_eligibility_status"].eq("NOT_EVALUATED").all():
        raise ValueError("Master inventory must not select routing terminals")

    # Legacy 40 m clusters are never copied into boarding-point identity.
    frozen_mask = master["source_family"].eq("FROZEN_GTFS_REFERENCE")
    if (
        master.loc[frozen_mask, "boarding_point_id_candidate"]
        == master.loc[frozen_mask, "legacy_physical_cluster_id"]
    ).any():
        raise ValueError("Legacy physical clusters leaked into boarding-point identity")

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    master_path = out / "master_stop_source_records_gpt_v3.csv"
    master.to_csv(master_path, index=False)

    review_count = 0
    if args.manual_verifications and Path(args.manual_verifications).exists():
        manual = pd.read_csv(args.manual_verifications, dtype=str)
        manual.to_csv(out / "master_manual_identity_review_gpt_v3.csv", index=False)
        review_count = int(len(manual))

    by_source = (
        master.groupby("source_family", dropna=False)
        .size()
        .rename("source_records")
        .reset_index()
        .sort_values("source_family")
    )
    by_source.to_csv(out / "master_stop_source_counts_gpt_v3.csv", index=False)

    validation = {
        "status": "PASS_SOURCE_PRESERVING_MASTER_BUILD",
        "source_records_count": int(len(master)),
        "source_records_by_family": {
            row.source_family: int(row.source_records)
            for row in by_source.itertuples(index=False)
        },
        "manual_identity_review_rows": review_count,
        "routing_terminal_selected_count": int(
            (~master["routing_terminal_eligibility_status"].eq("NOT_EVALUATED")).sum()
        ),
        "boarding_point_conflation_performed": False,
        "stop_place_finalization_performed": False,
        "legacy_40m_cluster_used_as_boarding_identity": False,
        "physical_municipality_exact_note": (
            "ASF OTP rows carry polygon-assigned exact municipality from their evidence layer. "
            "Frozen/context and local-coordinate special-service rows remain blank until a dedicated "
            "ISTAT polygon containment materialization is run."
        ),
        "downstream_contract": (
            "This artifact is neutral upstream evidence and MUST NOT be consumed as a routing-terminal list."
        ),
    }
    (out / "master_stop_inventory_validation_gpt_v3.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--frozen-existing",
        default="outputs/phase2/existing_official_stops.csv",
    )
    parser.add_argument(
        "--asf-c146",
        default="outputs/phase2/network_design_method_audit_v3/asf_c146_directional_stops_subagent_v3.csv",
    )
    parser.add_argument(
        "--special-service",
        default="outputs/phase2/network_design_method_audit_v3/special_service_stop_evidence_gpt_v3.csv",
    )
    parser.add_argument(
        "--manual-verifications",
        default="outputs/phase2/network_design_method_audit_v3/manual_google_maps_asf_verifications_gpt_v3.csv",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/phase2/network_design_method_audit_v3/master_stop_inventory_gpt_v3",
    )
    return parser.parse_args()


if __name__ == "__main__":
    build(parse_args())
