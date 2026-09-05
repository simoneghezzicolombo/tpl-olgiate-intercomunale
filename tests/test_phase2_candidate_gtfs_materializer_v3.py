from __future__ import annotations

import csv
import io
import zipfile

import pytest

from src.phase2_candidate_gtfs_materializer_v3 import (
    AgencyDefinition,
    BoardingPoint,
    RouteDefinition,
    ServiceCalendar,
    ServicePattern,
    StopCall,
    build_candidate_gtfs,
)


def fixture_inputs():
    agency = AgencyDefinition("A1", "Test Agency", "https://example.test", "Europe/Paris")
    stops = [
        BoardingPoint("S1", "Stop One", 45.00000001, 9.00000001),
        BoardingPoint("S2", "Stop Two", 45.01000001, 9.01000001),
        BoardingPoint("S3", "Stop Three", 45.02000001, 9.02000001),
    ]
    routes = [
        RouteDefinition("R1", "R1", "Route One", 3),
        RouteDefinition("R2", "R2", "Route Two", 3),
    ]
    calendars = [ServiceCalendar("WK", 1, 1, 1, 1, 1, 0, 0, "20260101", "20261231")]
    patterns = [
        ServicePattern(
            "P1", "R1", "WK", 0,
            (StopCall("S1", 1, 0), StopCall("S2", 2, 420), StopCall("S3", 3, 900)),
            (21600, 90000),
        ),
        ServicePattern(
            "P2", "R2", "WK", 1,
            (StopCall("S3", 1, 0), StopCall("S2", 2, 480)),
            (25200,),
        ),
    ]
    return agency, stops, routes, patterns, calendars


def build_from_fixture():
    agency, stops, routes, patterns, calendars = fixture_inputs()
    return build_candidate_gtfs(
        agency=agency,
        boarding_points=stops,
        routes=routes,
        patterns=patterns,
        calendars=calendars,
    )


def csv_rows(feed, filename):
    return list(csv.DictReader(io.StringIO(feed.file_bytes(filename).decode("utf-8"))))


def test_repeated_build_is_byte_identical():
    a = build_from_fixture()
    b = build_from_fixture()
    assert a.files == b.files
    assert a.zip_bytes == b.zip_bytes
    assert a.zip_sha256 == b.zip_sha256


def test_shuffled_input_order_is_identical():
    agency, stops, routes, patterns, calendars = fixture_inputs()
    a = build_candidate_gtfs(agency=agency, boarding_points=stops, routes=routes, patterns=patterns, calendars=calendars)
    b = build_candidate_gtfs(agency=agency, boarding_points=reversed(stops), routes=reversed(routes), patterns=reversed(patterns), calendars=reversed(calendars))
    assert a.files == b.files
    assert a.zip_bytes == b.zip_bytes


def test_shared_boarding_point_not_duplicated():
    rows = csv_rows(build_from_fixture(), "stops.txt")
    assert [r["stop_id"] for r in rows] == ["S1", "S2", "S3"]
    assert len(rows) == 3


def test_unresolved_stop_reference_fails_closed():
    agency, stops, routes, patterns, calendars = fixture_inputs()
    broken = list(patterns)
    broken[0] = ServicePattern("P1", "R1", "WK", 0, (StopCall("S1", 1, 0), StopCall("MISSING", 2, 420)), (21600,))
    with pytest.raises(ValueError, match="missing stop"):
        build_candidate_gtfs(agency=agency, boarding_points=stops, routes=routes, patterns=broken, calendars=calendars)


@pytest.mark.parametrize("collection_name", ["stops", "routes", "patterns", "calendars"])
def test_duplicate_stable_ids_fail_closed(collection_name):
    agency, stops, routes, patterns, calendars = fixture_inputs()
    values = {"stops": stops, "routes": routes, "patterns": patterns, "calendars": calendars}
    values[collection_name] = list(values[collection_name]) + [values[collection_name][0]]
    with pytest.raises(ValueError, match="duplicate"):
        build_candidate_gtfs(
            agency=agency,
            boarding_points=values["stops"],
            routes=values["routes"],
            patterns=values["patterns"],
            calendars=values["calendars"],
        )


def test_broken_stop_sequence_fails_closed():
    agency, stops, routes, patterns, calendars = fixture_inputs()
    broken = list(patterns)
    broken[0] = ServicePattern("P1", "R1", "WK", 0, (StopCall("S1", 1, 0), StopCall("S2", 3, 420)), (21600,))
    with pytest.raises(ValueError, match="contiguous"):
        build_candidate_gtfs(agency=agency, boarding_points=stops, routes=routes, patterns=broken, calendars=calendars)


def test_decreasing_runtime_fails_closed():
    agency, stops, routes, patterns, calendars = fixture_inputs()
    broken = list(patterns)
    broken[0] = ServicePattern("P1", "R1", "WK", 0, (StopCall("S1", 1, 0), StopCall("S2", 2, 500), StopCall("S3", 3, 450)), (21600,))
    with pytest.raises(ValueError, match="decreases"):
        build_candidate_gtfs(agency=agency, boarding_points=stops, routes=routes, patterns=broken, calendars=calendars)


def test_after_midnight_time_is_not_wrapped():
    rows = csv_rows(build_from_fixture(), "stop_times.txt")
    late = [r for r in rows if r["trip_id"] == "P1__T0090000"]
    assert [r["arrival_time"] for r in late] == ["25:00:00", "25:07:00", "25:15:00"]


def test_referential_integrity_is_exact():
    feed = build_from_fixture()
    stop_ids = {r["stop_id"] for r in csv_rows(feed, "stops.txt")}
    route_ids = {r["route_id"] for r in csv_rows(feed, "routes.txt")}
    service_ids = {r["service_id"] for r in csv_rows(feed, "calendar.txt")}
    trips = csv_rows(feed, "trips.txt")
    trip_ids = {r["trip_id"] for r in trips}
    assert all(r["route_id"] in route_ids for r in trips)
    assert all(r["service_id"] in service_ids for r in trips)
    stop_times = csv_rows(feed, "stop_times.txt")
    assert all(r["trip_id"] in trip_ids for r in stop_times)
    assert all(r["stop_id"] in stop_ids for r in stop_times)


def test_zip_contains_exact_minimal_file_set():
    feed = build_from_fixture()
    with zipfile.ZipFile(io.BytesIO(feed.zip_bytes)) as zf:
        assert sorted(zf.namelist()) == ["agency.txt", "calendar.txt", "routes.txt", "stop_times.txt", "stops.txt", "trips.txt"]
        assert all(zf.getinfo(name).date_time == (1980, 1, 1, 0, 0, 0) for name in zf.namelist())


def test_invalid_coordinate_and_calendar_fail_closed():
    agency, stops, routes, patterns, calendars = fixture_inputs()
    bad_stops = list(stops)
    bad_stops[0] = BoardingPoint("S1", "Stop One", float("nan"), 9.0)
    with pytest.raises(ValueError, match="latitude"):
        build_candidate_gtfs(agency=agency, boarding_points=bad_stops, routes=routes, patterns=patterns, calendars=calendars)
    bad_cal = [ServiceCalendar("WK", 1, 1, 1, 1, 1, 0, 0, "20261231", "20260101")]
    with pytest.raises(ValueError, match="starts after"):
        build_candidate_gtfs(agency=agency, boarding_points=stops, routes=routes, patterns=patterns, calendars=bad_cal)


def test_no_implicit_trip_generation():
    agency, stops, routes, patterns, calendars = fixture_inputs()
    broken = list(patterns)
    broken[0] = ServicePattern("P1", "R1", "WK", 0, (StopCall("S1", 1, 0), StopCall("S2", 2, 420)), ())
    with pytest.raises(ValueError, match="explicit departure"):
        build_candidate_gtfs(agency=agency, boarding_points=stops, routes=routes, patterns=broken, calendars=calendars)
