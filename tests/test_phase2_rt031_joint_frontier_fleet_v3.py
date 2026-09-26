from decimal import Decimal

import pytest

from scripts.phase2_screen_rt031_joint_frontier_fleet_v3 import exact_fleet


def test_exact_fleet_reuses_only_vehicles_ready_by_next_departure():
    departures = tuple(Decimal(value) for value in (0, 30, 60, 90))
    assert exact_fleet(departures, Decimal(30)) == 1
    assert exact_fleet(departures, Decimal(60)) == 2
    assert exact_fleet(departures, Decimal(61)) == 3


def test_nonpositive_cycle_fails_closed():
    with pytest.raises(ValueError, match="positive cycle"):
        exact_fleet((Decimal(0),), Decimal(0))
