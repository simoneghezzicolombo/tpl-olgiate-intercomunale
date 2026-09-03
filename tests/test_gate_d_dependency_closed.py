from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd

MODULE_PATH = Path("scripts/gate_d_structural_candidates_v3.py")
spec = importlib.util.spec_from_file_location("gate_d_structural_candidates_v3", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_gate_b_and_c_are_recorded_as_formally_pass_dependencies():
    assert module.GATE_B_VALIDATED_COMMIT == "55d726564e13acca55ce563cc911263ac513acb0"
    assert module.GATE_C_FINAL_COMMIT == "dcc3e75ae3b4f4ea5170f48e85345b83620c5536"


def test_calco_superiore_anchor_is_assumption_resolved_from_osm_name_not_coordinates():
    spec = module.base.ANCHOR_SPECS["CALCO_SUPERIORE"]
    assert spec == {"type": "osm_named_road", "name": "Via Calco Superiore"}
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert '"lat"' not in text
    assert '"lon"' not in text


def test_calco_superiore_is_bidirectionally_tested_as_sensitivity():
    selected = [
        candidate
        for candidate in module.base.CANDIDATES
        if candidate["family"] == "EAST_CALCO_SUPERIORE_SENSITIVITY"
    ]
    assert {candidate["direction"] for candidate in selected} == {"CW", "CCW"}
    assert all("CALCO_SUPERIORE" in candidate["anchors"] for candidate in selected)


def test_non_loop_existing_corridor_alternatives_are_present():
    selected = {
        candidate["candidate_id"]: candidate
        for candidate in module.base.CANDIDATES
        if candidate["family"] == "NON_LOOP_EXISTING_CORRIDOR"
    }
    assert set(selected) == {
        "WEST_D184_CORRIDOR_OUT_AND_BACK",
        "EAST_D185_CORRIDOR_OUT_AND_BACK",
    }
    assert all(candidate["direction"] == "OUT_AND_BACK" for candidate in selected.values())
    assert all(
        module.base.ANCHOR_SPECS[anchor]["type"] in {"gtfs_stop", "rail_gtfs_stop"}
        for candidate in selected.values()
        for anchor in set(candidate["anchors"])
    )


def test_dependency_closed_summary_does_not_claim_a_route_recommendation():
    metrics = pd.DataFrame(
        [
            {"candidate_id": "WEST_COMPACT_MONDONICO_CW", "route_km": 10.0, "pure_running_minutes": 20.0},
            {"candidate_id": "WEST_COMPACT_MONDONICO_CCW", "route_km": 10.1, "pure_running_minutes": 20.1},
            {"candidate_id": "EAST_COMPACT_ARLATE_CW", "route_km": 13.0, "pure_running_minutes": 25.0},
            {"candidate_id": "EAST_COMPACT_ARLATE_CCW", "route_km": 13.1, "pure_running_minutes": 25.1},
            {"candidate_id": "WEST_RAVELLINO_EXTENSION", "route_km": 14.0, "pure_running_minutes": 30.0},
            {"candidate_id": "EAST_CAPRINO_CELANA_EXTENSION", "route_km": 20.0, "pure_running_minutes": 40.0},
            {"candidate_id": "WEST_SAN_ZENO_SENSITIVITY", "route_km": 11.0, "pure_running_minutes": 22.0},
            {"candidate_id": "EAST_CALCO_SUPERIORE_SENSITIVITY_CW", "route_km": 16.0, "pure_running_minutes": 30.0},
            {"candidate_id": "EAST_CALCO_SUPERIORE_SENSITIVITY_CCW", "route_km": 15.7, "pure_running_minutes": 29.5},
            {"candidate_id": "WEST_D184_CORRIDOR_OUT_AND_BACK", "route_km": 18.0, "pure_running_minutes": 36.0},
            {"candidate_id": "EAST_D185_CORRIDOR_OUT_AND_BACK", "route_km": 17.0, "pure_running_minutes": 34.0},
        ]
    )
    summary = module.build_summary(metrics, {}, {}, {})
    assert summary["gate_b_status"] == "PASS"
    assert summary["gate_c_status"] == "PASS"
    assert summary["gate_c_dependency"] == "RESOLVED"
    assert summary["non_loop_alternatives_status"] == "TESTED_SAME_GRAPH_NOT_FIGURE8"
    assert summary["verdict"] == "READY_FOR_GATE_D_REVIEW"
    assert "recommend" not in summary["verdict"].lower()


def test_no_random_or_precomputed_route_metrics_in_v3_wrapper():
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "np.random" not in text
    assert "route_km\":" not in text
    assert "pure_running_minutes\":" not in text
