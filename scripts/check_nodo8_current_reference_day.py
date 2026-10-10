"""Check the historical playback day against the unchanged official GTFS ZIP."""
import csv
from datetime import date
import hashlib
import io
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data/raw/gtfs/agency_arriva/GTFS_invernale_2025-2026_-_Arriva_Italia_e_Addabus.zip"
ARCHIVE_SHA256 = "f890c393b909a40ae9500ab5acba71166cdfc5af3d42be92f55a92d92927553b"
RAW = ROOT / "assets/nodo8-current-simulation.json"
SERVICE_DAY = date(2026, 4, 28)
CLOSURE_NOTICE_URL = "https://bergamo.arriva.it/notice/linea-d185-chiusura-ponte-di-brivio/"
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def check():
    archive_bytes = ARCHIVE.read_bytes()
    archive_sha256 = hashlib.sha256(archive_bytes).hexdigest()
    if archive_sha256 != ARCHIVE_SHA256:
        raise ValueError("The official frozen GTFS archive has changed")
    service_date = SERVICE_DAY.strftime("%Y%m%d")
    weekday = WEEKDAYS[SERVICE_DAY.weekday()]
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        def rows(name):
            with archive.open(name) as stream:
                return list(csv.DictReader(io.TextIOWrapper(stream, encoding="utf-8-sig")))

        services = {
            row["service_id"] for row in rows("calendar.txt")
            if row["start_date"] <= service_date <= row["end_date"] and row[weekday] == "1"
        }
        for row in rows("calendar_dates.txt"):
            if row["date"] != service_date:
                continue
            if row["exception_type"] == "1":
                services.add(row["service_id"])
            elif row["exception_type"] == "2":
                services.discard(row["service_id"])
            else:
                raise ValueError("Unsupported calendar exception")
        trips = {
            row["trip_id"]: row for row in rows("trips.txt")
            if row["route_id"] in ("D184", "D185") and row["service_id"] in services
        }
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    if raw.get("source", {}).get("sha256") != archive_sha256:
        raise ValueError("The raw projection does not cite the frozen archive")
    route_counts = {route: sum(trip["route_id"] == route for trip in trips.values()) for route in ("D184", "D185")}
    trip_ids = sorted(trips)
    if route_counts != {"D184": 15, "D185": 19} or route_counts != raw.get("route_counts"):
        raise ValueError("The historical reference day does not preserve the raw route inventory")
    if trip_ids != sorted(trip["id"] for trip in raw["trips"]):
        raise ValueError("The historical reference day does not preserve every raw trip identity")
    if any(trips[trip["id"]]["route_id"] != trip["route"] or
           trips[trip["id"]]["shape_id"] != trip["shape_id"] or
           trips[trip["id"]]["direction_id"] != trip["direction_id"] for trip in raw["trips"]):
        raise ValueError("The historical reference day changes a trip route, direction or shape")
    return {
        "service_date": SERVICE_DAY.isoformat(),
        "route_counts": route_counts,
        "trip_ids": trip_ids,
        "archive_sha256": archive_sha256,
        "closure_notice_url": CLOSURE_NOTICE_URL,
    }


if __name__ == "__main__":
    print(json.dumps(check(), ensure_ascii=False, separators=(",", ":")))
