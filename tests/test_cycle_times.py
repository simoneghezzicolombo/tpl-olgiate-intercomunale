"""Gate E regression tests for cycle/headway semantics.

Legacy route-variant constants are intentionally not asserted here. Gate E must
validate formulas against explicit inputs rather than preserve old outputs.
"""

from src.service_math import combined_headway_rate_equivalent, cycle_minutes, vehicles_required


def test_cycle_components_are_explicit():
    assert cycle_minutes(50.0, 5.0, 5.0) == 60.0


def test_one_bus_each_direction_does_not_mean_30_minutes_each_direction():
    cycle = 60.0
    assert vehicles_required(cycle, 60.0) == 1
    assert combined_headway_rate_equivalent(60.0, 60.0) == 30.0


def test_thirty_minutes_each_direction_requires_four_buses_on_sixty_minute_cycle():
    cycle = 60.0
    total = vehicles_required(cycle, 30.0) + vehicles_required(cycle, 30.0)
    assert total == 4
    assert combined_headway_rate_equivalent(30.0, 30.0) == 15.0
