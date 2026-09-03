from pathlib import Path

MODULE = Path("scripts/gate_d_baseline_calibration.py")


def test_baseline_calibration_covers_d184_and_d185():
    text = MODULE.read_text(encoding="utf-8")
    assert '"D184"' in text
    assert '"D185"' in text
    assert "full endpoint-to-endpoint pattern" in text


def test_baseline_calibration_is_diagnostic_not_silently_applied():
    text = MODULE.read_text(encoding="utf-8")
    assert '"candidate_runtime_calibration_applied": False' in text
    assert '"calibration_status": "DIAGNOSTIC_ONLY_NOT_APPLIED_TO_CANDIDATES"' in text
    assert "scheduled time includes stopping, dwell and traffic effects" in text


def test_baseline_calibration_keeps_fact_derived_and_model_output_separate():
    text = MODULE.read_text(encoding="utf-8")
    assert '"distance_status": "DERIVED_OSM_STRUCTURAL"' in text
    assert '"schedule_status": "FACT_OFFICIAL_GTFS_REFERENCE_PERIOD"' in text
    assert '"model_status": "MODEL_OUTPUT_NOT_OBSERVED"' in text


def test_baseline_calibration_has_no_random_or_candidate_metric_constants():
    text = MODULE.read_text(encoding="utf-8")
    assert "np.random" not in text
    assert "PARETO" not in text
    assert "Raccomandata" not in text
