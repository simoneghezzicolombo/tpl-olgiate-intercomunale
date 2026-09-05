from __future__ import annotations

import pandas as pd

from src.phase2_alpha_stop_inventory import build_alpha_stop_inventory, canonical_municipality


def foundation_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "stop_foundation_id": "existing:EX_1",
                "physical_cluster_id": "EX_1",
                "stop_class": "EXISTING_OFFICIAL",
                "human_label": "Calco - via test",
                "municipality": "Calco",
                "lat": "45.72",
                "lon": "9.41",
                "evidence_status": "FACT_OFFICIAL_GTFS_REFERENCE_PERIOD_NOT_CURRENT_SERVICE",
                "field_check_status": "NOT_REQUIRED_FOR_EXISTING_IDENTITY",
                "current_d184_d185_physical_stop": "false",
                "current_routes": "D150",
                "human_identity_ready": "true",
                "source_lineage": "fixture",
            },
            {
                "stop_foundation_id": "proposed:P1",
                "physical_cluster_id": "",
                "stop_class": "PROPOSED_HYPOTHESIS",
                "human_label": "candidate",
                "municipality": "Calco",
                "lat": "45.73",
                "lon": "9.42",
                "evidence_status": "HYPOTHESIS",
                "field_check_status": "FIELD_CHECK_PENDING",
                "current_d184_d185_physical_stop": "false",
                "current_routes": "",
                "human_identity_ready": "true",
                "source_lineage": "fixture",
            },
        ]
    )


def routing_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "source_anchor_id": "existing:EX_1",
                "graph_node_id": "n:1:1",
                "snap_distance_m": "5",
                "snap_status": "ROUTE_READY_LE_75M",
                "route_ready": "true",
                "physical_status": "EXISTING_OFFICIAL_STOP_CLUSTER",
                "candidate_status": "NOT_PROPOSED",
                "epoch_id": "gate-d-fixture",
            },
            {
                "source_anchor_id": "proposed:P1",
                "graph_node_id": "n:2:2",
                "snap_distance_m": "4",
                "snap_status": "ROUTE_READY_LE_75M",
                "route_ready": "true",
                "physical_status": "CANDIDATE",
                "candidate_status": "FIELD_CHECK_PENDING",
                "epoch_id": "gate-d-fixture",
            },
        ]
    )


def test_reference_period_existing_official_stop_is_eligible():
    out = build_alpha_stop_inventory(foundation_fixture(), routing_fixture())
    row = out.loc[out["alpha_stop_id"] == "existing:EX_1"].iloc[0]
    assert bool(row["alpha_design_eligible"]) is True
    assert row["infrastructure_reuse_scope"] == "REFERENCE_PERIOD_OFFICIAL_STOP_REUSE_CANDIDATE"


def test_proposed_stop_never_enters_first_canonical_universe():
    out = build_alpha_stop_inventory(foundation_fixture(), routing_fixture())
    row = out.loc[out["alpha_stop_id"] == "proposed:P1"].iloc[0]
    assert bool(row["alpha_design_eligible"]) is False
    assert "NOT_EXISTING_OFFICIAL" in row["alpha_eligibility_reason"]


def test_route_ready_and_human_identity_are_hard_epistemic_guards():
    f = foundation_fixture().iloc[[0]].copy()
    r = routing_fixture().iloc[[0]].copy()
    r.loc[:, "route_ready"] = "false"
    out = build_alpha_stop_inventory(f, r)
    assert bool(out.iloc[0]["alpha_design_eligible"]) is False
    assert "NOT_ROUTE_READY_LE_75M" in out.iloc[0]["alpha_eligibility_reason"]


def test_historical_mojibake_maps_to_policy_municipality():
    assert canonical_municipality("Santa Maria HoÃ¨") == "Santa Maria Hoè"
