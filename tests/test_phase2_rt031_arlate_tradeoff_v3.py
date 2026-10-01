from fractions import Fraction

from scripts.phase2_compare_rt031_arlate_tradeoff_v3 import vector


def test_vector_preserves_exact_no_weight_axes():
    row = {
        "exact_total_coverage": {"5": "1/2", "8": "2/3", "10": "3/4"},
        "exact_municipality_coverage": {
            "a": {"5": "1/3", "8": "1/2", "10": "2/3"}},
        "retained_current_exact_stop_count": 6,
    }
    assert vector(row, ("a",)) == (
        Fraction(1, 2), Fraction(2, 3), Fraction(3, 4),
        Fraction(1, 3), Fraction(1, 2), Fraction(2, 3), Fraction(6, 11))
