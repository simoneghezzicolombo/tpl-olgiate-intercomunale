import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.gate_f_s8_bridge import build_s8_fragment


def _train_json(tmp_path):
    path = tmp_path / "trains.json"
    path.write_text(json.dumps({
        "gate": "C",
        "source_type": "LIVE_OFFICIAL_GTFS",
        "service_date": "2026-09-03",
        "download_sha256": "a" * 64,
        "events": [
            {"arrival_time": "08:00:00", "departure_time": "08:01:00"},
            {"arrival_time": "08:30:00", "departure_time": "08:31:00"},
            {"arrival_time": "09:00:00", "departure_time": "09:01:00"},
        ],
    }), encoding="utf-8")
    return path


def _bus_csv(tmp_path, status="MODEL OUTPUT"):
    frame = pd.DataFrame([
        {"scenario_id": "A", "service_day_group": "WEEKDAY", "event_type": "BUS_ARRIVAL", "event_time": "07:55:00", "epistemic_status": status, "source": "E:A"},
        {"scenario_id": "A", "service_day_group": "WEEKDAY", "event_type": "BUS_ARRIVAL", "event_time": "08:25:00", "epistemic_status": status, "source": "E:A"},
        {"scenario_id": "A", "service_day_group": "WEEKDAY", "event_type": "BUS_DEPARTURE", "event_time": "08:05:00", "epistemic_status": status, "source": "E:A"},
        {"scenario_id": "A", "service_day_group": "WEEKDAY", "event_type": "BUS_DEPARTURE", "event_time": "08:35:00", "epistemic_status": status, "source": "E:A"},
        {"scenario_id": "B", "service_day_group": "WEEKDAY", "event_type": "BUS_ARRIVAL", "event_time": "07:40:00", "epistemic_status": status, "source": "E:B"},
        {"scenario_id": "B", "service_day_group": "WEEKDAY", "event_type": "BUS_ARRIVAL", "event_time": "08:25:00", "epistemic_status": status, "source": "E:B"},
        {"scenario_id": "B", "service_day_group": "WEEKDAY", "event_type": "BUS_DEPARTURE", "event_time": "08:20:00", "epistemic_status": status, "source": "E:B"},
        {"scenario_id": "B", "service_day_group": "WEEKDAY", "event_type": "BUS_DEPARTURE", "event_time": "08:50:00", "epistemic_status": status, "source": "E:B"},
    ])
    path = tmp_path / "buses.csv"
    frame.to_csv(path, index=False)
    return path


def _policy(tmp_path, direction, minimum=3, maximum=10):
    path = tmp_path / f"policy_{direction}.json"
    path.write_text(json.dumps({
        "schema_version": 1,
        "comparison_id": "TEST",
        "service_date": "2026-09-03",
        "service_day_group": "WEEKDAY",
        "connection_direction": direction,
        "evaluation_start_time": "07:30:00",
        "evaluation_end_time": "09:10:00",
        "minimum_transfer_min": minimum,
        "maximum_wait_min": maximum,
    }), encoding="utf-8")
    return path


def test_bus_to_s8_uses_bus_arrivals_as_denominator(tmp_path):
    out = build_s8_fragment(_train_json(tmp_path), _bus_csv(tmp_path), _policy(tmp_path, "BUS_TO_S8")).set_index("scenario_id")
    assert out.loc["A", "s8_connection_denominator"] == 2
    assert out.loc["A", "s8_connection_numerator"] == 2
    assert out.loc["A", "s8_useful_connection_pct"] == 100.0
    assert out.loc["B", "s8_connection_denominator"] == 2
    assert out.loc["B", "s8_connection_numerator"] == 1
    assert out.loc["B", "s8_useful_connection_pct"] == 50.0
    assert "direction=BUS_TO_S8" in out.loc["A", "s8_useful_connection_pct__comparison_basis"]


def test_s8_to_bus_uses_train_arrivals_as_denominator(tmp_path):
    out = build_s8_fragment(_train_json(tmp_path), _bus_csv(tmp_path), _policy(tmp_path, "S8_TO_BUS")).set_index("scenario_id")
    assert out.loc["A", "s8_connection_denominator"] == 3
    assert out.loc["A", "s8_connection_numerator"] == 2
    assert out.loc["B", "s8_connection_denominator"] == 3
    assert out.loc["B", "s8_connection_numerator"] == 0


def test_transfer_window_is_not_hardcoded(tmp_path):
    normal = build_s8_fragment(_train_json(tmp_path), _bus_csv(tmp_path), _policy(tmp_path, "BUS_TO_S8", 3, 10)).set_index("scenario_id")
    tight = build_s8_fragment(_train_json(tmp_path), _bus_csv(tmp_path), _policy(tmp_path, "BUS_TO_S8", 8, 10)).set_index("scenario_id")
    assert normal.loc["A", "s8_useful_connection_pct"] > tight.loc["A", "s8_useful_connection_pct"]


def test_assumption_bus_events_are_refused_for_production(tmp_path):
    with pytest.raises(ValueError, match="ASSUMPTION"):
        build_s8_fragment(_train_json(tmp_path), _bus_csv(tmp_path, "ASSUMPTION"), _policy(tmp_path, "BUS_TO_S8"))


def test_service_date_mismatch_is_refused(tmp_path):
    policy = _policy(tmp_path, "BUS_TO_S8")
    payload = json.loads(policy.read_text(encoding="utf-8"))
    payload["service_date"] = "2026-09-04"
    policy.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="service_date"):
        build_s8_fragment(_train_json(tmp_path), _bus_csv(tmp_path), policy)
