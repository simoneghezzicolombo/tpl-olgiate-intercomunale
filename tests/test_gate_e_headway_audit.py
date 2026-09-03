from pathlib import Path
import csv
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.headway_audit import (  # noqa: E402
    combined_observed_headway_stats,
    headway_evidence_status,
    observed_headway_stats,
)
from src.service_math import ServiceMathError  # noqa: E402


def test_perfectly_offset_60_min_directions_produce_actual_30_min_combined_gaps():
    stats = combined_observed_headway_stats(
        ["06:00:00", "07:00:00", "08:00:00"],
        ["06:30:00", "07:30:00", "08:30:00"],
    )
    assert stats["rate_equivalent_from_directional_observed_means_min"] == pytest.approx(30.0)
    assert stats["mean_headway_min"] == pytest.approx(30.0)
    assert stats["max_headway_min"] == pytest.approx(30.0)
    assert stats["max_gap_to_rate_equivalent_ratio"] == pytest.approx(1.0)
    assert stats["simultaneous_CW_CCW_departures"] == 0


def test_simultaneous_60_min_directions_do_not_magically_create_30_min_actual_service():
    stats = combined_observed_headway_stats(
        ["06:00:00", "07:00:00", "08:00:00"],
        ["06:00:00", "07:00:00", "08:00:00"],
    )
    assert stats["rate_equivalent_from_directional_observed_means_min"] == pytest.approx(30.0)
    assert stats["max_headway_min"] == pytest.approx(60.0)
    assert stats["max_gap_to_rate_equivalent_ratio"] == pytest.approx(2.0)
    assert stats["simultaneous_CW_CCW_departures"] == 3
    assert stats["zero_gap_count"] == 3


def test_observed_headways_keep_after_midnight_gtfs_times_ordered():
    stats = observed_headway_stats(["23:30:00", "24:30:00", "25:30:00"])
    assert stats["mean_headway_min"] == 60.0
    assert stats["max_headway_min"] == 60.0


def test_observed_stats_do_not_invent_boundary_gaps():
    stats = observed_headway_stats(["06:30:00", "07:30:00"])
    assert stats["n_observed_interior_gaps"] == 1
    assert stats["boundary_gap_semantics"].startswith("EXCLUDED")


def test_headway_evidence_requires_c_lineage_when_gate_c_pass():
    with pytest.raises(ServiceMathError, match="lineage"):
        headway_evidence_status("PASS", ["DERIVED"], "PRODUCTION", "", "")


def test_assumed_departures_never_become_gate_e_evidence():
    status = headway_evidence_status("PASS", ["ASSUMPTION"], "SENSITIVITY", "c.csv", "abc")
    assert status == "SENSITIVITY_ONLY_NOT_GATE_E_EVIDENCE"


def test_nonpass_c_keeps_observed_departure_metrics_provisional():
    status = headway_evidence_status("IN_PROGRESS", ["DERIVED"], "PRODUCTION", "c.csv", "abc")
    assert status == "PROVISIONAL/BLOCKED_BY_GATE_C"


def test_pass_c_real_departures_are_eligible_as_headway_evidence():
    status = headway_evidence_status("PASS", ["DERIVED"], "PRODUCTION", "c.csv", "abc")
    assert status == "ELIGIBLE_FOR_GATE_E_HEADWAY_EVIDENCE"


def write_departures(path, shared="CONFIRMED", gate="PASS"):
    header = [
        "scenario_id", "service_day_group", "band_id", "stop_id", "direction", "departure_time",
        "analysis_mode", "epistemic_status", "upstream_gate_c_status", "gate_c_artifact",
        "gate_c_commit", "shared_stop_pattern_status",
    ]
    rows = []
    for direction, times in (
        ("CW", ["06:00:00", "07:00:00", "08:00:00"]),
        ("CCW", ["06:30:00", "07:30:00", "08:30:00"]),
    ):
        for t in times:
            rows.append({
                "scenario_id": "S", "service_day_group": "WEEKDAY", "band_id": "AM", "stop_id": "HUB",
                "direction": direction, "departure_time": t, "analysis_mode": "PRODUCTION",
                "epistemic_status": "DERIVED", "upstream_gate_c_status": gate,
                "gate_c_artifact": "departures.csv", "gate_c_commit": "abc123",
                "shared_stop_pattern_status": shared,
            })
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header); w.writeheader(); w.writerows(rows)


def test_runner_computes_observed_combined_gap_only_for_confirmed_shared_stop(tmp_path):
    inp, out = tmp_path / "departures.csv", tmp_path / "audit.csv"
    write_departures(inp, shared="CONFIRMED")
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts/gate_e_headway_audit.py"), "--input", str(inp), "--output", str(out)],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert proc.returncode == 0, proc.stderr
    row = next(csv.DictReader(out.open(encoding="utf-8")))
    assert row["combined_headway_computed"] == "True"
    assert float(row["combined_max_headway_min"]) == 30.0
    assert row["headway_evidence_status"] == "ELIGIBLE_FOR_GATE_E_HEADWAY_EVIDENCE"


def test_runner_withholds_combined_gap_if_shared_stop_pattern_not_confirmed(tmp_path):
    inp, out = tmp_path / "departures.csv", tmp_path / "audit.csv"
    write_departures(inp, shared="UNKNOWN")
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts/gate_e_headway_audit.py"), "--input", str(inp), "--output", str(out)],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert proc.returncode == 0, proc.stderr
    row = next(csv.DictReader(out.open(encoding="utf-8")))
    assert row["combined_headway_computed"] == "False"
    assert row["combined_max_headway_min"] == ""
