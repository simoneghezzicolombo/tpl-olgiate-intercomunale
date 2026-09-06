from __future__ import annotations

import pandas as pd
import pytest

from phase2_candidate_accessibility_pareto_v3 import (
    DECISION_SCENARIO,
    RT029ContractError,
    compile_rt029,
)


def _structures() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "structure_id": "C1",
            "link_ids": "L1;L2;L3;L4",
            "vertex_ids": "S00;S01;S02;S03;S04",
            "topology_class": "PATH",
            "vertex_count": 5,
            "edge_count": 4,
            "cycle_rank": 0,
            "contract": "ABSTRACT_NETWORK_STRUCTURES_NOT_TERRITORIAL_RECOMMENDATIONS",
        },
        {
            "structure_id": "C2",
            "link_ids": "L5;L6;L7;L8",
            "vertex_ids": "S10;S11;S12;S13;S14",
            "topology_class": "TREE_BRANCHING",
            "vertex_count": 5,
            "edge_count": 4,
            "cycle_rank": 0,
            "contract": "ABSTRACT_NETWORK_STRUCTURES_NOT_TERRITORIAL_RECOMMENDATIONS",
        },
    ])


def _manifest() -> pd.DataFrame:
    rows = []
    for sid, links in [("C1", ["L1", "L2", "L3", "L4"]), ("C2", ["L5", "L6", "L7", "L8"])]:
        for i, link in enumerate(links, 1):
            rows.append({
                "structure_id": sid,
                "structure_link_ordinal": i,
                "structural_link_id": link,
            })
    return pd.DataFrame(rows)


def _realizations() -> pd.DataFrame:
    endpoints = {
        "L1": ("S00", "S01"),
        "L2": ("S01", "S02"),
        "L3": ("S02", "S03"),
        "L4": ("S03", "S04"),
        "L5": ("S10", "S11"),
        "L6": ("S11", "S12"),
        "L7": ("S12", "S13"),
        "L8": ("S13", "S14"),
    }
    rows = []
    for link, (a, b) in endpoints.items():
        for direction, source, target in [
            ("A_TO_B", a, b),
            ("B_TO_A", b, a),
        ]:
            stops = f"{source};{target}"
            rows.append({
                "structural_link_id": link,
                "direction": direction,
                "alternative_ordinal": 1,
                "ordered_passenger_stop_place_ids": stops,
                "distance_m": 1000.0 if link.startswith("L1") else 1200.0,
                "running_minutes_model": 4.0,
            })
    rows = [
        row for row in rows
        if not (row["structural_link_id"] == "L1" and row["direction"] == "A_TO_B")
    ]
    rows.extend([
        {
            "structural_link_id": "L1",
            "direction": "A_TO_B",
            "alternative_ordinal": 1,
            "ordered_passenger_stop_place_ids": "S00;S05;S01",
            "distance_m": 900.0,
            "running_minutes_model": 3.5,
        },
        {
            "structural_link_id": "L1",
            "direction": "A_TO_B",
            "alternative_ordinal": 2,
            "ordered_passenger_stop_place_ids": "S00;S06;S01",
            "distance_m": 1100.0,
            "running_minutes_model": 4.5,
        },
    ])
    return pd.DataFrame(rows)


def _walk() -> pd.DataFrame:
    rows = []
    for stop_i in range(35):
        stop = f"S{stop_i:02d}"
        for pop, weight, scope, muni in [
            ("P_CORE_A", 10.0, "core", "A"),
            ("P_CORE_B", 10.0, "core", "B"),
            ("P_EXT", 5.0, "external", "X"),
        ]:
            if pop == "P_CORE_A":
                time = 2.0 + (stop_i % 7)
                status = "REACHABLE"
            elif pop == "P_CORE_B":
                if 10 <= stop_i <= 14:
                    time = 6.0
                    status = "REACHABLE"
                else:
                    time = None
                    status = "UNREACHABLE"
            else:
                time = 9.0
                status = "REACHABLE"
            rows.append({
                "population_unit_id": pop,
                "population_weight_2025": weight,
                "population_scope": scope,
                "population_municipality_name": muni,
                "stop_place_id": stop,
                "stop_service_class": "CONVENTIONAL_TPL",
                "walk_time_min": time,
                "reachability_status": status,
            })
    for pop, weight, scope, muni in [
        ("P_CORE_A", 10.0, "core", "A"),
        ("P_CORE_B", 10.0, "core", "B"),
        ("P_EXT", 5.0, "external", "X"),
    ]:
        rows.append({
            "population_unit_id": pop,
            "population_weight_2025": weight,
            "population_scope": scope,
            "population_municipality_name": muni,
            "stop_place_id": "SPECIAL",
            "stop_service_class": "SPECIAL_SERVICE",
            "walk_time_min": 1.0,
            "reachability_status": "REACHABLE",
        })
    return pd.DataFrame(rows)


def _compile(**overrides):
    args = {
        "structures": _structures(),
        "structure_link_manifest": _manifest(),
        "realizations": _realizations(),
        "walk_matrix": _walk(),
        "expected_structure_count": 2,
        "expected_core_municipality_count": 2,
        "lineage": {"fixture": "controlled_unit_test_only"},
    }
    args.update(overrides)
    return compile_rt029(**args)


def test_guaranteed_intersection_excludes_optional_alternative_stops() -> None:
    result = _compile()
    c1 = result.stop_sets[result.stop_sets.structure_id == "C1"].set_index("scenario")
    guaranteed = set(c1.loc[DECISION_SCENARIO, "ordered_stop_place_ids"].split(";"))
    possible = set(c1.loc["POSSIBLE_RT023", "ordered_stop_place_ids"].split(";"))
    assert "S05" not in guaranteed
    assert "S06" not in guaranteed
    assert {"S05", "S06"}.issubset(possible)
    assert c1.loc[DECISION_SCENARIO, "decision_eligible"]
    assert not c1.loc["POSSIBLE_RT023", "decision_eligible"]


def test_unreachable_population_stays_in_threshold_denominator() -> None:
    result = _compile()
    row = result.accessibility_summary[
        (result.accessibility_summary.structure_id == "C1")
        & (result.accessibility_summary.scenario == DECISION_SCENARIO)
        & (result.accessibility_summary.scope == "CORE")
    ].iloc[0]
    assert row.reachable_population_share == pytest.approx(0.5)
    assert row.unreachable_population_share == pytest.approx(0.5)
    assert row.share_le_5_min <= 0.5


def test_core_municipality_equity_preserves_zero_access() -> None:
    result = _compile()
    row = result.equity_summary[
        (result.equity_summary.structure_id == "C1")
        & (result.equity_summary.scenario == DECISION_SCENARIO)
        & (result.equity_summary.threshold_min == 10.0)
    ].iloc[0]
    assert row.minimum_core_municipality_share == 0.0
    assert row.core_municipality_share_gap >= 0.0


def test_possible_union_is_never_used_for_pareto() -> None:
    result = _compile()
    assert set(result.pareto_frontiers.structure_id).issubset({"C1", "C2"})
    assert result.audit["decision_scenario"] == DECISION_SCENARIO
    assert result.audit["negative_assertions"]["uses_possible_union_for_pareto"] is False
    assert result.audit["negative_assertions"]["uses_weighted_composite_score"] is False
    assert result.audit["negative_assertions"]["selects_primary_or_runner_up"] is False


def test_operating_envelope_keeps_realization_uncertainty() -> None:
    result = _compile()
    c1 = result.operating_envelope.set_index("structure_id").loc["C1"]
    assert c1.minimum_bidirectional_link_distance_m < c1.maximum_bidirectional_link_distance_m
    assert (
        c1.minimum_bidirectional_link_running_minutes_model
        < c1.maximum_bidirectional_link_running_minutes_model
    )


def test_manifest_mismatch_fails_closed() -> None:
    bad = _manifest().iloc[:-1].copy()
    with pytest.raises(RT029ContractError, match="manifest mismatch"):
        _compile(structure_link_manifest=bad)


def test_missing_direction_fails_closed() -> None:
    bad = _realizations()
    bad = bad[~((bad.structural_link_id == "L2") & (bad.direction == "B_TO_A"))]
    with pytest.raises(RT029ContractError, match="both A_TO_B and B_TO_A"):
        _compile(realizations=bad)


def test_special_service_cannot_enter_automatic_candidate_stop_set() -> None:
    bad = _structures().copy()
    bad.loc[0, "vertex_ids"] = "S00;S01;S02;S03;SPECIAL"
    with pytest.raises(RT029ContractError, match="non-conventional"):
        _compile(structures=bad)


def test_input_order_invariance() -> None:
    a = _compile()
    b = _compile(
        structures=_structures().sample(frac=1, random_state=1),
        structure_link_manifest=_manifest().sample(frac=1, random_state=2),
        realizations=_realizations().sample(frac=1, random_state=3),
        walk_matrix=_walk().sample(frac=1, random_state=4),
    )
    pd.testing.assert_frame_equal(a.stop_sets, b.stop_sets)
    pd.testing.assert_frame_equal(a.accessibility_summary, b.accessibility_summary)
    pd.testing.assert_frame_equal(a.pareto_frontiers, b.pareto_frontiers)
    pd.testing.assert_frame_equal(a.pareto_shortlist, b.pareto_shortlist)
    assert a.audit["pareto_shortlist_sha256"] == b.audit["pareto_shortlist_sha256"]


def test_production_count_guard_fails_on_fixture_when_88_required() -> None:
    with pytest.raises(RT029ContractError, match="expected exactly 88"):
        compile_rt029(
            structures=_structures(),
            structure_link_manifest=_manifest(),
            realizations=_realizations(),
            walk_matrix=_walk(),
            expected_structure_count=88,
            expected_core_municipality_count=2,
        )
