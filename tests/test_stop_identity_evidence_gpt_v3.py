from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs" / "phase2" / "network_design_method_audit_v3" / "master_stop_inventory_gpt_v3"


def test_identity_evidence_materialization_contract() -> None:
    master = pd.read_csv(BASE / "master_stop_identity_evidence_gpt_v3.csv", dtype=str)
    aliases = pd.read_csv(BASE / "source_alias_groups_gpt_v3.csv", dtype=str)
    places = pd.read_csv(BASE / "asf_operator_named_stop_places_gpt_v3.csv", dtype=str)
    validation = json.loads((BASE / "stop_identity_evidence_validation_gpt_v3.json").read_text(encoding="utf-8"))

    assert len(master) == 105
    assert master["master_source_record_id"].is_unique
    assert validation["status"] == "PASS_IDENTITY_EVIDENCE_MATERIALIZATION"
    assert validation["distinct_source_alias_groups"] == 87
    assert validation["strong_crossfeed_alias_groups"] == 18
    assert validation["source_records_in_strong_alias_groups"] == 36
    assert validation["asf_source_records_count"] == 38
    assert validation["asf_operator_named_stop_places_count"] == 20
    assert validation["asf_two_record_named_stop_places"] == 18
    assert validation["asf_single_record_named_stop_places"] == 2
    assert validation["final_boarding_points_assigned"] == 0
    assert validation["final_cross_operator_stop_places_assigned"] == 0
    assert validation["routing_terminal_selected_count"] == 0

    strong = aliases[aliases["source_alias_group_status"].eq("DERIVED_STRONG_CROSS_FEED_SOURCE_ALIAS_GROUP")]
    assert len(strong) == 18
    assert strong["source_records"].astype(int).eq(2).all()
    assert strong["source_alias_group_epistemic_status"].eq("DERIVED").all()

    asf_rows = master[master["source_family"].eq("ASF_OPERATOR_OTP")]
    assert asf_rows["operator_named_stop_place_id"].fillna("").ne("").all()
    assert asf_rows["operator_named_stop_place_status"].eq("FACT_SAME_ASF_OPERATOR_NAMED_STOP_PLACE").all()
    assert asf_rows["final_boarding_point_id"].fillna("").eq("").all()
    assert asf_rows["final_stop_place_id"].fillna("").eq("").all()

    singles = places[places["source_records"].astype(int).eq(1)]
    assert set(singles["source_codes"]) == {"BRIVIR06", "CALCOA09"}

    # ROVAGA01/ROVAGR01 differ only by punctuation in source naming and must resolve
    # to one operator-named place, not two phantom singletons.
    rovagnate = places[places["source_codes"].str.contains("ROVAGA01", na=False)]
    assert len(rovagnate) == 1
    assert rovagnate.iloc[0]["source_codes"] == "ROVAGA01|ROVAGR01"
    assert int(rovagnate.iloc[0]["source_records"]) == 2
