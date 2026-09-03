from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd

MODULE_PATH = Path("scripts/gate_d_baseline_calibration_v4.py")
spec = importlib.util.spec_from_file_location("gate_d_baseline_calibration_v4", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def _toy_feed():
    return {
        "routes": pd.DataFrame({"route_id": ["r"], "route_short_name": ["D185"]}),
        "trips": pd.DataFrame({
            "route_id": ["r"] * 5,
            "trip_id": ["a1", "a2", "a3", "b1", "short"],
            "direction_id": ["0", "0", "0", "1", "0"],
            "shape_id": ["s"] * 5,
        }),
        "stops": pd.DataFrame({
            "stop_id": ["olg", "mid", "far", "other"],
            "stop_name": [
                "Olgiate Molgora - stazione f.s.", "Calco", "Caprino", "Celana"
            ],
            "stop_lon": [9.40, 9.41, 9.42, 9.43],
            "stop_lat": [45.72, 45.73, 45.74, 45.75],
        }),
        "stop_times": pd.DataFrame([
            {"trip_id": tid, "stop_id": sid, "stop_sequence": str(seq)}
            for tid, pattern in {
                "a1": ["far", "mid", "olg"],
                "a2": ["far", "mid", "olg"],
                "a3": ["far", "mid", "olg"],
                "b1": ["olg", "mid", "far"],
                "short": ["other", "far"],
            }.items()
            for seq, sid in enumerate(pattern, start=1)
        ]),
    }


def test_d185_dominant_pattern_is_derived_without_hardcoded_outer_terminus():
    rows = module.dominant_olgiate_patterns(_toy_feed(), "D185")
    by_direction = {row["direction_id"]: row for row in rows}
    assert by_direction["0"]["pattern"] == ("far", "mid", "olg")
    assert by_direction["0"]["pattern_trip_count"] == 3
    assert by_direction["1"]["pattern"] == ("olg", "mid", "far")
    assert all(row["pattern_selection_status"] == module.SELECTION_STATUS for row in rows)


def test_calibration_v4_does_not_prescribe_ravellino_caprino_or_celana_endpoint_tokens():
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "ROUTE_ENDPOINT_TOKENS" not in text
    assert '"D184": ("olgiate"' not in text
    assert '"D185": ("olgiate"' not in text


def test_spatial_reconstruction_is_explicitly_from_official_gtfs_shape():
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "RECONSTRUCTED_FROM_OFFICIAL_GTFS_STOP_SEQUENCE_CONSTRAINED_TO_OFFICIAL_GTFS_SHAPE" in text
    assert "shape_monotonicity_tolerance_status" in text
    assert "ASSUMPTION_NUMERICAL_TOLERANCE_NOT_ROUTE_METRIC" in text


def test_no_random_or_transferable_runtime_factor():
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "np.random" not in text
    assert "candidate_runtime_calibration_applied" not in text
