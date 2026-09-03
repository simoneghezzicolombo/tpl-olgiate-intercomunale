from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/phase2"


def test_phase2_demand_profile_partition() -> None:
    corridor = pd.read_csv(OUT / "od_2021_corridor_summary.csv", dtype={"procom": str})
    assert len(corridor) == 6
    all_core = corridor[corridor["procom"] == "ALL_CORE"].iloc[0]
    assert int(all_core["resident_workers"]) == 8754
    assert int(all_core["self_workers"]) == 1315
    assert (
        int(all_core["self_workers"])
        + int(all_core["other_core_workers"])
        + int(all_core["s8_direct_workers"])
        + int(all_core["other_external_workers"])
        == 8754
    )


def test_phase2_destination_ranking_is_complete_and_unique() -> None:
    destinations = pd.read_csv(
        OUT / "od_2021_destinations_by_origin.csv",
        dtype={"procom_res": str, "procom_lav": str},
    )
    assert set(destinations["procom_res"]) == {"097010", "097012", "097058", "097074", "097092"}
    assert not destinations.duplicated(["procom_res", "procom_lav"]).any()
    assert set(destinations["category"]).issubset({"SELF", "OTHER_CORE", "S8_DIRECT", "OTHER_EXTERNAL"})
    for _, group in destinations.groupby("procom_res"):
        assert list(group["rank"]) == list(range(1, len(group) + 1))
        assert abs(float(group["share_of_origin_pct"].sum()) - 100.0) < 1e-5


def test_s8_municipalities_come_from_gtfs_spatial_join() -> None:
    stations = pd.read_csv(OUT / "s8_station_municipalities.csv", dtype={"procom": str})
    assert not stations.empty
    assert stations["procom"].notna().all()
    names = set(stations["stop_name"].astype(str).str.upper())
    assert any("OLGIATE" in name for name in names)
    assert any("LECCO" in name for name in names)
    assert any("MILANO" in name for name in names)


def test_validation_contract_and_2011_deferral() -> None:
    meta = json.loads((OUT / "od_2021_demand_profile_validation.json").read_text(encoding="utf-8"))
    assert meta["source_scope"] == "ISTAT_2021_WORK_COMMUTING_ONLY"
    assert meta["resident_workers"] == 8754
    assert meta["self_workers"] == 1315
    assert meta["comparison_2011_status"] == "DEFERRED_PENDING_NORMALIZATION_AUDIT"
    assert meta["n_s8_municipalities"] > 0
    assert meta["s8_direct_workers"] >= 0


def test_generated_doc_is_explicit_about_limits() -> None:
    text = (ROOT / "docs/PHASE2_DEMAND_PROFILE_2021.md").read_text(encoding="utf-8")
    assert "per lavoro" in text
    assert "Non è una stima della quota modale ferroviaria" in text
    assert "non viene ancora calcolato" in text
