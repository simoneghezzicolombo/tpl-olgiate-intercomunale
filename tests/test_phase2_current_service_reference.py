"""Tests for the Gate C -> Phase 2 current-service reference bridge.

Fixture values here test contracts only. The workflow separately downloads the
immutable authoritative Gate C artifact before testing materialised outputs.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts.phase2_build_current_service_reference import (
    GATE_C_COMMIT,
    REQUIRED_ROUTE_IDS,
    SERVICE_DATE,
    build_reference,
)


def _fixture_report():
    routes = []
    for index, route_id in enumerate(sorted(REQUIRED_ROUTE_IDS), start=1):
        routes.append({
            "route_id": route_id,
            "active_timetable_columns": index,
            "valid_from": "2026-06-09",
            "valid_to": "2026-09-13",
            "url": f"https://example.invalid/{route_id}.pdf",
            "download_sha256": str(index) * 64,
            "epistemic_status": "RECONSTRUCTED_FROM_OFFICIAL_PRIMARY_TIMETABLE",
        })
    return {
        "gate": "C",
        "source_class": "OFFICIAL_OPERATOR_PRIMARY_TIMETABLE_PDFS",
        "service_date": SERVICE_DATE,
        "routes": routes,
    }


def test_build_reference_preserves_gate_c_lineage_and_semantics():
    rows = build_reference(_fixture_report())
    assert {row["route_id"] for row in rows} == REQUIRED_ROUTE_IDS
    assert all(row["gate_c_commit"] == GATE_C_COMMIT for row in rows)
    assert all(row["semantic_scope"] == "DATED_ROUTE_LEVEL_SERVICE_REFERENCE" for row in rows)


def test_build_reference_rejects_wrong_route_universe():
    report = _fixture_report()
    report["routes"] = report["routes"][:-1]
    with pytest.raises(ValueError, match="Unexpected Gate C route universe"):
        build_reference(report)


def test_build_reference_rejects_non_gate_c_status():
    report = _fixture_report()
    report["routes"][0]["epistemic_status"] = "FACT"
    with pytest.raises(ValueError, match="unexpected epistemic status"):
        build_reference(report)


def test_materialised_reference_if_present_is_fail_closed():
    csv_path = Path("outputs/phase2/current_service_reference_2026-09-03.csv")
    validation_path = Path("outputs/phase2/current_service_reference_validation.json")
    if not csv_path.exists() and not validation_path.exists():
        pytest.skip("Materialised reference is created by the dedicated network workflow")
    assert csv_path.exists() and validation_path.exists()

    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    validation = json.loads(validation_path.read_text(encoding="utf-8"))

    assert {row["route_id"] for row in rows} == REQUIRED_ROUTE_IDS
    assert all(row["service_date"] == SERVICE_DATE for row in rows)
    assert all(row["gate_c_commit"] == GATE_C_COMMIT for row in rows)
    assert all(int(row["active_timetable_columns"]) > 0 for row in rows)
    assert validation["status"] == "PASS"
    assert validation["annual_production_from_this_snapshot"] == "NOT_IDENTIFIABLE"
    assert validation["stop_level_timetable_matrix"] == "NOT_MATERIALISED_BY_GATE_C"
    assert validation["legacy_outputs_current_service_baseline_csv"] == "FORBIDDEN_AS_PHASE2_EVIDENCE"
