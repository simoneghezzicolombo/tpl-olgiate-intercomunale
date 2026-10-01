from decimal import Decimal
from fractions import Fraction

from scripts.phase2_audit_rt031_south_municipal_frontier_v3 import ratio


def test_exact_decimal_ratio():
    assert ratio(Decimal("0.3"), Decimal("0.4")) == "3/4"
    assert Fraction(ratio(Decimal("4030.9096422430187852"),
                          Decimal("4030.9096422430187852"))) == 1
