from decimal import Decimal

import pytest

from scripts.phase2_build_s8_phasing_v2 import HUB_ANCHOR, route_runtime_components
from scripts.phase2_build_s8_phasing_v2_cached import (
    _require_integer_minute_rail_events,
    _translated_phase_metrics,
    representative_runtime_for_complete_phase_range,
)
from src.phase2_s8_phasing_v2 import RailEvent, Span, clockface_times, phase_raw_gap_metrics, steady_state_arrival_times


D = Decimal


def _rail():
    return [
        RailEvent("M1", "MILANO", D("362"), D("363")),
        RailEvent("M2", "MILANO", D("392"), D("393")),
        RailEvent("M3", "MILANO", D("422"), D("423")),
        RailEvent("L1", "LECCO", D("372"), D("373")),
        RailEvent("L2", "LECCO", D("402"), D("403")),
        RailEvent("L3", "LECCO", D("432"), D("433")),
    ]


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
    metrics = phase_raw_gap_metrics(
        rail_events=_rail(),
        cycle_runtime_min=D("12"),
        headway_min=20,
        span=Span("test", 360, 450),
        phase_min=5,
    )
    assert any(key.startswith("vehicle_cycle_to_rail_") for key in metrics)
    assert not any(key.startswith("bus_to_rail_") for key in metrics)
    assert any(key.startswith("rail_to_bus_") for key in metrics)


def _phase_rows(runtime: Decimal, headway: int, span: Span):
    return [
        phase_raw_gap_metrics(
            rail_events=_rail(),
            cycle_runtime_min=runtime,
            headway_min=headway,
            span=span,
            phase_min=phase,
        )
        for phase in range(headway)
    ]


def _range_signature(rows):
    keys = [key for key in rows[0] if key.endswith("_mean_gap_min") or key.endswith("_unmatched_count")]
    signature = {}
    for key in keys:
        values = [row[key] for row in rows if row[key] is not None]
        if key.endswith("_gap_min"):
            signature[key] = tuple(f"{value:.9f}" for value in (min(values), max(values))) if values else (None, None)
        else:
            signature[key] = (min(values), max(values)) if values else (None, None)
    return signature


def test_complete_phase_range_is_exactly_invariant_to_runtime_integer_part():
    span = Span("test", 360, 450)
    headway = 20
    original = D("137.5")
    representative = representative_runtime_for_complete_phase_range(original, headway)
    assert representative == D("20.5")
    assert _range_signature(_phase_rows(original, headway, span)) == _range_signature(
        _phase_rows(representative, headway, span)
    )


@pytest.mark.parametrize("actual", [D("137.25"), D("137.75"), D("20.125")])
def test_positive_fraction_translation_matches_direct_phase_metrics_at_persisted_precision(actual):
    span = Span("test", 360, 450)
    headway = 20
    representative = D("20.5")
    base_rows = _phase_rows(representative, headway, span)
    transformed = _translated_phase_metrics(base_rows, actual_fraction=actual % D("1"))
    direct = _phase_rows(actual, headway, span)
    assert _range_signature(transformed) == _range_signature(direct)


def test_fraction_compression_fails_closed_for_subminute_rail_event():
    rail = _rail()
    rail[0] = RailEvent("M1", "MILANO", D("362.5"), D("363.5"))
    with pytest.raises(ValueError, match="integer-minute S8"):
        _require_integer_minute_rail_events(rail)


def test_runtime_components_fail_closed_without_return_closure():
    with pytest.raises(ValueError, match="vehicle return closure"):
        route_runtime_components((HUB_ANCHOR, "stop:A"), {(HUB_ANCHOR, "stop:A"): D("5")})
