import math

from scripts.phase2_build_feeder_generalized_access_v2 import (
    HUB_ANCHOR,
    directional_base_metrics,
    nearest_rank,
    robust_timing_summary,
    route_anchor_ivt,
)


def test_open_route_never_uses_vehicle_closure_for_to_rail():
    anchors = (HUB_ANCHOR, "A", "B")
    runtime = {(HUB_ANCHOR, "A"): 5.0, ("A", "B"): 7.0}
    to_rail, from_rail = route_anchor_ivt(anchors, runtime)
    assert to_rail == {}
    assert from_rail == {"A": 5.0, "B": 12.0}


def test_closed_public_route_supports_both_feeder_directions():
    anchors = (HUB_ANCHOR, "A", "B", HUB_ANCHOR)
    runtime = {
        (HUB_ANCHOR, "A"): 5.0,
        ("A", "B"): 7.0,
        ("B", HUB_ANCHOR): 3.0,
    }
    to_rail, from_rail = route_anchor_ivt(anchors, runtime)
    assert to_rail == {"A": 10.0, "B": 3.0}
    assert from_rail == {"A": 5.0, "B": 12.0}


def test_intermediate_hub_resets_public_passenger_segment():
    anchors = (HUB_ANCHOR, "A", HUB_ANCHOR, "B", HUB_ANCHOR)
    runtime = {
        (HUB_ANCHOR, "A"): 4.0,
        ("A", HUB_ANCHOR): 6.0,
        (HUB_ANCHOR, "B"): 8.0,
        ("B", HUB_ANCHOR): 5.0,
    }
    to_rail, from_rail = route_anchor_ivt(anchors, runtime)
    assert to_rail == {"A": 6.0, "B": 5.0}
    assert from_rail == {"A": 4.0, "B": 8.0}


def test_directional_base_metric_selects_best_generalized_anchor_without_demand_imputation():
    anchor_ivt = {"A": 10.0, "B": 5.0}
    anchor_walks = {
        "A": {0: 1.0, 1: 4.0},
        "B": {0: 8.0, 1: 2.0},
    }
    pairs = ((1.0, 2.0, "B100_W200"),)
    result = directional_base_metrics(
        anchor_ivt,
        anchor_walks,
        weights=[2.0, 1.0, 3.0],
        municipalities=["M1", "M1", "M2"],
        feeder_mask=[True, True, True],
        feeder_denoms={"M1": 3.0, "M2": 3.0},
        pairs=pairs,
    )
    # Unit 0: A = 12, B = 21 -> A. Unit 1: A = 18, B = 9 -> B.
    assert math.isclose(result["reachable_population"], 3.0)
    assert math.isclose(result["reachable_share"], 0.5)
    assert result["worst_municipality"] == "M2"
    assert math.isclose(result["worst_municipality_share"], 0.0)
    assert math.isclose(result["means"]["B100_W200"], 11.0)
    assert math.isclose(result["worst_municipality_means"]["B100_W200"], 11.0)


def test_robust_timing_summary_adds_only_declared_common_screening_terms():
    cases = [
        {
            "bus_ivt_weight": 1.0,
            "walk_weight": 2.0,
            "wait_weight": 2.0,
            "transfer_penalty_min": 6.0,
            "station_transfer_walk_min": 2.0,
        }
    ]
    result = robust_timing_summary(
        {"B100_W200": 10.0},
        {"B100_W200": 12.0},
        20,
        cases,
    )
    # 10 + 2*2 transfer walk + 2*(20/2) wait + 6 transfer penalty = 40.
    assert result == {
        "minimum": 40.0,
        "median": 40.0,
        "p90": 40.0,
        "maximum": 40.0,
        "worst_municipality_minimum": 42.0,
        "worst_municipality_median": 42.0,
        "worst_municipality_p90": 42.0,
        "worst_municipality_maximum": 42.0,
    }


def test_nearest_rank_p90_is_conservative_order_statistic():
    values = list(range(1, 11))
    assert nearest_rank(values, 0.9) == 9
