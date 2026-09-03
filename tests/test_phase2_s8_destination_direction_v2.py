import pytest

from src.phase2_s8_destination_direction_v2 import (
    direct_stop_direction_map,
    municipality_direction_map,
    opposite_direction,
)
from src.phase2_s8_interchange import S8ModelError


def test_direct_stop_direction_uses_downstream_sequence_not_geography():
    events = [
        {"trip_id": "m", "direction": "MILANO"},
        {"trip_id": "l", "direction": "LECCO"},
    ]
    stop_times = [
        {"trip_id": "m", "stop_id": "SOUTH_ORIGIN", "stop_sequence": "1"},
        {"trip_id": "m", "stop_id": "S01514", "stop_sequence": "2"},
        {"trip_id": "m", "stop_id": "SOUTH_A", "stop_sequence": "3"},
        {"trip_id": "m", "stop_id": "SOUTH_B", "stop_sequence": "4"},
        {"trip_id": "l", "stop_id": "NORTH_ORIGIN", "stop_sequence": "1"},
        {"trip_id": "l", "stop_id": "S01514", "stop_sequence": "2"},
        {"trip_id": "l", "stop_id": "NORTH_A", "stop_sequence": "3"},
    ]
    result = direct_stop_direction_map(events, stop_times)
    assert result == {"NORTH_A": "LECCO", "SOUTH_A": "MILANO", "SOUTH_B": "MILANO"}
    assert "SOUTH_ORIGIN" not in result
    assert "NORTH_ORIGIN" not in result


def test_municipality_direction_collapses_multiple_stops_only_if_consistent():
    rows = [
        {"stop_id": "A", "procom": "1"},
        {"stop_id": "B", "procom": "1"},
        {"stop_id": "C", "procom": "2"},
        {"stop_id": "S01514", "procom": "3"},
    ]
    assert municipality_direction_map(rows, {"A": "MILANO", "B": "MILANO", "C": "LECCO"}) == {
        "1": "MILANO",
        "2": "LECCO",
    }


def test_municipality_direction_refuses_conflicting_direct_stops():
    rows = [{"stop_id": "A", "procom": "1"}, {"stop_id": "B", "procom": "1"}]
    with pytest.raises(S8ModelError, match="conflicting"):
        municipality_direction_map(rows, {"A": "MILANO", "B": "LECCO"})


def test_opposite_direction_is_exact():
    assert opposite_direction("MILANO") == "LECCO"
    assert opposite_direction("LECCO") == "MILANO"
    with pytest.raises(S8ModelError):
        opposite_direction("BERGAMO")
