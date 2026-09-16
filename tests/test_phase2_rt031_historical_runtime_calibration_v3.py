from decimal import Decimal

import pytest

from src.phase2_rt031_historical_runtime_calibration_v3 import (
    decimal_median,
    gtfs_time_seconds,
    historical_scheduled_metrics,
)


def test_gtfs_time_supports_after_midnight_hours():
    assert gtfs_time_seconds("24:03:00") == 86580
    with pytest.raises(ValueError):
        gtfs_time_seconds("12:60:00")


def test_decimal_median_is_exact():
    assert decimal_median([Decimal("1"), Decimal("2")]) == Decimal("1.5")


def test_historical_metrics_do_not_treat_equal_clocks_as_observed_zero_dwell():
    trips = [{"trip_id": "T", "route_id": "D184"}]
    stops = [
        {"trip_id": "T", "arrival_time": "06:00:00", "departure_time": "06:00:00",
         "stop_sequence": "1", "shape_dist_traveled": "0"},
        {"trip_id": "T", "arrival_time": "06:20:00", "departure_time": "06:20:00",
         "stop_sequence": "2", "shape_dist_traveled": "10"},
    ]
    result = historical_scheduled_metrics(trips, stops, route_ids=("D184",))
    assert result["dwell_calibration_available"] is False
    assert result["comparable_scheduled_speed_kmh"]["median"] == "30"
