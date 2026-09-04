from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "phase2_redteam_gjt_bounds_corner_envelope_a.py"
CONFIG = Path(__file__).resolve().parents[1] / "config" / "phase2_feeder_generalized_access_sensitivity_v2.json"


def run(tmp_path: Path):
    validation = tmp_path / "validation.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--config",
            str(CONFIG),
            "--validation",
            str(validation),
        ],
        capture_output=True,
        text=True,
    )
    return result, validation


def test_historical_grid_can_only_be_reused_as_monotone_sensitivity_axes(tmp_path):
    result, validation = run(tmp_path)
    assert result.returncode == 0, result.stderr
    payload = json.loads(validation.read_text(encoding="utf-8"))
    assert payload["precheck_pass"] is True
    assert payload["historical_grid_case_count"] == 243
    assert payload["historical_grid_is_empirical_interval"] is False
    assert payload["historical_h2_present"] is True
    assert payload["historical_h2_authorized_for_exact_bounds"] is False
    assert payload["origin_waiting_estimated_by_this_precheck"] is False
    assert payload["two_corner_envelope_exact_under_preconditions"] is True
    assert all(payload["oracle"]["checks"].values())
    assert payload["final_alpha_exact_builder_review_pending"] is True


def test_precheck_never_claims_demand_or_selection(tmp_path):
    result, validation = run(tmp_path)
    assert result.returncode == 0, result.stderr
    payload = json.loads(validation.read_text(encoding="utf-8"))
    guards = payload["epistemic_guards"]
    assert guards == {
        "worker_allocation_performed": False,
        "resident_population_used_as_demand": False,
        "departure_time_distribution_imputed": False,
        "full_expected_gjt_claimed": False,
        "ranking_or_selection_performed": False,
    }
