#!/usr/bin/env python3
"""Run Gate C against official GTFS snapshots only."""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.transit_integrity import write_report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--service-date", required=True, help="Civil date YYYY-MM-DD to audit")
    parser.add_argument("--output", default="outputs/gate_c/transit_integrity.json")
    args = parser.parse_args()
    service_date = date.fromisoformat(args.service_date)
    report = write_report(Path(args.output), service_date)

    print(f"Gate C service date: {service_date.isoformat()}")
    print(
        "Bus feed declared range:",
        report["bus_feed"]["declared_start"],
        "->",
        report["bus_feed"]["declared_end"],
        "within range=",
        report["bus_feed"]["date_within_declared_feed_range"],
    )
    for route in report["bus_feed"]["routes"]:
        print(
            route["route_id"],
            "operator=", route["agency_name"],
            "snapshot_trips=", route["all_snapshot_trips"],
            "active_trips=", route["active_trips"],
            "patterns=", route["active_patterns"],
        )
    rail = report["rail_feed"]
    print(
        "S8 stop=", rail["stop_name"],
        "events=", rail["events_count"],
        "service_date_status=", rail["service_date_status"],
    )
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
