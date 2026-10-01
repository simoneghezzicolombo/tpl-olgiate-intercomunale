import pytest

from src.phase2_rt031_hub_split_physical_probe_v3 import shortest_hub_split_walk
from src.phase2_rt031_rt023_pairwise_compatibility_v3 import LEGAL, ILLEGAL


def fixture():
    catalog = {
        "HW": {"source_stop_id": "H", "target_stop_id": "W"},
        "WH": {"source_stop_id": "W", "target_stop_id": "H"},
        "HE": {"source_stop_id": "H", "target_stop_id": "E"},
        "EH": {"source_stop_id": "E", "target_stop_id": "H"},
    }
    pairs = [
        {"left_realization_id": a, "right_realization_id": b, "status": LEGAL}
        for a in catalog for b in catalog
        if catalog[a]["target_stop_id"] == catalog[b]["source_stop_id"]
    ]
    return catalog, pairs, {r: "1" for r in catalog}, {
        "HW": ["H", "W"], "WH": ["W", "H"],
        "HE": ["H", "E"], "EH": ["E", "H"],
    }


def run(*, west=(("W",),), east=(("E",),)):
    catalog, pairs, weights, stops = fixture()
    return shortest_hub_split_walk(
        catalog, pairs, weights, stops, hub_stop_id="H",
        west_target_groups=west, east_target_groups=east,
        history_locality_certified=True, atomic_legality_certified=True)


def test_two_distinct_hub_lobes_have_a_physical_lower_bound():
    result = run()
    assert result["pairwise_graph_lower_bound_m"] == "4"
    assert result["west_realization_ids"] == ["HW", "WH"]
    assert result["east_realization_ids"] == ["HE", "EH"]
    assert result["public_service_certified"] is False


def test_missing_lobe_target_fails_closed():
    with pytest.raises(ValueError, match="absent"):
        run(east=(("UNSEEN",),))


def test_no_switch_before_first_hub_return():
    catalog, pairs, weights, stops = fixture()
    result = shortest_hub_split_walk(
        catalog, pairs, weights, stops, hub_stop_id="H",
        west_target_groups=(("W",), ("E",)), east_target_groups=(("E",),),
        history_locality_certified=True, atomic_legality_certified=True)
    assert result["pairwise_graph_lower_bound_m"] is None
    assert result["west_realization_ids"] == []


def test_illegal_intermediate_hub_transition_cannot_join_lobes():
    catalog, pairs, weights, stops = fixture()
    for pair in pairs:
        if pair["left_realization_id"] == "WH" and pair["right_realization_id"] == "HE":
            pair["status"] = ILLEGAL
    result = shortest_hub_split_walk(
        catalog, pairs, weights, stops, hub_stop_id="H",
        west_target_groups=(("W",),), east_target_groups=(("E",),),
        history_locality_certified=True, atomic_legality_certified=True)
    assert result["pairwise_graph_lower_bound_m"] is None


def test_uncertified_history_scope_fails_closed():
    catalog, pairs, weights, stops = fixture()
    with pytest.raises(ValueError, match="certified physical"):
        shortest_hub_split_walk(
            catalog, pairs, weights, stops, hub_stop_id="H",
            west_target_groups=(("W",),), east_target_groups=(("E",),),
            history_locality_certified=False, atomic_legality_certified=True)


def test_ordered_lobe_targets_follow_available_stop_sequence():
    catalog = {
        "HW": {"source_stop_id": "H", "target_stop_id": "W"},
        "WE": {"source_stop_id": "W", "target_stop_id": "E"},
        "EH": {"source_stop_id": "E", "target_stop_id": "H"},
        "HX": {"source_stop_id": "H", "target_stop_id": "X"},
        "XH": {"source_stop_id": "X", "target_stop_id": "H"},
    }
    pairs = [
        {"left_realization_id": a, "right_realization_id": b, "status": LEGAL}
        for a in catalog for b in catalog
        if catalog[a]["target_stop_id"] == catalog[b]["source_stop_id"]
    ]
    stops = {rid: [row["source_stop_id"], row["target_stop_id"]]
             for rid, row in catalog.items()}
    arguments = dict(
        catalog=catalog, pairs=pairs, weights={rid: "1" for rid in catalog},
        stop_sets=stops, hub_stop_id="H", east_target_groups=(("X",),),
        history_locality_certified=True, atomic_legality_certified=True,
        ordered_within_lobes=True)
    ordered = shortest_hub_split_walk(
        **arguments, west_target_groups=(("W",), ("E",)))
    reversed_order = shortest_hub_split_walk(
        **arguments, west_target_groups=(("E",), ("W",)))
    assert ordered["pairwise_graph_lower_bound_m"] == "5"
    assert ordered["ordered_physical_target_presence_certified"] is True
    assert reversed_order["pairwise_graph_lower_bound_m"] is None
