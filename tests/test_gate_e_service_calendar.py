from pathlib import Path
import csv
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.gate_e_service_calendar import CONTRACT, validate_and_aggregate  # noqa: E402
from src.service_math import ServiceMathError  # noqa: E402


def row(d, group="WEEKDAY", mode="PRODUCTION", status="DERIVED"):
    return {
        "contract_version": CONTRACT, "scenario_id": "S", "service_day_group": group,
        "service_date": d, "analysis_mode": mode, "epistemic_status": status,
        "source_artifact": "calendar.csv", "source_commit": "abc123",
    }


def test_explicit_dates_derive_service_day_count():
    out = validate_and_aggregate([row("2027-01-04"), row("2027-01-05"), row("2027-01-06")])
    assert out[0]["service_days_year"] == 3
    assert out[0]["calendar_semantics"] == "DERIVED_FROM_EXPLICIT_NONOVERLAPPING_DATE_SET"
    assert out[0]["result_status"] == "ELIGIBLE_AS_SERVICE_DAY_COUNT_INPUT"


def test_same_date_cannot_be_double_counted_across_service_groups():
    with pytest.raises(ServiceMathError, match="multiple additive"):
        validate_and_aggregate([row("2027-01-04", "WEEKDAY"), row("2027-01-04", "SCHOOL_WEEKDAY")])


def test_duplicate_same_group_date_is_rejected():
    with pytest.raises(ServiceMathError, match="duplicate"):
        validate_and_aggregate([row("2027-01-04"), row("2027-01-04")])


def test_calendar_separates_years_instead_of_blending_counts():
    out = validate_and_aggregate([row("2027-12-31"), row("2028-01-02")])
    assert {(r["calendar_year"], r["service_days_year"]) for r in out} == {(2027, 1), (2028, 1)}


def test_assumed_calendar_is_sensitivity_only():
    out = validate_and_aggregate([row("2027-01-04", mode="SENSITIVITY", status="ASSUMPTION")])
    assert out[0]["service_days_status"] == "ASSUMPTION"
    assert out[0]["result_status"] == "SENSITIVITY_ONLY_NOT_PROJECT_RESULT"


def test_assumed_calendar_cannot_be_hidden_in_production():
    with pytest.raises(ServiceMathError):
        validate_and_aggregate([row("2027-01-04", mode="PRODUCTION", status="ASSUMPTION")])


def test_production_calendar_requires_lineage():
    value = row("2027-01-04"); value["source_commit"] = ""
    with pytest.raises(ServiceMathError, match="lineage"):
        validate_and_aggregate([value])


def test_invalid_date_is_rejected():
    with pytest.raises(ServiceMathError, match="invalid ISO"):
        validate_and_aggregate([row("2027-02-30")])


def test_cli_writes_derived_count_without_embedded_303_day_constant(tmp_path):
    inp, out = tmp_path / "dates.csv", tmp_path / "summary.csv"
    fields = list(row("2027-01-04").keys())
    with inp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows([
            row("2027-01-04"), row("2027-01-05"), row("2027-01-06")
        ])
    proc = subprocess.run([
        sys.executable, str(ROOT / "scripts/gate_e_service_calendar.py"),
        "--input", str(inp), "--output", str(out),
    ], cwd=ROOT, text=True, capture_output=True)
    assert proc.returncode == 0, proc.stderr
    result = next(csv.DictReader(out.open(encoding="utf-8")))
    assert result["service_days_year"] == "3"
    assert "303" not in (ROOT / "scripts" / "gate_e_service_calendar.py").read_text(encoding="utf-8")
