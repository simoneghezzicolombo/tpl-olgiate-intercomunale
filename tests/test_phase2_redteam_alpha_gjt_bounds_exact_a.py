from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "phase2_redteam_alpha_gjt_bounds_exact_a.py"


def test_frozen_alpha_commit_reproduces_out_of_span_passenger_return_leak(tmp_path):
    validation = tmp_path / "validation.json"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--validation", str(validation)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(validation.read_text(encoding="utf-8"))
    assert payload["status"] == "FAIL_PHASE2_GJT_BOUNDS_TARGETED_REVIEW_A"
    assert payload["certification_pass"] is False
    assert payload["out_of_span_public_return_leak_detected"] is True
    fixture = payload["fixture"]
    assert fixture["trip_departure_min"] < fixture["span_end_min"]
    assert fixture["reconstructed_public_hub_return_min"] >= fixture["span_end_min"]
    assert fixture["passenger_component_was_created"] is True
    assert payload["other_review_findings"]["historical_half_headway_wait_reused"] is False
    assert payload["other_review_findings"]["municipal_od_downscaled"] is False
    assert payload["other_review_findings"]["resident_population_used_as_demand"] is False
