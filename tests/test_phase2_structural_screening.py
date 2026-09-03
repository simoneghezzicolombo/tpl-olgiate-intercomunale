from __future__ import annotations

import math
import pytest

from src.phase2_optimizer_core import PathLeg, ReducedPathMatrix
from src.phase2_structural_screening import (
    AnchorMeta,
    CatchmentRecord,
    build_catchment_index,
    catchment_union,
    intercepted_anchors_for_leg,
    lies_on_directed_shortest_path,
    route_legs,
    summarise_scenario_structure,
)


def matrix() -> ReducedPathMatrix:
    return ReducedPathMatrix(
        [
            PathLeg("A", "B", 2.0, 4.0, "QUANTIFIED"),
            PathLeg("A", "C", 1.0, 2.0, "RESOLVED"),
            PathLeg("C", "B", 1.0, 2.0, "UNKNOWN"),
            PathLeg("A", "D", 1.4, 2.8, "QUANTIFIED"),
            PathLeg("D", "B", 1.4, 2.8, "QUANTIFIED"),
            PathLeg("B", "A", 2.2, 4.4, "QUANTIFIED"),
            PathLeg("B", "C", 1.5, 3.0, "QUANTIFIED"),
            PathLeg("C", "A", 1.5, 3.0, "QUANTIFIED"),
            PathLeg("B", "D", 1.0, 2.0, "RESOLVED"),
            PathLeg("D", "A", 1.2, 2.4, "RESOLVED"),
            PathLeg("C", "D", 0.7, 1.4, "RESOLVED"),
            PathLeg("D", "C", 0.8, 1.6, "RESOLVED"),
        ]
    )


def meta() -> dict[str, AnchorMeta]:
    return {
        "A": AnchorMeta("A", "HUB_RAIL"),
        "B": AnchorMeta("B", "EXISTING_PHYSICAL_STOP_CLUSTER"),
        "C": AnchorMeta("C", "PROPOSED_STOP"),
        "D": AnchorMeta("D", "PROPOSED_STOP"),
    }


def test_directed_on_path_is_metric_and_asymmetric() -> None:
    m = matrix()
    assert lies_on_directed_shortest_path(
        m, origin="A", destination="B", candidate="C", abs_tol_km=0.0, rel_tol=0.0
    )
    assert not lies_on_directed_shortest_path(
        m, origin="B", destination="A", candidate="C", abs_tol_km=0.0, rel_tol=0.0
    )


def test_on_path_tolerance_is_caller_declared() -> None:
    m = ReducedPathMatrix(
        [
            PathLeg("A", "B", 2.0, 4.0),
            PathLeg("A", "C", 1.0002, 2.0),
            PathLeg("C", "B", 1.0, 2.0),
        ]
    )
    assert not lies_on_directed_shortest_path(
        m, origin="A", destination="B", candidate="C", abs_tol_km=0.0001, rel_tol=0.0
    )
    assert lies_on_directed_shortest_path(
        m, origin="A", destination="B", candidate="C", abs_tol_km=0.0003, rel_tol=0.0
    )


def test_missing_via_leg_does_not_create_interception() -> None:
    m = ReducedPathMatrix(
        [
            PathLeg("A", "B", 2.0, 4.0),
            PathLeg("A", "C", 1.0, 2.0),
        ]
    )
    assert not lies_on_directed_shortest_path(
        m, origin="A", destination="B", candidate="C", abs_tol_km=0.001, rel_tol=1e-6
    )


def test_leg_interception_always_contains_endpoints() -> None:
    got = intercepted_anchors_for_leg(
        matrix(),
        origin="A",
        destination="B",
        anchors=["A", "B", "C", "D"],
        abs_tol_km=0.0,
        rel_tol=0.0,
    )
    assert got == frozenset({"A", "B", "C"})


def test_open_route_is_not_silently_closed() -> None:
    result = summarise_scenario_structure(
        matrix(),
        routes=[["A", "C", "D"]],
        optional_extensions=[],
        anchor_meta=meta(),
        abs_tol_km=0.0,
        rel_tol=0.0,
    )
    assert result["public_leg_count"] == 2
    assert result["public_distance_km"] == pytest.approx(1.7)
    assert result["public_runtime_min"] == pytest.approx(3.4)
    # A route A-C-D is not auto-closed with D-A.
    assert result["public_distance_km"] != pytest.approx(2.9)


def test_public_and_optional_extension_metrics_remain_separate() -> None:
    result = summarise_scenario_structure(
        matrix(),
        routes=[["A", "B"]],
        optional_extensions=[["B", "D"]],
        anchor_meta=meta(),
        abs_tol_km=0.0,
        rel_tol=0.0,
    )
    assert result["public_distance_km"] == pytest.approx(2.0)
    assert result["extension_distance_km"] == pytest.approx(1.0)
    assert result["public_intercepted_existing_stop_count"] == 1
    assert result["public_intercepted_proposed_stop_count"] == 1  # C lies on A->B


def test_uncertainty_exposure_is_counted_and_summed_not_scored() -> None:
    result = summarise_scenario_structure(
        matrix(),
        routes=[["A", "C", "B"]],
        optional_extensions=[],
        anchor_meta=meta(),
        abs_tol_km=0.0,
        rel_tol=0.0,
    )
    assert result["public_resolved_leg_count"] == 1
    assert result["public_unknown_leg_count"] == 1
    assert result["public_quantified_leg_count"] == 0
    assert result["public_unknown_distance_km"] == pytest.approx(1.0)
    assert result["public_resolved_distance_km"] == pytest.approx(1.0)


def test_catchment_union_counts_each_unit_once() -> None:
    by_anchor, weights = build_catchment_index(
        [
            CatchmentRecord("S1", "U1", 10.0),
            CatchmentRecord("S1", "U2", 20.0),
            CatchmentRecord("S2", "U2", 20.0),
            CatchmentRecord("S2", "U3", 5.0),
        ]
    )
    units, total = catchment_union(["S1", "S2"], by_anchor=by_anchor, unit_weights=weights)
    assert units == frozenset({"U1", "U2", "U3"})
    assert total == pytest.approx(35.0)


def test_catchment_index_rejects_conflicting_unit_weights() -> None:
    with pytest.raises(ValueError, match="Conflicting weights"):
        build_catchment_index(
            [CatchmentRecord("S1", "U1", 10.0), CatchmentRecord("S2", "U1", 11.0)]
        )


def test_nonfinite_or_negative_values_fail_closed() -> None:
    with pytest.raises(ValueError):
        CatchmentRecord("S", "U", math.nan)
    with pytest.raises(ValueError):
        CatchmentRecord("S", "U", -1.0)
    with pytest.raises(ValueError):
        lies_on_directed_shortest_path(
            matrix(), origin="A", destination="B", candidate="C", abs_tol_km=math.inf, rel_tol=0.0
        )


def test_route_validation_rejects_implicit_degenerate_legs() -> None:
    with pytest.raises(ValueError):
        route_legs(["A"])
    with pytest.raises(ValueError):
        route_legs(["A", "A"])
