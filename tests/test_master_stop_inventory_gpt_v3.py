from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_build_master_stop_inventory_gpt_v3.py"
MUNICIPALIZER = ROOT / "scripts" / "phase2_materialize_master_stop_municipalities_gpt_v3.py"
IDENTITY_CANDIDATES = ROOT / "scripts" / "phase2_build_stop_identity_candidates_gpt_v3.py"
FROZEN = ROOT / "outputs" / "phase2" / "existing_official_stops.csv"
AUDIT = ROOT / "outputs" / "phase2" / "network_design_method_audit_v3"
ASF = AUDIT / "asf_c146_directional_stops_subagent_v3.csv"
SPECIAL = AUDIT / "special_service_stop_evidence_gpt_v3.csv"
MANUAL = AUDIT / "manual_google_maps_asf_verifications_gpt_v3.csv"
BOUNDARIES = ROOT / "data" / "raw" / "boundaries" / "comuni_core_istat_2026.geojson"
CORE = {"Brivio", "Calco", "La Valletta Brianza", "Olgiate Molgora", "Santa Maria Hoè"}


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _build_master(output_dir: Path) -> None:
    subprocess.run([
        sys.executable, str(SCRIPT), "--frozen-existing", str(FROZEN), "--asf-c146", str(ASF),
        "--special-service", str(SPECIAL), "--manual-verifications", str(MANUAL),
        "--output-dir", str(output_dir),
    ], check=True, cwd=ROOT)


def _municipalize(output_dir: Path) -> None:
    subprocess.run([
        sys.executable, str(MUNICIPALIZER),
        "--master-source-records", str(output_dir / "master_stop_source_records_gpt_v3.csv"),
        "--boundaries", str(BOUNDARIES), "--output-dir", str(output_dir),
    ], check=True, cwd=ROOT)


def test_master_builder_preserves_sources_and_selects_no_terminals(tmp_path: Path) -> None:
    _build_master(tmp_path)
    master = pd.read_csv(tmp_path / "master_stop_source_records_gpt_v3.csv", dtype=str)
    validation = json.loads((tmp_path / "master_stop_inventory_validation_gpt_v3.json").read_text(encoding="utf-8"))
    assert len(master) == 105
    assert master["master_source_record_id"].is_unique
    assert master["source_family"].value_counts().to_dict() == {
        "FROZEN_GTFS_REFERENCE": 66, "ASF_OPERATOR_OTP": 38, "SPECIAL_SERVICE_EVIDENCE": 1,
    }
    assert master["routing_terminal_eligibility_status"].eq("NOT_EVALUATED").all()
    assert validation["routing_terminal_selected_count"] == 0
    assert validation["boarding_point_conflation_performed"] is False
    assert validation["stop_place_finalization_performed"] is False
    assert validation["legacy_40m_cluster_used_as_boarding_identity"] is False
    frozen = master[master["source_family"].eq("FROZEN_GTFS_REFERENCE")]
    assert frozen["physical_municipality_exact"].isna().all()
    assert not (frozen["boarding_point_id_candidate"].fillna("") == frozen["legacy_physical_cluster_id"].fillna("")).any()
    asf = master[master["source_family"].eq("ASF_OPERATOR_OTP")]
    assert asf["boarding_point_id_candidate"].is_unique
    assert asf["boarding_point_assignment_status"].eq("DIRECTIONAL_OPERATOR_RECORD_DISTINCT_CANDIDATE").all()


def test_exact_istat_municipality_materialization(tmp_path: Path) -> None:
    _build_master(tmp_path)
    _municipalize(tmp_path)
    master = pd.read_csv(tmp_path / "master_stop_source_records_municipalized_gpt_v3.csv", dtype=str)
    validation = json.loads((tmp_path / "master_stop_municipality_validation_gpt_v3.json").read_text(encoding="utf-8"))
    assert len(master) == 105
    assert master["master_source_record_id"].is_unique
    assert master["physical_municipality_exact"].notna().all()
    assert set(master["physical_municipality_exact"]).issubset(CORE | {"OUTSIDE_CORE"})
    assert master["municipality_assignment_method"].eq("ISTAT_2026_EXACT_POINT_IN_POLYGON").all()
    assert master["routing_terminal_eligibility_status"].eq("NOT_EVALUATED").all()
    assert validation["source_records_count"] == 105
    assert validation["routing_terminal_selected_count"] == 0
    assert validation["asf_containment_conflict_count"] == 0
    assert validation["core_polygon_assigned_count"] + validation["outside_core_count"] == 105
    asf = master[master["source_family"].eq("ASF_OPERATOR_OTP")]
    assert asf["municipality_comparison_status"].eq("AGREES_WITH_PHYSICAL_CONTAINMENT").all()
    indexed = master.set_index("master_source_record_id")
    for stop_id in ("300501", "300863", "300908"):
        row = indexed.loc[f"FROZEN_GTFS::{stop_id}"]
        assert row["physical_municipality_exact"] == "OUTSIDE_CORE"
        assert row["municipality_comparison_status"] == "REPORTED_CONTEXT_BUT_PHYSICALLY_OUTSIDE_CORE"
    special = master[master["source_family"].eq("SPECIAL_SERVICE_EVIDENCE")].iloc[0]
    assert special["physical_municipality_exact"] == "Olgiate Molgora"


def test_identity_candidate_edges_are_complete_and_non_decisional(tmp_path: Path) -> None:
    _build_master(tmp_path)
    _municipalize(tmp_path)
    subprocess.run([
        sys.executable, str(IDENTITY_CANDIDATES),
        "--master-municipalized", str(tmp_path / "master_stop_source_records_municipalized_gpt_v3.csv"),
        "--output-dir", str(tmp_path),
    ], check=True, cwd=ROOT)

    master = pd.read_csv(tmp_path / "master_stop_source_records_municipalized_gpt_v3.csv", dtype=str)
    directional = pd.read_csv(tmp_path / "asf_directional_pair_distances_gpt_v3.csv", dtype=str)
    nearest = pd.read_csv(tmp_path / "asf_frozen_identity_candidates_gpt_v3.csv", dtype=str)
    aliases = pd.read_csv(tmp_path / "frozen_crossfeed_alias_candidates_gpt_v3.csv", dtype=str)
    validation = json.loads((tmp_path / "stop_identity_candidate_validation_gpt_v3.json").read_text(encoding="utf-8"))

    asf_ids = set(master.loc[master["source_family"].eq("ASF_OPERATOR_OTP"), "master_source_record_id"])
    represented = set(directional["source_record_a"].dropna()) | set(directional["source_record_b"].dropna())
    assert represented == asf_ids
    assert len(asf_ids) == 38
    assert directional["boarding_point_identity_status"].isin({
        "DISTINCT_DIRECTIONAL_SOURCE_RECORDS_NO_AUTO_MERGE", "SOURCE_RECORD_PRESERVED_NO_MERGE"
    }).all()
    assert nearest["identity_decision"].eq("UNRESOLVED_NO_AUTO_MERGE").all()
    assert aliases["boarding_point_identity_decision"].eq("NOT_FINALIZED").all()
    assert validation["boarding_point_merges_performed"] == 0
    assert validation["stop_place_finalizations_performed"] == 0
    assert validation["routing_terminal_selected_count"] == 0
    assert validation["asf_source_records_count"] == 38

    # The current operator code/name correction must remain visible as review evidence,
    # never as an automatic merge with the old Via Statale/edicola record.
    calco = nearest[(nearest["asf_code"].eq("CALCOA06")) & (nearest["frozen_native_id"].eq("300089"))]
    assert len(calco) == 1
    assert 5.0 < float(calco.iloc[0]["distance_m"]) < 20.0
    assert calco.iloc[0]["identity_decision"] == "UNRESOLVED_NO_AUTO_MERGE"

    # Strong legacy cross-feed aliases are only candidates and cannot finalize physical identity.
    strong = aliases[aliases["alias_candidate_status"].eq("STRONG_CROSS_FEED_SOURCE_ALIAS_CANDIDATE")]
    assert not strong.empty
    assert strong["boarding_point_identity_decision"].eq("NOT_FINALIZED").all()


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
        distance = _haversine_m(float(old["stop_lat"]), float(old["stop_lon"]), float(current["lat"]), float(current["lon"]))
        assert distance > 300.0
    manual = pd.read_csv(MANUAL, dtype=str).set_index("record_id")
    assert manual.loc["GM006", "interpretation"] == "LIKELY_MAPS_FROZEN_SOURCE_ALIAS_ASF_CARTELLO_PAESE_DISTINCT_LOCATION"
