from decimal import Decimal

import pytest

from scripts.phase2_build_s8_phasing_v2 import HUB_ANCHOR, route_runtime_components
from scripts.phase2_build_s8_phasing_v2_cached import representative_runtime_for_complete_phase_range
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


def _range_signature(runtime: Decimal, headway: int, span: Span, rail: list[RailEvent]):
    rows = [
        phase_raw_gap_metrics(
            rail_events=rail,
            cycle_runtime_min=runtime,
            headway_min=headway,
            span=span,
            phase_min=phase,
        )
        for phase in range(headway)
    ]
    keys = [key for key in rows[0] if key.endswith("_mean_gap_min") or key.endswith("_unmatched_count")]
    signature = {}
    for key in keys:
        values = [row[key] for row in rows if row[key] is not None]
        signature[key] = (min(values), max(values)) if values else (None, None)
    return signature


def test_complete_phase_range_is_exactly_invariant_to_runtime_integer_part():
    span = Span("test", 360, 480)
    rail = [
        RailEvent("M1", "MILANO", D("362"), D("363")),
        RailEvent("M2", "MILANO", D("392"), D("393")),
        RailEvent("M3", "MILANO", D("422"), D("423")),
        RailEvent("L1", "LECCO", D("372"), D("373")),
        RailEvent("L2", "LECCO", D("402"), D("403")),
        RailEvent("L3", "LECCO", D("432"), D("433")),
    ]
    headway = 20
    original = D("137.5")
    representative = representative_runtime_for_complete_phase_range(original, headway)
    assert representative == D("20.5")
    assert _range_signature(original, headway, span, rail) == _range_signature(representative, headway, span, rail)


def test_runtime_components_fail_closed_without_return_closure():
    with pytest.raises(ValueError, match="vehicle return closure"):
        route_runtime_components((HUB_ANCHOR, "stop:A"), {(HUB_ANCHOR, "stop:A"): D("5")})
