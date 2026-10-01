from decimal import Decimal

import pytest

from src.phase2_rt031_single_line_binding_v3 import (
    municipal_frontier_within_cap,
)


def candidate(identity, distance="1000", *, hub=True):
    stops = ["FROZEN::L00407", "S"] if hub else ["S"]
    return {
        "candidate_line_id": identity,
        "total_distance_m": distance,
        "conditional_annual_bus_km_at_20_daily_cycles": str(
            Decimal(distance) * 20 * 260 / 1000),
        "available_stop_ids": stops,
        "realization_ids": ["R1"],
        "exact_municipality_coverage": {
            code: {threshold: "1/2" for threshold in ("5", "8", "10")}
            for code in ("A", "B", "C", "D", "E")
        },
    }


def test_municipal_frontier_cap_is_exact_and_not_a_retention_filter():
    within = candidate("within", "1000")
    within["retained_current_exact_stop_count"] = 0
    over = candidate("over", "3000")
    assert municipal_frontier_within_cap(
        [over, within], annual_bus_km_cap="6000") == [within]


def test_municipal_frontier_validation_fails_closed():
    bad = candidate("bad", hub=False)
    with pytest.raises(ValueError, match="semantics drift"):
        municipal_frontier_within_cap([bad], annual_bus_km_cap="111419")

    duplicate = candidate("same")
    with pytest.raises(ValueError, match="unique"):
        municipal_frontier_within_cap(
            [duplicate, dict(duplicate)], annual_bus_km_cap="111419")
