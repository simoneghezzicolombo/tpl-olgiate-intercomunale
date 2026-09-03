import csv
from datetime import date
from pathlib import Path

from src.transit_integrity import (
    CORE_BUS_ROUTES,
    OFFICIAL_ARRIVA,
    OFFICIAL_LINEELECCO,
    OFFICIAL_TRENORD,
    _trip_stop_sequences,
    active_service_ids,
    bus_route_audit,
    feed_declared_range,
    rail_has_standard_service_calendar,
    route_operator_map,
    s8_station_events,
)


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def test_core_routes_are_in_official_arriva_feed_and_not_lineelecco():
    arriva = route_operator_map(OFFICIAL_ARRIVA)
    lineelecco = route_operator_map(OFFICIAL_LINEELECCO)
    assert set(CORE_BUS_ROUTES).issubset(arriva)
    assert set(CORE_BUS_ROUTES).isdisjoint(lineelecco)


def test_core_route_operator_is_resolved_from_agency_table():
    audit = bus_route_audit(OFFICIAL_ARRIVA, date(2026, 5, 6))
    assert {r["agency_name"] for r in audit} == {"Arriva Italia Srl - Lecco"}
    assert all(r["agency_id"] == "A2013327" for r in audit)


def test_arriva_feed_dates_are_explicit_and_stale_for_current_project_date():
    start, end = feed_declared_range(OFFICIAL_ARRIVA)
    assert start == date(2026, 1, 1)
    assert end == date(2026, 6, 8)
    assert not (start <= date(2026, 9, 3) <= end)
    assert not active_service_ids(OFFICIAL_ARRIVA, date(2026, 9, 3)), (
        "A stale feed must not silently yield current-date services"
    )


def test_calendar_dates_drive_arriva_service_not_empty_calendar_file():
    calendar_rows = (
        (OFFICIAL_ARRIVA / "calendar.txt")
        .read_text(encoding="utf-8-sig")
        .strip()
        .splitlines()
    )
    assert len(calendar_rows) == 1, (
        "Official Arriva calendar.txt is expected to contain only its header"
    )
    assert (OFFICIAL_ARRIVA / "calendar_dates.txt").stat().st_size > 1000
    assert active_service_ids(OFFICIAL_ARRIVA, date(2026, 5, 6)), (
        "calendar_dates must yield active services"
    )


def test_official_route_patterns_have_real_active_trips_and_valid_stop_foreign_keys():
    service_date = date(2026, 5, 6)
    active_services = active_service_ids(OFFICIAL_ARRIVA, service_date)
    trips = _csv_rows(OFFICIAL_ARRIVA / "trips.txt")
    official_stop_ids = {
        row["stop_id"] for row in _csv_rows(OFFICIAL_ARRIVA / "stops.txt")
    }
    audit = bus_route_audit(OFFICIAL_ARRIVA, service_date)
    assert all(r["active_trips"] > 0 for r in audit)
    assert all(r["active_patterns"] > 0 for r in audit)

    active_core_trip_ids = {
        row["trip_id"]
        for row in trips
        if row.get("route_id") in CORE_BUS_ROUTES
        and row.get("service_id") in active_services
    }
    sequences = _trip_stop_sequences(OFFICIAL_ARRIVA, active_core_trip_ids)
    assert set(sequences) == active_core_trip_ids, (
        "Every active core trip must have at least one stop_times sequence"
    )
    referenced_stop_ids = {
        stop_id for sequence in sequences.values() for stop_id in sequence
    }
    assert referenced_stop_ids
    assert referenced_stop_ids.issubset(official_stop_ids), (
        "Every active core pattern stop_id must resolve in official stops.txt"
    )
    assert all(len(sequence) >= 2 for sequence in sequences.values()), (
        "An active bus trip cannot be treated as a route pattern with fewer than two stops"
    )


def test_trenord_s8_events_come_from_gtfs_and_service_date_is_not_fabricated():
    rail = s8_station_events(OFFICIAL_TRENORD)
    assert rail["events_count"] > 0
    assert rail["stop_name"] == "Olgiate-Calco-Brivio"
    assert rail["stop_id"] == "S01514"
    assert not rail_has_standard_service_calendar(OFFICIAL_TRENORD)
    assert rail["service_date_status"] == "PROVISIONAL_SERVICE_DATE_UNRESOLVED"
    assert all(
        event["arrival_time"] and event["departure_time"]
        for event in rail["events"]
    )


def test_gate_c_module_does_not_consume_reconstructed_gtfs():
    source = Path("src/transit_integrity.py").read_text(encoding="utf-8")
    forbidden_as_inputs = [
        'Path("data/raw/gtfs/network_structural")',
        'Path("data/raw/gtfs/network_2026_emergency")',
        "TRENI_S8_VIGENTI",
        "STOPS_DATABASE",
    ]
    for token in forbidden_as_inputs:
        assert token not in source
