from __future__ import annotations

import pytest

from src.phase2_s8_scenario_feeder_envelope_v2 import RouteTimingGap, summarise_role


def gap(route_id: str, *, roundtrip: bool, complete: int, best: float | None, worst: float | None) -> RouteTimingGap:
    return RouteTimingGap(
        route_id=route_id,
        roundtrip_passenger_supported=roundtrip,
        complete_match_phase_count=complete,
        best_complete_phase_weighted_mean_gap_min=best,
        worst_complete_phase_weighted_mean_gap_min=worst,
    )


def test_role_summary_keeps_passenger_support_classes_separate_and_uses_extrema_only() -> None:
    rows = {
        "r1": gap("r1", roundtrip=True, complete=4, best=3.0, worst=9.0),
        "r2": gap("r2", roundtrip=True, complete=0, best=None, worst=None),
        "r3": gap("r3", roundtrip=False, complete=2, best=5.0, worst=12.0),
    }
    summary = summarise_role(["r1", "r2", "r3"], rows)
    assert summary["route_count"] == 3
    assert summary["complete_match_route_count"] == 2
    assert summary["complete_match_route_share"] == pytest.approx(2 / 3)
    assert summary["all_routes_have_some_complete_match_phase"] is False
    assert summary["any_route_has_some_complete_match_phase"] is True

    rt = summary["roundtrip"]
    assert rt["route_count"] == 2
    assert rt["complete_match_route_count"] == 1
    assert rt["complete_match_route_share"] == pytest.approx(0.5)
    assert rt["best_complete_gap_min_min"] == 3.0
    assert rt["best_complete_gap_min_max"] == 3.0
    assert rt["worst_complete_gap_min_min"] == 9.0
    assert rt["worst_complete_gap_min_max"] == 9.0

    one_way = summary["rail_to_bus_only"]
    assert one_way["route_count"] == 1
    assert one_way["complete_match_route_count"] == 1
    assert one_way["best_complete_gap_min_min"] == 5.0
    assert one_way["worst_complete_gap_min_max"] == 12.0


def test_empty_extension_role_is_explicitly_not_applicable_not_vacuously_true() -> None:
    summary = summarise_role([], {})
    assert summary["route_count"] == 0
    assert summary["complete_match_route_share"] is None
    assert summary["all_routes_have_some_complete_match_phase"] is None
    assert summary["any_route_has_some_complete_match_phase"] is None
    assert summary["roundtrip"]["all_routes_have_complete_match_phase"] is None
    assert summary["rail_to_bus_only"]["best_complete_gap_min_min"] is None


def test_duplicate_route_reference_fails_closed() -> None:
    rows = {"r1": gap("r1", roundtrip=True, complete=1, best=2.0, worst=3.0)}
    with pytest.raises(ValueError, match="duplicate route IDs"):
        summarise_role(["r1", "r1"], rows)


def test_missing_route_timing_gap_fails_closed() -> None:
    with pytest.raises(ValueError, match="missing route timing gap"):
        summarise_role(["missing"], {})


def test_no_complete_match_route_cannot_carry_gap_values() -> None:
    bad = gap("r1", roundtrip=True, complete=0, best=2.0, worst=None)
    with pytest.raises(ValueError, match="No-complete-match route"):
        bad.validate()


def test_complete_match_route_requires_ordered_finite_nonnegative_gaps() -> None:
    with pytest.raises(ValueError, match="cannot exceed"):
        gap("r1", roundtrip=True, complete=1, best=5.0, worst=4.0).validate()
    with pytest.raises(ValueError, match="finite and non-negative"):
        gap("r2", roundtrip=False, complete=1, best=-1.0, worst=4.0).validate()
