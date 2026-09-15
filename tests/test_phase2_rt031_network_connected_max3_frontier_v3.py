from decimal import Decimal
from fractions import Fraction

from scripts.phase2_build_rt031_network_connected_max3_frontier_v3 import (
    dominates,
    exact_row_vector,
)


def test_exact_row_vector_preserves_fractional_access_and_retention():
    row = {
        "exact_access_ratios": ["1/2", "2/3", "3/4", "4/5", "5/6", "6/7"],
        "retained_current_exact_stop_count": 8,
    }
    assert exact_row_vector(row, 11) == (
        Fraction(1, 2), Fraction(2, 3), Fraction(3, 4),
        Fraction(4, 5), Fraction(5, 6), Fraction(6, 7), Fraction(8, 11),
    )


def test_dominance_requires_no_worse_all_dimensions_and_strict_improvement():
    base = (Fraction(1, 2),) * 7
    better_one = (Fraction(2, 3),) + base[1:]
    worse_one = (Fraction(1, 3),) + base[1:]

    assert dominates(better_one, Decimal("10"), base, Decimal("10"))
    assert dominates(base, Decimal("9"), base, Decimal("10"))
    assert not dominates(base, Decimal("10"), base, Decimal("10"))
    assert not dominates(worse_one, Decimal("9"), base, Decimal("10"))
    assert not dominates(better_one, Decimal("11"), base, Decimal("10"))
