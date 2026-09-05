from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.phase2_candidate_gtfs_materializer_v3 import (
    AgencyDefinition,
    BoardingPoint,
    RouteDefinition,
    ServiceCalendar,
    ServicePattern,
    StopCall,
    build_candidate_gtfs,
)


OUT_DIR = Path("outputs/phase2/candidate_gtfs_materializer_v3")
VALIDATION = OUT_DIR / "candidate_gtfs_materializer_v3_validation.json"
FEED_ZIP = OUT_DIR / "controlled_candidate_gtfs.zip"


def _fixture():
    agency = AgencyDefinition("A1", "Test Agency", "https://example.test", "Europe/Paris")
    stops = (
        BoardingPoint("S1", "Stop One", 45.00000001, 9.00000001),
        BoardingPoint("S2", "Stop Two", 45.01000001, 9.01000001),
        BoardingPoint("S3", "Stop Three", 45.02000001, 9.02000001),
    )
    routes = (
        RouteDefinition("R1", "R1", "Route One", 3),
        RouteDefinition("R2", "R2", "Route Two", 3),
    )
    calendars = (ServiceCalendar("WK", 1, 1, 1, 1, 1, 0, 0, "20260101", "20261231"),)
    patterns = (
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
    )
    return agency, stops, routes, patterns, calendars


def main() -> None:
    agency, stops, routes, patterns, calendars = _fixture()
    feed_a = build_candidate_gtfs(agency=agency, boarding_points=stops, routes=routes, patterns=patterns, calendars=calendars)
    feed_b = build_candidate_gtfs(
        agency=agency,
        boarding_points=reversed(stops),
        routes=reversed(routes),
        patterns=reversed(patterns),
        calendars=reversed(calendars),
    )
    assert feed_a.zip_bytes == feed_b.zip_bytes
    assert feed_a.files == feed_b.files

    stop_times = feed_a.file_bytes("stop_times.txt").decode("utf-8")
    assert "25:00:00" in stop_times
    assert "25:15:00" in stop_times

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    FEED_ZIP.write_bytes(feed_a.zip_bytes)
    payload = {
        "status": "PASS_RT014_CANDIDATE_GTFS_MATERIALIZATION_CONTRACT_V3",
        "fixture_semantics": "CONTROLLED_ABSTRACT_GTFS_FIXTURE_NOT_TERRITORIAL_DATA",
        "deterministic_files": True,
        "deterministic_zip": True,
        "zip_sha256": feed_a.zip_sha256,
        "zip_sha256_recomputed": hashlib.sha256(feed_a.zip_bytes).hexdigest(),
        "required_gtfs_file_count": len(feed_a.files),
        "required_gtfs_files": [name for name, _ in feed_a.files],
        "boarding_point_count": 3,
        "pattern_count": 2,
        "trip_count": 3,
        "after_midnight_gtfs_time_preserved": True,
        "fuzzy_matching_used": False,
        "implicit_stop_creation": False,
        "implicit_trip_generation": False,
        "weighted_composite_score": False,
        "territorial_candidate_claim": False,
        "network_recommendation_claim": False,
    }
    VALIDATION.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
