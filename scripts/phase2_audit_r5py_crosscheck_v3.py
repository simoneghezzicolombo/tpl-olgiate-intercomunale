from __future__ import annotations

import csv
import datetime as dt
import json
import platform
import subprocess
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

import r5py
import r5py.sampledata.helsinki as helsinki


OUT = Path("outputs/phase2/r5py_crosscheck_v3/r5py_crosscheck_v3_validation.json")


def choose_service_date(gtfs_path: Path) -> dt.date:
    with zipfile.ZipFile(gtfs_path) as zf:
        names = set(zf.namelist())
        if "calendar.txt" in names:
            with zf.open("calendar.txt") as fh:
                rows = list(csv.DictReader(line.decode("utf-8-sig") for line in fh))
            dates = sorted(
                dt.datetime.strptime(row["start_date"], "%Y%m%d").date()
                for row in rows
                if row.get("start_date")
            )
            if dates:
                return dates[0]
        if "calendar_dates.txt" in names:
            with zf.open("calendar_dates.txt") as fh:
                rows = list(csv.DictReader(line.decode("utf-8-sig") for line in fh))
            dates = sorted(
                dt.datetime.strptime(row["date"], "%Y%m%d").date()
                for row in rows
                if row.get("date") and row.get("exception_type") == "1"
            )
            if dates:
                return dates[0]
    raise RuntimeError("pinned GTFS fixture contains no usable service date")


def matrix_signature(matrix: pd.DataFrame) -> list[dict[str, object]]:
    cols = ["from_id", "to_id", "travel_time"]
    table = matrix[cols].copy().sort_values(["from_id", "to_id"]).reset_index(drop=True)
    return table.to_dict(orient="records")


def validate_matrix(matrix: pd.DataFrame) -> None:
    required = {"from_id", "to_id", "travel_time"}
    if not required.issubset(matrix.columns):
        raise AssertionError(f"missing columns: {required - set(matrix.columns)}")
    if matrix.empty:
        raise AssertionError("travel-time matrix is empty")
    values = pd.to_numeric(matrix["travel_time"], errors="coerce")
    if values.isna().any() or (values < 0).any():
        raise AssertionError("travel times must be finite and non-negative")


def main() -> None:
    gtfs = Path(helsinki.gtfs)
    osm = Path(helsinki.osm_pbf)
    if not gtfs.exists() or not osm.exists():
        raise AssertionError("pinned sample fixture did not materialize")

    service_date = choose_service_date(gtfs)
    departure = dt.datetime.combine(service_date, dt.time(8, 0))

    network = r5py.TransportNetwork(osm, [gtfs])

    origins = gpd.GeoDataFrame(
        {"id": ["O1", "O2"]},
        geometry=[Point(24.9410, 60.1710), Point(24.9500, 60.1690)],
        crs="EPSG:4326",
    )
    destinations = gpd.GeoDataFrame(
        {"id": ["D1", "D2"]},
        geometry=[Point(24.9380, 60.1700), Point(24.9580, 60.1740)],
        crs="EPSG:4326",
    )

    walk_1 = r5py.TravelTimeMatrix(
        network,
        origins=origins,
        destinations=destinations,
        transport_modes=[r5py.TransportMode.WALK],
        departure=departure,
    )
    walk_2 = r5py.TravelTimeMatrix(
        network,
        origins=origins,
        destinations=destinations,
        transport_modes=[r5py.TransportMode.WALK],
        departure=departure,
    )
    transit = r5py.TravelTimeMatrix(
        network,
        origins=origins,
        destinations=destinations,
        transport_modes=[r5py.TransportMode.TRANSIT],
        departure=departure,
    )

    validate_matrix(walk_1)
    validate_matrix(walk_2)
    validate_matrix(transit)
    if matrix_signature(walk_1) != matrix_signature(walk_2):
        raise AssertionError("repeated deterministic WALK request changed")

    java_version = subprocess.run(
        ["java", "-version"], capture_output=True, text=True, check=True
    )
    java_text = (java_version.stderr or java_version.stdout).splitlines()[0]

    payload = {
        "status": "PASS_RT012_R5PY_CROSSCHECK_SMOKE_V3",
        "fixture_semantics": "PINNED_UPSTREAM_SAMPLE_FIXTURE_NOT_TERRITORIAL_DATA",
        "python_version": platform.python_version(),
        "r5py_version": r5py.__version__,
        "java_version_line": java_text,
        "service_date": service_date.isoformat(),
        "transport_network_built": True,
        "walk_matrix_rows": int(len(walk_1)),
        "transit_matrix_rows": int(len(transit)),
        "walk_repeat_deterministic": True,
        "walk_min_travel_time": float(pd.to_numeric(walk_1["travel_time"]).min()),
        "walk_max_travel_time": float(pd.to_numeric(walk_1["travel_time"]).max()),
        "transit_min_travel_time": float(pd.to_numeric(transit["travel_time"]).min()),
        "transit_max_travel_time": float(pd.to_numeric(transit["travel_time"]).max()),
        "territorial_candidate_claim": False,
        "network_recommendation_claim": False,
        "weighted_composite_score": False,
        "internal_engine_replaced": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
