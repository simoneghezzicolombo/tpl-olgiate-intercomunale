from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_build_master_stop_inventory_gpt_v3.py"
FROZEN = ROOT / "outputs" / "phase2" / "existing_official_stops.csv"
AUDIT = ROOT / "outputs" / "phase2" / "network_design_method_audit_v3"
ASF = AUDIT / "asf_c146_directional_stops_subagent_v3.csv"
SPECIAL = AUDIT / "special_service_stop_evidence_gpt_v3.csv"
MANUAL = AUDIT / "manual_google_maps_asf_verifications_gpt_v3.csv"


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2.0) ** 2
    )
    return 2.0 * radius * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def test_master_builder_preserves_sources_and_selects_no_terminals(tmp_path: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--frozen-existing",
            str(FROZEN),
            "--asf-c146",
            str(ASF),
            "--special-service",
            str(SPECIAL),
            "--manual-verifications",
            str(MANUAL),
            "--output-dir",
            str(tmp_path),
        ],
        check=True,
        cwd=ROOT,
    )

    master = pd.read_csv(tmp_path / "master_stop_source_records_gpt_v3.csv", dtype=str)
    validation = json.loads(
        (tmp_path / "master_stop_inventory_validation_gpt_v3.json").read_text(
            encoding="utf-8"
        )
    )

    # Counts are frozen against the actual GitHub inputs, not a remembered V3 summary.
    assert len(master) == 105
    assert master["master_source_record_id"].is_unique
    assert master["source_family"].value_counts().to_dict() == {
        "FROZEN_GTFS_REFERENCE": 66,
        "ASF_OPERATOR_OTP": 38,
        "SPECIAL_SERVICE_EVIDENCE": 1,
    }
    assert master["routing_terminal_eligibility_status"].eq("NOT_EVALUATED").all()
    assert validation["routing_terminal_selected_count"] == 0
    assert validation["boarding_point_conflation_performed"] is False
    assert validation["stop_place_finalization_performed"] is False
    assert validation["legacy_40m_cluster_used_as_boarding_identity"] is False

    frozen = master[master["source_family"].eq("FROZEN_GTFS_REFERENCE")]
    assert frozen["physical_municipality_exact"].isna().all()
    assert not (
        frozen["boarding_point_id_candidate"].fillna("")
        == frozen["legacy_physical_cluster_id"].fillna("")
    ).any()

    asf = master[master["source_family"].eq("ASF_OPERATOR_OTP")]
    assert asf["boarding_point_id_candidate"].is_unique
    assert asf["boarding_point_assignment_status"].eq(
        "DIRECTIONAL_OPERATOR_RECORD_DISTINCT_CANDIDATE"
    ).all()


def test_calcoa06_name_conflict_is_not_auto_conflated() -> None:
    manual = pd.read_csv(MANUAL, dtype=str).set_index("record_id")
    row = manual.loc["GM001"]
    assert row["user_transcribed_asf_code_claim"] == "CALCOA06"
    assert row["interpretation"] == "CODE_CANONICAL_NAME_CONFLICT_PHYSICAL_IDENTITY_UNRESOLVED"

    asf = pd.read_csv(ASF, dtype=str).set_index("stop_code")
    assert asf.loc["CALCOA06", "stop_name"] == "Calco - Largo Pomea"


def test_beverate_cartello_paese_is_not_frozen_300398() -> None:
    frozen = pd.read_csv(FROZEN, dtype={"stop_id": str}).set_index("stop_id")
    asf = pd.read_csv(ASF, dtype=str).set_index("stop_code")

    old = frozen.loc["300398"]
    for code in ("BRIVIA05", "BRIVIR05"):
        current = asf.loc[code]
        distance = _haversine_m(
            float(old["stop_lat"]),
            float(old["stop_lon"]),
            float(current["lat"]),
            float(current["lon"]),
        )
        assert distance > 300.0

    manual = pd.read_csv(MANUAL, dtype=str).set_index("record_id")
    assert manual.loc["GM006", "interpretation"] == (
        "LIKELY_MAPS_FROZEN_SOURCE_ALIAS_ASF_CARTELLO_PAESE_DISTINCT_LOCATION"
    )
