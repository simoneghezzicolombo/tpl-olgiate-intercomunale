from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "outputs" / "phase2" / "network_design_method_audit_v3"
BASE = AUDIT / "master_stop_inventory_gpt_v3"
SCRIPT = ROOT / "scripts" / "phase2_validate_arriva_service_stop_crosswalk_gpt_v4.py"


def test_arriva_service_crosswalk_preserves_unresolved_official_stops(tmp_path: Path) -> None:
    subprocess.run([
        sys.executable,
        str(SCRIPT),
        "--stop-service-evidence", str(AUDIT / "arriva_published_stop_service_evidence_gpt_v4.csv"),
        "--line-temporal-evidence", str(AUDIT / "arriva_line_temporal_evidence_gpt_v4.csv"),
        "--crosswalk", str(AUDIT / "arriva_stop_place_service_crosswalk_gpt_v4.csv"),
        "--master-identity-evidence", str(BASE / "master_stop_identity_evidence_gpt_v3.csv"),
        "--asf-named-places", str(BASE / "asf_operator_named_stop_places_gpt_v3.csv"),
        "--output-dir", str(tmp_path),
    ], check=True, cwd=ROOT)

    validation = json.loads((tmp_path / "arriva_service_stop_crosswalk_validation_gpt_v4.json").read_text(encoding="utf-8"))
    unresolved = pd.read_csv(tmp_path / "arriva_unresolved_official_stop_places_gpt_v4.csv", dtype=str)
    validated = pd.read_csv(tmp_path / "arriva_stop_place_service_crosswalk_validated_gpt_v4.csv", dtype=str)

    assert validation["status"] == "PASS_ARRIVA_SERVICE_STOP_PLACE_CROSSWALK"
    assert validation["as_of_date"] == "2026-09-05"
    assert validation["official_future_timing_point_rows"] == 18
    assert validation["resolved_or_strong_stop_place_crosswalks"] == 14
    assert validation["unresolved_stop_place_crosswalks"] == 4
    assert validation["official_coordinate_unresolved_count"] == 2
    assert set(validation["official_coordinate_unresolved_names"]) == {
        "CALCO Località Cornello",
        "S. MARIA HOE' Tre Strade",
    }
    assert validation["boarding_point_finalizations_performed"] == 0
    assert validation["routing_terminal_selected_count"] == 0
    assert set(validation["line_current_summer_index_facts"]) == {"D184", "D185"}

    assert len(validated) == 18
    assert set(unresolved["evidence_id"]) == {"AR184_008", "AR148_002", "AR148_004", "AR148_006"}

    gaps = unresolved[unresolved["stop_place_decision"].eq("OFFICIAL_STOP_PLACE_COORDINATE_UNRESOLVED")]
    assert set(gaps["evidence_id"]) == {"AR148_002", "AR148_004"}
    assert gaps["target_source_records"].fillna("").eq("").all()
    assert gaps["target_operator_named_stop_place_id"].fillna("").eq("").all()

    # The generic BRIVIO timetable label cannot be used to undo the previously proven
    # physical distinction between the two historical 'capolinea' geometries.
    brivio = unresolved[unresolved["evidence_id"].eq("AR148_006")].iloc[0]
    assert brivio["stop_place_decision"] == "AMBIGUOUS_GENERIC_TIMETABLE_PLACE"
    assert pd.isna(brivio["target_source_records"]) or brivio["target_source_records"] == ""

    # Largo Pomeo/Pomea crosswalk targets the current ASF place only. The nearby frozen
    # 'Via Statale (edicola)' records remain outside this resolved service decision.
    pomea = validated[validated["evidence_id"].eq("AR148_009")].iloc[0]
    assert pomea["target_operator_named_stop_place_id"] == "SP_ASF::CALCO::CALCO_LARGO_POMEA"
    assert set(pomea["target_source_records"].split("|")) == {"ASF_OTP::CALCOA06", "ASF_OTP::CALCOR06"}
    assert "300089" not in pomea["target_source_records"]

    # The legacy Airuno label is physically in Brivio and is only corrected at passenger
    # stop-place/service-label level, not collapsed into one boarding point.
    elettroadda = validated[validated["evidence_id"].eq("AR148_007")].iloc[0]
    assert set(elettroadda["target_source_records"].split("|")) == {
        "FROZEN_GTFS::300527", "FROZEN_GTFS::L00527"
    }
    assert "UNRESOLVED" in elettroadda["boarding_point_decision"]
