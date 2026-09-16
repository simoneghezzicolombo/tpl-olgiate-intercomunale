from src.phase2_rt031_mixed_frequency_surface_v4 import (
    exact_vehicle_count_for_departures,
    mixed_pareto_frontier,
    mixed_service_templates,
    phased_departures,
)
from src.phase2_exact_timetable_optimizer_v2 import RouteInput


def test_templates_trade_peak_hours_for_longer_span_at_equal_departures():
    templates = mixed_service_templates()
    assert [row["span_minutes"] for row in templates] == [720, 840, 960, 1080]
    assert [row["h30_peak_hours"] for row in templates] == [8, 6, 4, 2]
    assert [row["h60_base_hours"] for row in templates] == [12, 14, 16, 18]
    assert [row["h60_offpeak_hours"] for row in templates] == [4, 8, 12, 16]
    for row in templates:
        assert (row["h30_peak_hours"] + row["h60_offpeak_hours"]
                == row["span_minutes"] // 60)
        departures = phased_departures(row, 0)
        assert len(departures) == 20
        assert set(b - a for a, b in zip(departures, departures[1:])) <= {30, 60}


def test_phase_preserves_departure_count_and_moves_every_trip_together():
    template = mixed_service_templates()[-1]
    assert tuple(value + 17 for value in phased_departures(template, 0)) == (
        phased_departures(template, 17))


def test_exact_vehicle_count_uses_explicit_mixed_departures():
    route = RouteInput("R", 45, 45, True, True, False, True, True)
    assert exact_vehicle_count_for_departures(route, (0, 30, 60, 120), 10) == 2


def test_mixed_frontier_keeps_span_coverage_tradeoff_and_drops_dominated():
    def row(identity, span, brivio, quality, annual):
        return {
            "profile_id": identity,
            "template_id": "T",
            "phase_min": 0,
            "exact_total_coverage": {value: "1/2" for value in ("5", "8", "10")},
            "exact_municipality_coverage": {
                code: {value: (brivio if code == "A" else "1/2")
                       for value in ("5", "8", "10")}
                for code in ("A", "B", "C", "D", "E")
            },
            "retained_current_exact_stop_count": 9,
            "span_minutes": span,
            "h30_peak_hours": 4,
            "robust_min_transfer_quality": quality,
            "robust_unweighted_mean_transfer_quality": quality,
            "conditional_annual_bus_km": annual,
            "maximum_exact_vehicle_count": 3,
            "worst_deterministic_bus_to_rail_miss_share_by_runtime_stress_min": {
                value: .2 for value in ("0", "5", "10", "15")},
        }
    strong = row("strong", 960, "1/2", .5, "100000")
    dominated = row("dominated", 840, "1/2", .4, "101000")
    territorial = row("territorial", 840, "3/4", .4, "101000")
    assert mixed_pareto_frontier(
        (strong, dominated, territorial), ("A", "B", "C", "D", "E")) == [
            strong, territorial]
