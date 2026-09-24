"""Contract tests for Phase 2 budget envelopes.

Fixture numbers are TEST_FIXTURE_ONLY. The dedicated workflow separately reads
the immutable validated Gate E artifact.
"""
import pytest

from scripts.phase2_build_budget_envelopes import (
    EXPECTED_BUDGET_STATUS,
    GATE_E_COMMIT,
    build_envelopes,
    extract_reference_budget,
    parse_changes,
)


def _rows(reference="100000"):
    common = {
        "gate_d_status": "PASS",
        "gate_d_commit": "a" * 40,
        "gate_d_artifact_id": "123",
        "gate_d_artifact_sha256": "b" * 64,
        "route_definition_status": "ASSUMPTION",
        "budget_bus_km_year": reference,
        "budget_status": EXPECTED_BUDGET_STATUS,
        "equal_pair_envelope_semantics": "INTEGER_MAX_FOR_EQUAL_CW_CCW_FULL_LOOPS_NOT_A_SERVICE_PLAN",
    }
    return [
        {**common, "route_id": "A"},
        {**common, "route_id": "B"},
    ]


def test_extract_reference_requires_consistent_structured_gate_e_rows():
    reference, metadata = extract_reference_budget(_rows())
    assert reference == pytest.approx(100000.0)
    assert metadata["gate_e_commit"] == GATE_E_COMMIT
    assert metadata["budget_status"] == EXPECTED_BUDGET_STATUS
    assert metadata["not_a_service_plan"] is True


def test_extract_reference_rejects_disagreement_between_pairable_rows():
    rows = _rows()
    rows[1]["budget_bus_km_year"] = "90000"
    with pytest.raises(ValueError, match="disagree"):
        extract_reference_budget(rows)


def test_extract_reference_rejects_unexpected_epistemic_status():
    rows = _rows()
    rows[0]["budget_status"] = "ASSUMPTION"
    with pytest.raises(ValueError, match="epistemic status"):
        extract_reference_budget(rows)


def test_changes_are_explicit_and_budget_caps_are_derived_only():
    changes = parse_changes("-0.2,-0.1,0,0.1,0.2,0.3")
    envelopes = build_envelopes(100000.0, changes)
    assert [row["annual_bus_km_cap"] for row in envelopes] == pytest.approx(
        [80000, 90000, 100000, 110000, 120000, 130000]
    )
    assert all(row["envelope_status"] == "PHASE2_DECLARED_DESIGN_SEARCH_ENVELOPE" for row in envelopes)


def test_duplicate_or_nonpositive_changes_fail_closed():
    with pytest.raises(ValueError, match="Duplicate"):
        parse_changes("0,0")
    with pytest.raises(ValueError, match="non-positive"):
        parse_changes("-1")
