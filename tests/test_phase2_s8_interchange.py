from __future__ import annotations

import csv
import hashlib
import inspect
import json
from pathlib import Path
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.phase2_s8_interchange import (  # noqa: E402
    DelayCase,
    S8ModelError,
    TransferQualityProfile,
    annotate_work_demand_addressability,
    build_active_s8_events,
    characterize_timetable,
    parse_gtfs_time,
    robust_connection_quality,
    score_bus_hub_timetable,
    station_sfr_context,
    summarize_addressable_workers,
    transfer_quality_from_slack,
)


def _write_csv(path: Path, fields: list[str], rows: list[list[object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)


def _fixture_gtfs(tmp_path: Path) -> tuple[Path, Path]:
    # Synthetic data are confined to tests/fixture generation and are never production evidence.
    root = tmp_path / "gtfs"
    root.mkdir()
    _write_csv(
        root / "trips.txt",
        ["trip_id", "route_id", "trip_short_name", "service_id"],
        [
            ["M1", "S8", "S8 - M1", "svc"],
            ["L1", "S8", "S8 - L1", "svc"],
        ],
    )
    _write_csv(
        root / "stops.txt",
        ["stop_id", "stop_name", "stop_lat", "stop_lon"],
        [
            ["S01520", "Lecco", 0, 0],
            ["S01514", "Olgiate-Calco-Brivio", 0, 0],
            ["S01645", "Milano Porta Garibaldi", 0, 0],
        ],
    )
    _write_csv(
        root / "stop_times.txt",
        ["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"],
        [
            ["M1", "06:00:00", "06:00:00", "S01520", 1],
            ["M1", "06:20:00", "06:21:00", "S01514", 2],
            ["M1", "07:00:00", "07:00:00", "S01645", 3],
            ["L1", "06:30:00", "06:30:00", "S01645", 1],
            ["L1", "07:09:00", "07:10:00", "S01514", 2],
            ["L1", "07:30:00", "07:30:00", "S01520", 3],
        ],
    )
    zpath = tmp_path / "gtfs.zip"
    with zipfile.ZipFile(zpath, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in ("trips.txt", "stops.txt", "stop_times.txt"):
            zf.write(root / name, name)
    sha = hashlib.sha256(zpath.read_bytes()).hexdigest()
    gate = {
        "gate": "C",
        "source_type": "LIVE_OFFICIAL_GTFS",
        "download_sha256": sha,
        "service_date": "2026-09-03",
        "station": {"stop_id": "S01514", "stop_name": "Olgiate-Calco-Brivio"},
        "active_s8_station_events_count": 2,
        "events": [
            {
                "trip_id": "M1",
                "trip_short_name": "S8 - M1",
                "arrival_time": "06:20:00",
                "departure_time": "06:21:00",
            },
            {
                "trip_id": "L1",
                "trip_short_name": "S8 - L1",
                "arrival_time": "07:09:00",
                "departure_time": "07:10:00",
            },
        ],
    }
    gate_path = tmp_path / "gate_c.json"
    gate_path.write_text(json.dumps(gate), encoding="utf-8")
    return zpath, gate_path


def profile() -> TransferQualityProfile:
    return TransferQualityProfile(
        transfer_walk_min=2,
        preferred_wait_min=4,
        miss_transition_scale_min=1.5,
        wait_decay_min=12,
    )


def test_parse_gtfs_time_supports_post_midnight_gtfs_hours():
    assert parse_gtfs_time("24:15:30") == pytest.approx(1455.5)


def test_exact_gtfs_join_infers_direction_from_stop_sequence(tmp_path: Path):
    zpath, gate = _fixture_gtfs(tmp_path)
    events, payload = build_active_s8_events(gate, zpath)
    assert payload["service_date"] == "2026-09-03"
    assert {e["direction"] for e in events} == {"MILANO", "LECCO"}
    m = next(e for e in events if e["trip_id"] == "M1")
    l = next(e for e in events if e["trip_id"] == "L1")
    assert m["origin_stop_id"] == "S01520" and m["terminal_stop_id"] == "S01645"
    assert l["origin_stop_id"] == "S01645" and l["terminal_stop_id"] == "S01520"


def test_wrong_gtfs_hash_fails_closed(tmp_path: Path):
    zpath, gate = _fixture_gtfs(tmp_path)
    payload = json.loads(gate.read_text())
    payload["download_sha256"] = "0" * 64
    gate.write_text(json.dumps(payload))
    with pytest.raises(S8ModelError, match="GTFS SHA256 mismatch"):
        build_active_s8_events(gate, zpath)


def test_gate_c_event_time_mismatch_fails_closed(tmp_path: Path):
    zpath, gate = _fixture_gtfs(tmp_path)
    payload = json.loads(gate.read_text())
    payload["events"][0]["departure_time"] = "06:22:00"
    gate.write_text(json.dumps(payload))
    with pytest.raises(S8ModelError, match="departure does not match GTFS"):
        build_active_s8_events(gate, zpath)


def test_characterization_has_direction_specific_spans_and_headways():
    events = [
        {"direction": "MILANO", "arrival_min": 100, "departure_min": 101},
        {"direction": "MILANO", "arrival_min": 130, "departure_min": 131},
        {"direction": "LECCO", "arrival_min": 110, "departure_min": 111},
        {"direction": "LECCO", "arrival_min": 140, "departure_min": 141},
    ]
    out = characterize_timetable(events)
    assert out["directions"]["MILANO"]["headway_median_min"] == 30
    assert out["directions"]["LECCO"]["headway_median_min"] == 30
    assert out["asymmetry"]["event_count_difference_milano_minus_lecco"] == 0


def test_transfer_quality_is_continuous_around_physical_boundary():
    p = profile()
    q_left = transfer_quality_from_slack(-0.01, p)
    q_zero = transfer_quality_from_slack(0.0, p)
    q_right = transfer_quality_from_slack(0.01, p)
    assert 0 < q_left < 1
    assert 0 < q_zero < 1
    assert 0 < q_right < 1
    assert abs(q_right - q_left) < 0.01


def test_bus_to_rail_delay_robustness_has_expected_directionality():
    p = profile()
    rail = {"departure_min": 100.0, "arrival_min": 99.0}
    base = robust_connection_quality(
        94.0,
        rail,
        "BUS_TO_RAIL",
        p,
        [DelayCase(0, 0, 1, "base")],
    )
    bus_late = robust_connection_quality(
        94.0,
        rail,
        "BUS_TO_RAIL",
        p,
        [DelayCase(5, 0, 1, "bus_late")],
    )
    rail_late = robust_connection_quality(
        94.0,
        rail,
        "BUS_TO_RAIL",
        p,
        [DelayCase(0, 5, 1, "rail_late")],
    )
    assert bus_late["expected_slack_after_walk_min"] < base["expected_slack_after_walk_min"]
    assert rail_late["expected_slack_after_walk_min"] > base["expected_slack_after_walk_min"]
    assert bus_late["hard_miss_probability"] == 1


def test_rail_to_bus_delay_robustness_has_inverse_directionality():
    p = profile()
    rail = {"arrival_min": 100.0, "departure_min": 101.0}
    base = robust_connection_quality(
        106.0,
        rail,
        "RAIL_TO_BUS",
        p,
        [DelayCase(0, 0, 1, "base")],
    )
    bus_late = robust_connection_quality(
        106.0,
        rail,
        "RAIL_TO_BUS",
        p,
        [DelayCase(4, 0, 1, "bus_late")],
    )
    rail_late = robust_connection_quality(
        106.0,
        rail,
        "RAIL_TO_BUS",
        p,
        [DelayCase(0, 4, 1, "rail_late")],
    )
    assert bus_late["expected_slack_after_walk_min"] > base["expected_slack_after_walk_min"]
    assert rail_late["expected_slack_after_walk_min"] < base["expected_slack_after_walk_min"]


def test_optimizer_scoring_is_topology_neutral():
    sig = inspect.signature(score_bus_hub_timetable)
    assert "topology" not in sig.parameters
    rail = [
        {"trip_id": "M", "direction": "MILANO", "arrival_min": 100, "departure_min": 101},
        {"trip_id": "L", "direction": "LECCO", "arrival_min": 110, "departure_min": 111},
    ]
    bus = [
        {"scenario_id": "anything", "event_type": "BUS_ARRIVAL", "event_time": "01:36:00"},
        {"scenario_id": "anything", "event_type": "BUS_DEPARTURE", "event_time": "01:55:00"},
    ]
    rows = score_bus_hub_timetable(bus, rail, profile())
    assert len(rows) == 4
    assert {r["rail_direction"] for r in rows} == {"MILANO", "LECCO"}


def test_demand_addressability_preserves_s8_direct_as_non_modal(tmp_path: Path):
    demand = tmp_path / "demand.csv"
    _write_csv(
        demand,
        ["procom_res", "origin_name", "procom_lav", "destination_name", "workers", "category"],
        [
            ["097010", "Brivio", "015146", "Milano", 80, "S8_DIRECT"],
            ["097010", "Brivio", "097048", "Merate", 105, "OTHER_EXTERNAL"],
        ],
    )
    s8 = tmp_path / "s8.csv"
    _write_csv(
        s8,
        ["stop_id", "stop_name", "procom", "comune"],
        [["S01645", "Milano Porta Garibaldi", "015146", "Milano"]],
    )
    rows = annotate_work_demand_addressability(demand, s8)
    by_dest = {r["destination_name"]: r for r in rows}
    assert by_dest["Milano"]["rail_addressability"] == "DIRECT_S8_GTFS_VERIFIED"
    assert by_dest["Milano"]["rail_semantics"] == "INFRASTRUCTURE_ADDRESSABILITY_NOT_MODAL_SHARE"
    assert by_dest["Merate"]["rail_addressability"] == "NOT_RAIL_ASSIGNED"
    assert summarize_addressable_workers(rows)["direct_s8_workers"] == 80


def test_s8_direct_without_station_municipality_evidence_is_rejected(tmp_path: Path):
    demand = tmp_path / "demand.csv"
    _write_csv(
        demand,
        ["procom_res", "origin_name", "procom_lav", "destination_name", "workers", "category"],
        [["097010", "Brivio", "015146", "Milano", 80, "S8_DIRECT"]],
    )
    s8 = tmp_path / "s8.csv"
    _write_csv(s8, ["stop_id", "stop_name", "procom", "comune"], [["X", "Elsewhere", "000001", "Elsewhere"]])
    with pytest.raises(S8ModelError, match="S8_DIRECT"):
        annotate_work_demand_addressability(demand, s8)


def test_verified_transfer_requires_traceable_evidence(tmp_path: Path):
    demand = tmp_path / "demand.csv"
    _write_csv(
        demand,
        ["procom_res", "origin_name", "procom_lav", "destination_name", "workers", "category"],
        [["097010", "Brivio", "016024", "Bergamo", 22, "OTHER_EXTERNAL"]],
    )
    s8 = tmp_path / "s8.csv"
    _write_csv(s8, ["stop_id", "stop_name", "procom", "comune"], [["S01645", "Milano", "015146", "Milano"]])
    transfers = tmp_path / "transfers.json"
    transfers.write_text(json.dumps({"016024": {"transfer_station": "Carnate"}}))
    with pytest.raises(S8ModelError, match="lacks required evidence"):
        annotate_work_demand_addressability(demand, s8, transfers)


def test_verified_transfer_can_enter_only_with_explicit_evidence(tmp_path: Path):
    demand = tmp_path / "demand.csv"
    _write_csv(
        demand,
        ["procom_res", "origin_name", "procom_lav", "destination_name", "workers", "category"],
        [["097010", "Brivio", "016024", "Bergamo", 22, "OTHER_EXTERNAL"]],
    )
    s8 = tmp_path / "s8.csv"
    _write_csv(s8, ["stop_id", "stop_name", "procom", "comune"], [["S01645", "Milano", "015146", "Milano"]])
    transfers = tmp_path / "transfers.json"
    transfers.write_text(
        json.dumps(
            {
                "016024": {
                    "transfer_station": "Carnate",
                    "connecting_route_id": "VERIFIED_ROUTE",
                    "service_date": "2026-09-03",
                    "evidence_source": "official_active_timetable_fixture",
                }
            }
        )
    )
    rows = annotate_work_demand_addressability(demand, s8, transfers)
    assert rows[0]["rail_addressability"] == "TRANSFER_RAIL_GTFS_VERIFIED"
    assert rows[0]["feeder_objective_eligible"] is True


def test_sfr_is_context_not_modal_share(tmp_path: Path):
    sfr = tmp_path / "sfr.csv"
    _write_csv(
        sfr,
        ["Anno", "Stazione_std", "Stazione", "Saliti24H", "Indice_2019_100", "Fonte_periodo"],
        [
            [2019, "OLGIATE-CALCO-BRIVIO", "Olgiate-Calco-Brivio", 1420, 100, "period1"],
            [2025, "OLGIATE-CALCO-BRIVIO", "Olgiate-Calco-Brivio", 2400, 169.0140845, "period2"],
        ],
    )
    out = station_sfr_context(sfr)
    assert out["latest_year"] == 2025
    assert out["latest_saliti24h"] == 2400
    assert "NOT_MODAL_SHARE" in out["epistemic_status"]


def test_production_module_has_no_rng_or_hardcoded_topology_choice():
    text = (ROOT / "src/phase2_s8_interchange.py").read_text(encoding="utf-8")
    assert "np.random" not in text
    assert "import random" not in text
    assert "FIG8_COMPACT" not in text
    assert "Raccomand" not in text
