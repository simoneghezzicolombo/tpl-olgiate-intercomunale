"""Tests for current PDF timetable stop identity cross-checking.

All stop names and IDs here are TEST_FIXTURE_ONLY. No fixture is territorial evidence.
"""
from __future__ import annotations

from src.phase2_current_service_stop_identity import (
    GtfsStop,
    PageRow,
    exact_physical_equivalence,
    labels_compatible,
    normalize_stop_label,
    resolve_page,
    unique_route_patterns,
)


def test_normalization_handles_punctuation_and_common_transit_abbreviations():
    assert normalize_stop_label("AIRUNO F.S.") == ("AIRUNO", "FS")
    assert normalize_stop_label("MERATE (P.zza Italia)") == ("MERATE", "PIAZZA", "ITALIA")


def test_label_matching_is_conservative_containment_not_edit_distance():
    assert labels_compatible("OLGIATE (Via Nazionale)", "Olgiate Molgora - via nazionale")
    assert labels_compatible("CALOLZIO F.S.", "Calolziocorte - stazione f.s.")
    assert labels_compatible("CALCO", "Calco - via statale")
    assert not labels_compatible("CALCO", "Brivio - centro")
    # A genuine typo is not repaired by edit distance.
    assert not labels_compatible("IMBERSAGO", "Imbersogo - centro")


def test_unique_route_name_candidate_resolves_without_forcing_sequence():
    stops = {
        "A": GtfsStop("A", "Alpha - centro"),
        "B": GtfsStop("B", "Beta - piazza"),
    }
    rows = [PageRow("R", 1, 1, "ALPHA")]
    result = resolve_page(rows, route_patterns=[("A", "B")], stops=stops)
    assert result[0].status == "RESOLVED_ROUTE_NAME_UNIQUE"
    assert result[0].stop_id == "A"


def test_exact_same_name_and_coordinate_gtfs_records_are_one_physical_equivalence():
    stops = {
        "300001": GtfsStop("300001", "Town - centro", "45.700000", "9.400000"),
        "L00001": GtfsStop("L00001", "Town - centro", "45.700000", "9.400000"),
    }
    equivalence = exact_physical_equivalence(stops)
    assert equivalence["300001"] == ("300001", "L00001")
    result = resolve_page(
        [PageRow("R", 1, 1, "TOWN CENTRO")],
        route_patterns=[("300001",), ("L00001",)],
        stops=stops,
    )
    assert result[0].status == "RESOLVED_EQUIVALENT_GTFS_RECORDS_SAME_NAME_COORDINATE"
    assert result[0].stop_id == "300001"
    assert result[0].equivalent_stop_ids == ("300001", "L00001")


def test_same_name_but_different_coordinates_is_not_collapsed():
    stops = {
        "A": GtfsStop("A", "Town - centro", "45.700000", "9.400000"),
        "B": GtfsStop("B", "Town - centro", "45.700100", "9.400000"),
    }
    result = resolve_page(
        [PageRow("R", 1, 1, "TOWN CENTRO")],
        route_patterns=[("A",), ("B",)],
        stops=stops,
    )
    assert result[0].status == "AMBIGUOUS_HISTORICAL_GTFS"
    assert result[0].stop_id is None


def test_sequence_disambiguates_repeated_name_candidate_when_best_pattern_is_unique():
    stops = {
        "X": GtfsStop("X", "Town - start"),
        "A": GtfsStop("A", "Town - beverate cariplo"),
        "B": GtfsStop("B", "Town - beverate paese"),
        "Y": GtfsStop("Y", "Town - terminal"),
        "Z": GtfsStop("Z", "Other - branch"),
    }
    rows = [
        PageRow("R", 1, 1, "TOWN START"),
        PageRow("R", 1, 2, "BEVERATE"),
        PageRow("R", 1, 3, "TOWN TERMINAL"),
    ]
    result = resolve_page(
        rows,
        route_patterns=[("X", "A", "Y"), ("X", "B", "Z")],
        stops=stops,
    )
    assert result[1].status == "RESOLVED_BEST_SEQUENCE_UNIQUE"
    assert result[1].stop_id == "A"
    assert result[1].best_pattern_match_rows == 3


def test_equal_best_patterns_with_different_stop_ids_remain_ambiguous():
    stops = {
        "X": GtfsStop("X", "Town - start"),
        "A": GtfsStop("A", "Town - centro lato a"),
        "B": GtfsStop("B", "Town - centro lato b"),
        "Y": GtfsStop("Y", "Town - terminal"),
    }
    rows = [
        PageRow("R", 1, 1, "TOWN START"),
        PageRow("R", 1, 2, "TOWN CENTRO"),
        PageRow("R", 1, 3, "TOWN TERMINAL"),
    ]
    result = resolve_page(
        rows,
        route_patterns=[("X", "A", "Y"), ("X", "B", "Y")],
        stops=stops,
    )
    assert result[1].status == "AMBIGUOUS_HISTORICAL_GTFS"
    assert result[1].stop_id is None
    assert result[1].tied_best_pattern_count == 2


def test_unmatched_label_stays_unresolved():
    stops = {"A": GtfsStop("A", "Alpha - centro")}
    rows = [PageRow("R", 1, 1, "GAMMA")]
    result = resolve_page(rows, route_patterns=[("A",)], stops=stops)
    assert result[0].status == "NO_HISTORICAL_GTFS_NAME_MATCH"
    assert result[0].stop_id is None


def test_pdf_rows_must_be_ordered():
    stops = {"A": GtfsStop("A", "Alpha")}
    rows = [PageRow("R", 1, 2, "ALPHA"), PageRow("R", 1, 1, "ALPHA")]
    try:
        resolve_page(rows, route_patterns=[("A",)], stops=stops)
    except ValueError as exc:
        assert "ordered" in str(exc)
    else:
        raise AssertionError("unordered PDF rows must fail closed")


def test_unique_route_patterns_are_deterministic_and_route_scoped():
    trips = [
        {"trip_id": "T1", "route_id": "R1"},
        {"trip_id": "T2", "route_id": "R1"},
        {"trip_id": "T3", "route_id": "R2"},
    ]
    stop_times = [
        {"trip_id": "T1", "stop_sequence": "2", "stop_id": "B"},
        {"trip_id": "T1", "stop_sequence": "1", "stop_id": "A"},
        {"trip_id": "T2", "stop_sequence": "1", "stop_id": "A"},
        {"trip_id": "T2", "stop_sequence": "2", "stop_id": "B"},
        {"trip_id": "T3", "stop_sequence": "1", "stop_id": "C"},
    ]
    patterns = unique_route_patterns(trips, stop_times, {"R1", "R2"})
    assert patterns["R1"] == [("A", "B")]
    assert patterns["R2"] == [("C",)]
