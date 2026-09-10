"""Historical D184/D185 semantics inventory, NOT physical calibration PASS.

All trip/stop-time values are retained as published, including repeated visits,
pickup/dropoff, direction, shape, block and calendar references. No historical
stop is promoted to the frozen conventional stop universe.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path

from src.phase2_rt031_typed_composition_v3 import payload_hash

EXPECTED = {
    "routes.txt": "a59e48ac22ba0d71215be926818e368bb37a58531256b1b74850b6b9e2624583",
    "trips.txt": "ff3005d3831bf14ce1a7965b3d746c278f3392d67b163d6be61a28a9644903bb",
    "stop_times.txt": "c5b4a6f98935893c916281b58f1a7384e500ffe3800dac11f68550043cea5709",
    "shapes.txt": "a34ab65ecfc1e31e348b617d19a7e469cc056d40d6e3435030508fa5b066dee0",
    "stops.txt": "099163a45d1c75f12fdd172f1ea9984132e3aa14f9d7741a196293dff405be72",
    "calendar.txt": "df53464dd12a0cd9a1f91ce4b88cd8fb4574119c356794a457e7df7d201f6ce5",
    "calendar_dates.txt": "de510c13a9d8e9c55160e2f7f26c9e59d1420b5d31327d7d8c4d0d7a809ef022",
    "feed_info.txt": "a45d751ea105ab23122d928eeb96e885b71dc18b680b0763825cbb7c20a63030",
}


def inventory(tables):
    trips = [r for r in tables["trips.txt"] if r["route_id"] in {"D184", "D185"}]
    if not trips or len({t["trip_id"] for t in trips}) != len(trips):
        raise ValueError("empty/duplicate historical trip identity")
    tids = {t["trip_id"] for t in trips}
    stops = {s["stop_id"]: s for s in tables["stops.txt"]}
    if len(stops) != len(tables["stops.txt"]):
        raise ValueError("duplicate source stop identity")
    times = defaultdict(list)
    for row in tables["stop_times.txt"]:
        if row["trip_id"] in tids:
            times[row["trip_id"]].append(row)
    shapes = defaultdict(list)
    wanted_shapes = {t["shape_id"] for t in trips if t["shape_id"]}
    for row in tables["shapes.txt"]:
        if row["shape_id"] in wanted_shapes:
            shapes[row["shape_id"]].append(row)
    calendars = {r["service_id"] for key in ("calendar.txt", "calendar_dates.txt") for r in tables[key]}
    shape_manifest = []
    for sid, rows in sorted(shapes.items()):
        rows.sort(key=lambda r: int(r["shape_pt_sequence"]))
        if len({r["shape_pt_sequence"] for r in rows}) != len(rows):
            raise ValueError("duplicate shape point sequence")
        shape_manifest.append({"shape_id": sid, "published_point_count": len(rows),
                               "ordered_source_rows_sha256": payload_hash(rows),
                               "certified_rt017_carrier": None})
    records = []
    for trip in sorted(trips, key=lambda r: r["trip_id"]):
        rows = sorted(times[trip["trip_id"]], key=lambda r: int(r["stop_sequence"]))
        if not rows or len({int(r["stop_sequence"]) for r in rows}) != len(rows):
            raise ValueError("missing/duplicate trip stop sequence")
        if trip["service_id"] not in calendars:
            raise ValueError("historical trip references missing service calendar")
        if any(r["stop_id"] not in stops for r in rows):
            raise ValueError("unknown historical stop")
        visits = [{"source_stop_time": dict(r), "source_stop": dict(stops[r["stop_id"]]),
                   "frozen_stop_mapping": None} for r in rows]
        records.append({"source_trip": dict(trip), "visits": visits,
                        "published_shape_present": trip["shape_id"] in shapes,
                        "physical_turn_attachment_calibration": "OPEN",
                        "onboard_continuity_between_trips": None})
    semantic_patterns = {payload_hash({"route": t["source_trip"]["route_id"],
                                      "direction": t["source_trip"]["direction_id"],
                                      "shape": t["source_trip"]["shape_id"],
                                      "ordered_events": [[v["source_stop_time"][k] for k in
                                                           ("stop_id", "pickup_type", "drop_off_type")]
                                                          for v in t["visits"]]}) for t in records}
    audit = {"status": "PASS_HISTORICAL_SERVICE_SEMANTICS_INVENTORY_ONLY", "epistemic_status": "DERIVED",
             "source_role": "HISTORICAL_GTFS_NOT_CURRENT_SERVICE", "feed_info": tables["feed_info.txt"],
             "trip_count": len(records), "route_trip_counts": dict(sorted(Counter(t["route_id"] for t in trips).items())),
             "stop_occurrence_count": sum(len(r["visits"]) for r in records),
             "trip_patterns_with_repeated_stop_ids": sum(len({v["source_stop_time"]["stop_id"] for v in r["visits"]}) < len(r["visits"]) for r in records),
             "direction_shape_pickup_dropoff_profile_count": len(semantic_patterns),
             "referenced_shape_count": len(wanted_shapes), "present_shape_count": len(shapes),
             "missing_shape_trip_count": sum(not r["published_shape_present"] for r in records),
             "nonempty_block_id_trip_count": sum(bool(t["block_id"]) for t in trips),
             "pickup_type_values": dict(sorted(Counter(v["source_stop_time"]["pickup_type"] for r in records for v in r["visits"]).items())),
             "drop_off_type_values": dict(sorted(Counter(v["source_stop_time"]["drop_off_type"] for r in records for v in r["visits"]).items())),
             "full_trip_payload_sha256": payload_hash(records), "shape_manifest_sha256": payload_hash(shape_manifest),
             "physical_geometry_turn_calibration_pass": False, "historical_to_frozen_stop_mapping_pass": False,
             "interlining_inferred_from_block_id": False, "stop_count_target_selected": False,
             "production_rt031_pass": False}
    return records, shape_manifest, audit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gtfs", type=Path, default=Path("data/raw/gtfs/agency_arriva"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    tables = {}
    for name, expected in EXPECTED.items():
        path = args.gtfs / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("historical input SHA256 mismatch: " + name)
        with path.open(encoding="utf-8-sig", newline="") as f:
            tables[name] = list(csv.DictReader(f))
    trips, shapes, audit = inventory(tables)
    audit["input_sha256"] = EXPECTED
    args.out.mkdir(parents=True, exist_ok=True)
    for name, value in (("historical_trip_semantics.json", trips), ("historical_shape_manifest.json", shapes),
                        ("historical_calibration_audit.json", audit)):
        (args.out / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    print(json.dumps(audit, sort_keys=True))


if __name__ == "__main__":
    main()
