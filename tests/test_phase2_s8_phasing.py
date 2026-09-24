from __future__ import annotations

import pytest

from src.phase2_s8_phasing import (
    PhasingProfile,
    choose_robust_phase,
    choose_robust_phase_grid,
    clockface_transfer_quality,
    extension_pattern,
    rail_clockface_offsets,
    route_cycle_runtime,
)


def rail_events():
    # Synthetic fixtures are test-only. Production S8 evidence is the certified
    # 2026-09-03 official-GTFS-derived event table.
    return [
        {"direction": "MILANO", "arrival_min": 25.0, "departure_min": 26.0},
        {"direction": "MILANO", "arrival_min": 55.0, "departure_min": 56.0},
        {"direction": "LECCO", "arrival_min": 2.0, "departure_min": 3.0},
        {"direction": "LECCO", "arrival_min": 32.0, "departure_min": 33.0},
    ]


def profiles():
    return [
        PhasingProfile("A", 1.5, 3.0, 1.0, 8.0),
        PhasingProfile("B", 2.0, 4.0, 1.5, 12.0),
        PhasingProfile("C", 3.0, 5.0, 2.0, 15.0),
    ]


def test_rail_clockface_requires_exact_half_hour_offsets():
    offsets = rail_clockface_offsets(rail_events())
    assert offsets[("BUS_TO_RAIL", "MILANO")] == (26.0, 56.0)
    broken = rail_events()
    broken[1] = {**broken[1], "departure_min": 57.0}
    with pytest.raises(ValueError, match="exact half-hour"):
        rail_clockface_offsets(broken)


def test_clockface_quality_is_thirty_minute_periodic():
    profile = profiles()[1].as_transfer_profile()
    q1 = clockface_transfer_quality(
        10.25,
        first_rail_offset_min=26.0,
        connection_type="BUS_TO_RAIL",
        profile=profile,
    )
    q2 = clockface_transfer_quality(
        40.25,
        first_rail_offset_min=26.0,
        connection_type="BUS_TO_RAIL",
        profile=profile,
    )
    assert q1 == pytest.approx(q2)
    assert 0.0 <= q1 <= 1.0


def test_extension_patterns_conserve_declared_share_across_headways():
    for headway in (15, 20, 30, 60):
        for share in (0.0, 0.25, 0.5, 1.0):
            rotations = range(4) if share == 0.25 else range(2) if share == 0.5 else range(1)
            for rotation in rotations:
                flags, n = extension_pattern(
                    headway_min=headway,
                    extension_share=share,
                    rotation=rotation,
                )
                assert n == len(flags)
                assert sum(flags) / n == pytest.approx(share)


def test_route_cycle_runtime_adds_only_required_certified_return():
    lookup = {
        ("H", "A"): 7.0,
        ("A", "H"): 8.0,
        ("A", "B"): 4.0,
        ("B", "H"): 6.0,
    }
    assert route_cycle_runtime(["H", "A", "H"], lookup) == 15.0
    assert route_cycle_runtime(["H", "A", "B"], lookup) == 17.0
    with pytest.raises(ValueError, match="return leg"):
        route_cycle_runtime(["H", "A"], {("H", "A"): 7.0})


def test_robust_phase_is_deterministic_and_not_passenger_weighted():
    first = choose_robust_phase(
        headway_min=30,
        public_route_runtimes_min=[43.25, 52.75],
        extension_share=0.0,
        extension_runtime_min=None,
        rail_events=rail_events(),
        profiles=profiles(),
    )
    second = choose_robust_phase(
        headway_min=30,
        public_route_runtimes_min=[52.75, 43.25],
        extension_share=0.0,
        extension_runtime_min=None,
        rail_events=rail_events(),
        profiles=profiles(),
    )
    assert first == second
    assert 0 <= first["phase_offset_min"] < 30
    assert 0 <= first["robust_min_transfer_quality"] <= 1
    assert len(first["profile_cell_quality"]) == 12


def test_scheduled_extension_search_uses_real_base_and_extension_runtimes():
    grid = choose_robust_phase_grid(
        headways_min=[20],
        public_route_runtimes_min=[35.0],
        extension_shares=[0.0, 0.25, 0.5, 1.0],
        extension_runtime_min=49.0,
        rail_events=rail_events(),
        profiles=profiles(),
    )
    assert set(grid) == {(20, 0.0), (20, 0.25), (20, 0.5), (20, 1.0)}
    assert grid[(20, 0.25)]["extension_pattern_period_departures"] == 12
    assert grid[(20, 0.5)]["extension_pattern_period_departures"] == 6
    assert grid[(20, 1.0)]["extension_pattern_period_departures"] == 3


def test_positive_extension_share_fails_without_extension_runtime():
    with pytest.raises(ValueError, match="extension_runtime"):
        choose_robust_phase_grid(
            headways_min=[30],
            public_route_runtimes_min=[35.0],
            extension_shares=[0.5],
            extension_runtime_min=None,
            rail_events=rail_events(),
            profiles=profiles(),
        )
