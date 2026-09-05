import pytest

from src.phase2_cross_engine_discrepancy_v3 import (
    ODTravelTime,
    compare_engines,
    summarize_discrepancies,
)


def rows(values):
    return [ODTravelTime(a, b, t) for a, b, t in values]


def test_exact_matrices_have_zero_discrepancy():
    a = rows([("O1", "D1", 5), ("O1", "D2", 9)])
    b = rows([("O1", "D1", 5), ("O1", "D2", 9)])
    diff = compare_engines(a, b, engine_a_label="A", engine_b_label="B")
    assert all(r.absolute_difference_min == 0 for r in diff)
    s = summarize_discrepancies(diff)
    assert s["max_absolute_difference_min"] == 0


def test_input_order_does_not_change_comparison():
    a = rows([("O2", "D1", 8), ("O1", "D1", 5)])
    b = rows([("O1", "D1", 6), ("O2", "D1", 7)])
    x = compare_engines(a, b, engine_a_label="A", engine_b_label="B")
    y = compare_engines(list(reversed(a)), list(reversed(b)), engine_a_label="A", engine_b_label="B")
    assert x == y


def test_missing_extra_and_duplicate_od_fail_closed():
    a = rows([("O1", "D1", 5), ("O1", "D2", 9)])
    with pytest.raises(ValueError, match="OD_ALIGNMENT_ERROR"):
        compare_engines(a, rows([("O1", "D1", 5)]), engine_a_label="A", engine_b_label="B")
    with pytest.raises(ValueError, match="OD_ALIGNMENT_ERROR"):
        compare_engines(rows([("O1", "D1", 5)]), a, engine_a_label="A", engine_b_label="B")
    with pytest.raises(ValueError, match="duplicate OD key"):
        compare_engines(
            rows([("O1", "D1", 5), ("O1", "D1", 6)]),
            rows([("O1", "D1", 5)]),
            engine_a_label="A",
            engine_b_label="B",
        )


def test_large_disagreement_remains_visible():
    a = rows([("O1", "D1", 5), ("O1", "D2", 10), ("O2", "D1", 8), ("O2", "D2", 7)])
    b = rows([("O1", "D1", 5), ("O1", "D2", 10), ("O2", "D1", 8), ("O2", "D2", 27)])
    diff = compare_engines(a, b, engine_a_label="A", engine_b_label="B")
    s = summarize_discrepancies(diff)
    assert s["max_absolute_difference_min"] == 20
    assert s["p95_absolute_difference_min"] == 20
    assert s["share_abs_diff_le_5_min"] == 0.75


def test_signed_difference_preserves_direction():
    diff = compare_engines(
        rows([("O1", "D1", 10), ("O2", "D1", 10)]),
        rows([("O1", "D1", 13), ("O2", "D1", 6)]),
        engine_a_label="A",
        engine_b_label="B",
    )
    assert diff[0].signed_difference_min == 3
    assert diff[1].signed_difference_min == -4


def test_zero_denominator_has_no_infinite_relative_difference():
    diff = compare_engines(
        rows([("O1", "D1", 0), ("O2", "D1", 5)]),
        rows([("O1", "D1", 2), ("O2", "D1", 10)]),
        engine_a_label="A",
        engine_b_label="B",
    )
    assert diff[0].relative_difference_vs_a is None
    s = summarize_discrepancies(diff)
    assert s["relative_difference_undefined_count"] == 1
    assert s["relative_difference_defined_count"] == 1


def test_reporting_bands_are_diagnostics_not_equivalence_claims():
    diff = compare_engines(
        rows([("O1", "D1", 5)]),
        rows([("O1", "D1", 5.5)]),
        engine_a_label="A",
        engine_b_label="B",
    )
    s = summarize_discrepancies(diff, reporting_bands_min=(1, 3))
    assert s["share_abs_diff_le_1_min"] == 1.0
    assert s["reporting_bands_are_diagnostic_only"] is True
    assert s["automatic_equivalence_claim"] is False
    assert s["engine_average_constructed"] is False
