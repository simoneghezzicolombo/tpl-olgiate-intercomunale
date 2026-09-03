from decimal import Decimal

import pytest

from scripts.phase2_build_s8_phasing_v2 import HUB_ANCHOR, route_runtime_components
from src.phase2_s8_phasing_v2 import RailEvent, Span, clockface_times, phase_raw_gap_metrics, steady_state_arrival_times


D = Decimal


def test_route_runtime_components_separate_public_service_from_vehicle_closure():
    runtimes = {
        (HUB_ANCHOR, "stop:A"): D("5"),
        ("stop:A", HUB_ANCHOR): D("7"),
    }
    public_runtime, cycle_runtime, closure_added = route_runtime_components((HUB_ANCHOR, "stop:A"), runtimes)
    assert public_runtime == D("5")
    assert cycle_runtime == D("12")
    assert closure_added is True

    public_runtime, cycle_runtime, closure_added = route_runtime_components((HUB_ANCHOR, "stop:A", HUB_ANCHOR), runtimes)
    assert public_runtime == D("12")
    assert cycle_runtime == D("12")
    assert closure_added is False


def test_clockface_and_vehicle_returns_are_distinct_event_series():
    span = Span("test", 360, 420)
    assert clockface_times(phase_min=5, headway_min=20, span=span) == (D("365"), D("385"), D("405"))
    assert steady_state_arrival_times(
        phase_min=5,
        headway_min=20,
        cycle_runtime_min=D("12.5"),
        span=span,
    ) == (D("377.5"), D("397.5"), D("417.5"))


def test_raw_gap_metrics_never_label_vehicle_cycle_return_as_bus_to_rail_passenger_service():
    span = Span("test", 360, 420)
    rail = [
        RailEvent("M1", "MILANO", D("362"), D("363")),
        RailEvent("M2", "MILANO", D("392"), D("393")),
        RailEvent("L1", "LECCO", D("372"), D("373")),
        RailEvent("L2", "LECCO", D("402"), D("403")),
    ]
    metrics = phase_raw_gap_metrics(
        rail_events=rail,
        cycle_runtime_min=D("12"),
        headway_min=20,
        span=span,
        phase_min=5,
    )
    assert any(key.startswith("vehicle_cycle_to_rail_") for key in metrics)
    assert not any(key.startswith("bus_to_rail_") for key in metrics)
    assert any(key.startswith("rail_to_bus_") for key in metrics)


def test_runtime_components_fail_closed_without_return_closure():
    with pytest.raises(ValueError, match="vehicle return closure"):
        route_runtime_components((HUB_ANCHOR, "stop:A"), {(HUB_ANCHOR, "stop:A"): D("5")})
