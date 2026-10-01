from __future__ import annotations

import math

import pytest

from src.phase2_current_service_baseline_v4 import (
    CURRENT_SERVICE_EVIDENCE_IS_RIDERSHIP,
    FUTURE_2026_09_14_USED_AS_CURRENT,
    OLGIATE_DIAGNOSTIC_IN_CANDIDATE_OPTIMISATION,
    PDF_TIMING_ROWS_TREATED_AS_COMPLETE_STOP_UNIVERSE,
    StopForClustering,
    activation_status,
    cluster_stop_records,
    deterministic_pattern_id,
    normalise_official_name,
    validate_official_coordinate,
)
from scripts.phase2_build_current_service_access_baseline_v4 import (
    build_olgiate_diagnostic,
    coverage_by_unit,
)


def test_directional_poles_can_share_physical_cluster_without_losing_identity():
    stops = [
        StopForClustering("300063", "Brivio - capolinea", 45.741333, 9.445700),
        StopForClustering("L00063", "Brivio - capolinea", 45.742450, 9.445850),
    ]
    clusters, reasons = cluster_stop_records(
        stops,
        frozen_cluster_by_stop_id={"300063": "EX_002", "L00063": "EX_002"},
    )
    assert clusters["300063"] == clusters["L00063"] == "EX_002"
    assert set(clusters) == {"300063", "L00063"}
    assert all(reasons[sid] == "EXACT_STOP_ID_TO_FROZEN_CERTIFIED_CLUSTER" for sid in clusters)


def test_nearby_but_non_equivalent_stops_are_not_fused():
    stops = [
        StopForClustering("300401", "Celana", 45.750000, 9.492000),
        StopForClustering("300402", "Celana", 45.750001, 9.492001),
    ]
    clusters, _ = cluster_stop_records(stops, frozen_cluster_by_stop_id={})
    assert clusters["300401"] != clusters["300402"]


def test_future_2026_09_14_evidence_is_never_current_service():
    assert FUTURE_2026_09_14_USED_AS_CURRENT is False


def test_historical_gtfs_identity_does_not_imply_current_trip_activation():
    status = activation_status("D185")
    assert "HISTORICAL_ORDINARY" in status
    assert status != "CURRENT_2026_09_04_CONFIRMED"


def test_pdf_timing_rows_are_not_complete_stop_universe():
    assert PDF_TIMING_ROWS_TREATED_AS_COMPLETE_STOP_UNIVERSE is False


def test_no_official_stop_coordinate_can_be_invented_or_non_finite():
    with pytest.raises(ValueError):
        validate_official_coordinate(math.nan, 9.4)
    with pytest.raises(ValueError):
        validate_official_coordinate(95.0, 9.4)
    validate_official_coordinate(45.73, 9.40)


def test_no_fuzzy_aliasing_is_hidden_in_name_normalisation():
    assert normalise_official_name("Cisano - via Mazzini") != normalise_official_name("Cisano - corso Mazzini")
    assert normalise_official_name("S.Maria Hoe'") == normalise_official_name("S Maria Hoe'")


def test_catchment_materialisation_is_deterministic():
    kwargs = dict(
        selected_clusters={"EX_A", "EX_B"},
        walks={
            "EX_A": {"U1": 4.0, "U2": 9.0},
            "EX_B": {"U1": 4.0, "U2": 7.0},
        },
        unit_weights={"U1": 1.0, "U2": 2.0, "U3": 3.0},
        unit_municipality={"U1": "Olgiate Molgora", "U2": "Olgiate Molgora", "U3": "Calco"},
        municipality_codes={"Olgiate Molgora": "097058", "Calco": "097012"},
    )
    first = coverage_by_unit(**kwargs)
    second = coverage_by_unit(**kwargs)
    assert first == second
    assert first[0]["nearest_physical_stop_cluster_id"] == "EX_A"
    assert first[1]["nearest_physical_stop_cluster_id"] == "EX_B"


def test_current_service_evidence_is_not_ridership():
    assert CURRENT_SERVICE_EVIDENCE_IS_RIDERSHIP is False


def test_olgiate_diagnostic_cannot_enter_candidate_optimisation():
    assert OLGIATE_DIAGNOSTIC_IN_CANDIDATE_OPTIMISATION is False
    municipality = [{
        "PRO_COM_T": "097058",
        "COMUNE": "Olgiate Molgora",
        "located_population_model": "100.0",
        "coverage_5m_share": "0.1",
        "covered_population_5m": "10",
        "coverage_8m_share": "0.2",
        "covered_population_8m": "20",
        "coverage_10m_share": "0.3",
        "covered_population_10m": "30",
        "coverage_12m_share": "0.4",
        "covered_population_12m": "40",
    }]
    rows = build_olgiate_diagnostic([], [], municipality)
    assert len(rows) == 4
    assert all(row["used_in_candidate_optimisation"] == "false" for row in rows)


def test_300_l00_equivalence_requires_exact_name_and_coordinate_compatibility():
    stops = [
        StopForClustering("300401", "Celana", 45.750067, 9.492217),
        StopForClustering("L00401", "Celana", 45.750220, 9.492070),
    ]
    clusters, reasons = cluster_stop_records(stops, frozen_cluster_by_stop_id={})
    assert clusters["300401"] == clusters["L00401"] == "V4_EQ_401"
    assert "EXACT_300_L00_SUFFIX" in reasons["300401"]


def test_pattern_ids_are_stable_and_order_sensitive():
    a = deterministic_pattern_id("D184", "0", ("A", "B", "C"))
    b = deterministic_pattern_id("D184", "0", ("A", "B", "C"))
    c = deterministic_pattern_id("D184", "0", ("A", "C", "B"))
    assert a == b
    assert a != c
