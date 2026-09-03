from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.phase2_current_service_matrix import (  # noqa: E402
    CurrentServiceMatrixAmbiguity,
    build_complete_cell_matrix,
    enrich_trip_identity,
)


def _trip(trip_id="T1", route="D184", column=1):
    return {
        "trip_id": trip_id,
        "route_id": route,
        "source_page": 1,
        "source_column": column,
        "active_on_reference_date": True,
        "direction_heading": "A→B",
    }


def _stop(sequence, label, route="D184"):
    return {
        "route_id": route,
        "source_page": 1,
        "stop_sequence_on_page": sequence,
        "stop_label_pdf": label,
        "source_url": "https://official.test/timetable.pdf",
        "source_pdf_sha256": "a" * 64,
    }


def _time(trip_id, sequence, label, clock, minute, route="D184"):
    return {
        "trip_id": trip_id,
        "route_id": route,
        "trip_stop_sequence": sequence,
        "pdf_row_sequence": sequence,
        "stop_label_pdf": label,
        "published_time": clock,
        "service_minutes": minute,
    }


def test_complete_matrix_preserves_unpublished_cells_without_interpolation():
    trips = [_trip()]
    stops = [_stop(1, "A"), _stop(2, "MID"), _stop(3, "B"), _stop(4, "AFTER")]
    times = [_time("T1", 1, "A", "08:00", 480), _time("T1", 3, "B", "08:20", 500)]
    matrix = build_complete_cell_matrix(trips, times, stops, [])
    assert len(matrix) == 4
    assert [row["cell_state"] for row in matrix] == [
        "PUBLISHED_TIME",
        "NO_PUBLISHED_TIME_WITHIN_COLUMN_SPAN",
        "PUBLISHED_TIME",
        "OUTSIDE_PUBLISHED_TIMED_SPAN",
    ]
    assert matrix[1]["time_usable_for_scheduled_gjt"] is False
    assert matrix[1]["unpublished_time_interpolated"] is False


def test_explicit_d185_suspension_is_not_treated_as_unknown_blank():
    trip = _trip(route="D185")
    trip["direction_heading"] = "CELANA→OLGIATE"
    stops = [_stop(1, "A", "D185"), _stop(2, "CISANO Sosta", "D185"), _stop(3, "B", "D185")]
    times = [_time("T1", 1, "A", "08:00", 480, "D185"), _time("T1", 3, "B", "08:20", 500, "D185")]
    conditions = [{
        "route_id": "D185",
        "condition_type": "TEMPORARY_DEVIATION_AND_STOP_SUSPENSION",
        "reference_date_active": True,
        "stop_effect": "CISANO_SOSTA_SUSPENDED",
    }]
    matrix = build_complete_cell_matrix([trip], times, stops, conditions)
    assert matrix[1]["cell_state"] == "EXPLICITLY_SUSPENDED_STOP"


def test_published_time_at_explicitly_suspended_stop_fails_closed():
    trip = _trip(route="D185")
    stops = [_stop(1, "A", "D185"), _stop(2, "CISANO Sosta", "D185"), _stop(3, "B", "D185")]
    times = [
        _time("T1", 1, "A", "08:00", 480, "D185"),
        _time("T1", 2, "CISANO Sosta", "08:10", 490, "D185"),
        _time("T1", 3, "B", "08:20", 500, "D185"),
    ]
    conditions = [{
        "route_id": "D185",
        "condition_type": "TEMPORARY_DEVIATION_AND_STOP_SUSPENSION",
        "reference_date_active": True,
        "stop_effect": "CISANO_SOSTA_SUSPENDED",
    }]
    with pytest.raises(CurrentServiceMatrixAmbiguity):
        build_complete_cell_matrix([trip], times, stops, conditions)


def test_reconstructed_column_identity_is_not_promoted_to_operator_trip_id():
    trips = [_trip()]
    times = [_time("T1", 1, "A", "08:00", 480), _time("T1", 2, "B", "08:20", 500)]
    enriched = enrich_trip_identity(trips, times)[0]
    assert enriched["trip_first_published_stop_label"] == "A"
    assert enriched["trip_last_published_stop_label"] == "B"
    assert enriched["operator_trip_id"] == ""
    assert "NOT_OPERATOR_TRIP_ID" in enriched["trip_identity_semantics"]
