from copy import deepcopy
import pytest
from scripts.phase2_audit_rt031_historical_service_calibration_v3 import inventory


def fixture():
    trips = [dict(route_id="D184", trip_id=t, shape_id="shape", service_id="weekday", direction_id="0", block_id="shared") for t in ("t1", "t2")]
    times = [dict(trip_id=t, stop_id=s, stop_sequence=str(i), pickup_type="0", drop_off_type="0", arrival_time="10:00:00", departure_time="10:00:00")
             for t in ("t1", "t2") for i, s in enumerate(("S", "B", "S"), 1)]
    return {"trips.txt": trips, "stop_times.txt": times, "stops.txt": [dict(stop_id=s) for s in ("S", "B")],
            "shapes.txt": [dict(shape_id="shape", shape_pt_sequence="1")], "calendar.txt": [dict(service_id="weekday")],
            "calendar_dates.txt": [], "feed_info.txt": []}


def test_preserves_revisits_and_distinguishes_pickup_semantics_on_same_sequence():
    data = fixture(); data["stop_times.txt"][3]["pickup_type"] = "1"
    trips, shapes, audit = inventory(data)
    assert [v["source_stop_time"]["stop_id"] for v in trips[0]["visits"]] == ["S", "B", "S"]
    assert audit["direction_shape_pickup_dropoff_profile_count"] == 2
    assert audit["trip_patterns_with_repeated_stop_ids"] == 2
    assert not audit["interlining_inferred_from_block_id"]
    assert all(v["frozen_stop_mapping"] is None for t in trips for v in t["visits"])


def test_missing_shape_is_explicit_not_invented():
    data = fixture(); data["shapes.txt"] = []
    _, _, audit = inventory(data)
    assert audit["missing_shape_trip_count"] == 2
    assert not audit["physical_geometry_turn_calibration_pass"]


def test_source_row_order_invariance():
    data = fixture(); other = deepcopy(data)
    for rows in other.values(): rows.reverse()
    assert inventory(data) == inventory(other)


def test_duplicate_stop_sequence_rejected():
    data = fixture(); data["stop_times.txt"][1]["stop_sequence"] = "1"
    with pytest.raises(ValueError, match="duplicate trip stop sequence"):
        inventory(data)
