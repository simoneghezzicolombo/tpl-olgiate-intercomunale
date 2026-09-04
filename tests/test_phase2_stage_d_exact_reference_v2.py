from decimal import Decimal

from src.phase2_stage_d_exact_reference_v2 import (
    ExactRailEvent,
    ExactRoute,
    TransferProfile,
    clockface_departures,
    materialise_route_trips,
    minimum_common_hub_blocks,
    phase_vector_objective,
    route_phase_evidence,
    source_centric_cell,
)

D = Decimal


def profiles():
    return [
        TransferProfile("LOW", 1.5, 3.0, 1.0, 8.0),
        TransferProfile("MID", 2.0, 4.0, 1.5, 12.0),
        TransferProfile("HIGH", 3.0, 5.0, 2.0, 15.0),
    ]


def rail_events():
    # Synthetic timing fixture only for unit-test mathematics, never production evidence.
    rows = []
    for direction, offset in (("MILANO", 6), ("LECCO", 13)):
        for hour in (6, 7, 8):
            dep = D(hour * 60 + offset)
            rows.append(ExactRailEvent(f"{direction}-{hour}", direction, dep - 1, dep))
    return rows


def test_clockface_departures_are_end_exclusive_and_phase_sensitive():
    assert clockface_departures(phase_min=0, headway_min=30, span_start_min=360, span_end_min=420) == (D(360), D(390))
    assert clockface_departures(phase_min=5, headway_min=30, span_start_min=360, span_end_min=420) == (D(365), D(395))


def test_open_route_technical_return_never_creates_bus_to_rail_quality_cells():
    route = ExactRoute("OPEN", D("12"), D("20"), D("8"), False)
    evidence = route_phase_evidence(
        route,
        phase_min=0,
        headway_min=30,
        span_start_min=360,
        span_end_min=540,
        rail_events=rail_events(),
        profiles=profiles(),
    )
    assert len(evidence.cell_labels) == 6
    assert all("RAIL_TO_BUS" in label for label in evidence.cell_labels)
    assert all("BUS_TO_RAIL" not in label for label in evidence.cell_labels)


def test_closed_route_has_both_connection_directions_for_all_profiles_and_rail_directions():
    route = ExactRoute("LOOP", D("20"), D("20"), D("8"), True)
    evidence = route_phase_evidence(
        route,
        phase_min=0,
        headway_min=30,
        span_start_min=360,
        span_end_min=540,
        rail_events=rail_events(),
        profiles=profiles(),
    )
    assert len(evidence.cell_labels) == 12
    assert sum("RAIL_TO_BUS" in x for x in evidence.cell_labels) == 6
    assert sum("BUS_TO_RAIL" in x for x in evidence.cell_labels) == 6


def test_source_centric_cell_reports_physical_miss_without_hard_thresholding_quality():
    profile = profiles()[1].as_model_profile()
    quality, miss = source_centric_cell(
        source_times_min=[D(100)],
        target_times_min=[D(99)],
        connection_type="RAIL_TO_BUS",
        profile=profile,
    )
    assert 0.0 <= quality <= 1.0
    assert miss == 1.0


def test_common_hub_block_colouring_is_exact_for_overlapping_cycles():
    route = ExactRoute("R", D("20"), D("40"), D("10"), False)
    trips = materialise_route_trips(route, phase_min=0, headway_min=30, span_start_min=360, span_end_min=450)
    fleet5, blocks5 = minimum_common_hub_blocks(trips, recovery_min=5)
    fleet20, blocks20 = minimum_common_hub_blocks(trips, recovery_min=20)
    assert len(blocks5) == len(trips) == 3
    assert fleet5 == 2
    assert fleet20 == 2


def test_phase_vector_objective_is_unweighted_across_supported_route_cells():
    route_a = ExactRoute("A", D("20"), D("20"), D("8"), True)
    route_b = ExactRoute("B", D("12"), D("20"), D("6"), False)
    a = route_phase_evidence(route_a, phase_min=0, headway_min=30, span_start_min=360, span_end_min=540, rail_events=rail_events(), profiles=profiles())
    b = route_phase_evidence(route_b, phase_min=0, headway_min=30, span_start_min=360, span_end_min=540, rail_events=rail_events(), profiles=profiles())
    qmin, qmean = phase_vector_objective([a, b])
    all_values = list(a.cell_mean_quality) + list(b.cell_mean_quality)
    assert qmin == min(all_values)
    assert abs(qmean - sum(all_values) / len(all_values)) < 1e-15
