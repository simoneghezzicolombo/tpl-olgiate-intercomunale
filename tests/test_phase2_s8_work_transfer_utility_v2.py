import pytest

from src.phase2_s8_work_transfer_utility_v2 import (
    WorkDirectionWeights,
    weight_transfer_quality,
)


def cells():
    return {
        "A|BUS_TO_RAIL|LECCO": 0.8,
        "A|BUS_TO_RAIL|MILANO": 0.6,
        "A|RAIL_TO_BUS|LECCO": 0.4,
        "A|RAIL_TO_BUS|MILANO": 1.0,
        "B|BUS_TO_RAIL|LECCO": 0.5,
        "B|BUS_TO_RAIL|MILANO": 0.5,
        "B|RAIL_TO_BUS|LECCO": 0.5,
        "B|RAIL_TO_BUS|MILANO": 0.5,
    }


def test_empirical_roundtrip_direction_weighting_is_exact():
    weights = WorkDirectionWeights(
        outbound_bus_to_rail={"LECCO": 1.0, "MILANO": 3.0},
        return_rail_to_bus={"LECCO": 3.0, "MILANO": 1.0},
    )
    out = weight_transfer_quality(cells(), weights)
    # Profile A: (1*.8 + 3*.6 + 3*.4 + 1*1.0) / 8 = 0.6
    assert out.profile_quality["A"] == pytest.approx(0.6)
    assert out.profile_quality["B"] == pytest.approx(0.5)
    assert out.worst_profile_quality == pytest.approx(0.5)
    assert out.mean_profile_quality == pytest.approx(0.55)
    assert out.best_profile_quality == pytest.approx(0.6)
    assert out.worker_count == pytest.approx(4.0)
    assert out.weighted_connection_count == pytest.approx(8.0)


def test_direction_weights_require_same_outbound_and_return_total():
    weights = WorkDirectionWeights(
        outbound_bus_to_rail={"LECCO": 1.0, "MILANO": 3.0},
        return_rail_to_bus={"LECCO": 2.0, "MILANO": 1.0},
    )
    with pytest.raises(ValueError, match="totals must match"):
        weights.validate()


def test_profile_cells_fail_closed_when_incomplete():
    weights = WorkDirectionWeights(
        outbound_bus_to_rail={"LECCO": 1.0, "MILANO": 1.0},
        return_rail_to_bus={"LECCO": 1.0, "MILANO": 1.0},
    )
    incomplete = cells()
    del incomplete["B|RAIL_TO_BUS|MILANO"]
    with pytest.raises(ValueError, match="incomplete"):
        weight_transfer_quality(incomplete, weights)
