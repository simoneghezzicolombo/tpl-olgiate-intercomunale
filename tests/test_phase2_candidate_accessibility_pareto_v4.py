from __future__ import annotations

import pandas as pd
import pytest

from phase2_candidate_accessibility_pareto_v4 import (
    DECISION_SCENARIO,
    RT029V4ContractError,
    compile_rt029_e456,
    pareto_front_fast,
    validate_structure_layers,
)

CONTRACT = "ABSTRACT_NETWORK_STRUCTURES_NOT_TERRITORIAL_RECOMMENDATIONS"


def _s(sid: str, e: int, links: list[str], vertices: list[str]) -> dict[str, object]:
    return {
        "structure_id": sid,
        "link_ids": ";".join(links),
        "vertex_ids": ";".join(vertices),
        "topology_class": "PATH",
        "vertex_count": len(vertices),
        "edge_count": e,
        "cycle_rank": e - len(vertices) + 1,
        "contract": CONTRACT,
    }


def _layers() -> dict[int, pd.DataFrame]:
    return {
        4: pd.DataFrame([
            _s("E4_A", 4, ["L01", "L12", "L23", "L34"], ["S00", "S01", "S02", "S03", "S04"]),
            _s("E4_B", 4, ["L02", "L12", "L23", "L34"], ["S00", "S01", "S02", "S03", "S04"]),
        ]),
        5: pd.DataFrame([
            _s("E5_A", 5, ["L02", "L12", "L23", "L34", "L45"], ["S00", "S01", "S02", "S03", "S04", "S05"]),
        ]),
        6: pd.DataFrame([
            _s("E6_A", 6, ["L02", "L12", "L23", "L34", "L45", "L56"], ["S00", "S01", "S02", "S03", "S04", "S05", "S06"]),
        ]),
    }


ENDPOINTS = {
    "L01": ("S00", "S01"), "L02": ("S00", "S02"), "L12": ("S01", "S02"),
    "L23": ("S02", "S03"), "L34": ("S03", "S04"), "L45": ("S04", "S05"),
    "L56": ("S05", "S06"),
}


def _rt023() -> pd.DataFrame:
    rows = []
    for link, (a, b) in ENDPOINTS.items():
        for direction, source, target in [("A_TO_B", a, b), ("B_TO_A", b, a)]:
            alternatives = [1, 2] if link == "L23" else [1]
            for alt in alternatives:
                rows.append({
                    "realization_id": f"R_{link}_{direction}_{alt}",
                    "structural_link_id": link,
                    "direction": direction,
                    "alternative_ordinal": alt,
                    "source_stop_place_id": source,
                    "target_stop_place_id": target,
                    "ordered_passenger_stop_place_ids": f"{source};{target}",
                    "distance_m": (3000.0 if link == "L01" else 800.0) + 50.0 * (alt - 1),
                    "running_minutes_model": 3.0 + 0.25 * (alt - 1),
                })
    return pd.DataFrame(rows)


def _patterns() -> pd.DataFrame:
    rows = []
    for row in _rt023().itertuples(index=False):
        if row.structural_link_id == "L23":
            if row.direction == "A_TO_B" and row.alternative_ordinal == 1:
                stops = "S02;S10;S03"
            elif row.direction == "A_TO_B":
                stops = "S02;S10;S11;S03"
            elif row.alternative_ordinal == 1:
                stops = "S03;S10;S02"
            else:
                stops = "S03;S12;S10;S02"
        else:
            stops = row.ordered_passenger_stop_place_ids
        rows.append({
            "realization_id": row.realization_id,
            "structural_link_id": row.structural_link_id,
            "direction": row.direction,
            "alternative_ordinal": row.alternative_ordinal,
            "ordered_passenger_stop_ids": stops,
            "passenger_stop_count": len(stops.split(";")),
        })
    return pd.DataFrame(rows)


def _walk(mojibake: bool = False) -> pd.DataFrame:
    populations = [
        ("P1", 10.0, "core", "97074", "Santa Maria HoÃ¨" if mojibake else "Santa Maria Hoè"),
        ("P2", 10.0, "core", "97012", "Calco"),
        ("P3", 5.0, "external", "99999", "External"),
    ]
    rows = []
    for i in range(35):
        stop = f"S{i:02d}"
        for pop, weight, scope, code, municipality in populations:
            if pop == "P1":
                time, status = 2.0 + i % 8, "REACHABLE"
            elif pop == "P2" and i in {5, 6, 10}:
                time, status = 4.0 + i % 3, "REACHABLE"
            elif pop == "P2":
                time, status = None, "UNREACHABLE"
            else:
                time, status = 8.0, "REACHABLE"
            rows.append({
                "population_unit_id": pop,
                "population_weight_2025": weight,
                "population_scope": scope,
                "population_municipality_code": code,
                "population_municipality_name": municipality,
                "stop_place_id": stop,
                "stop_service_class": "CONVENTIONAL_TPL",
                "walk_time_min": time,
                "reachability_status": status,
            })
    for pop, weight, scope, code, municipality in populations:
        rows.append({
            "population_unit_id": pop,
            "population_weight_2025": weight,
            "population_scope": scope,
            "population_municipality_code": code,
            "population_municipality_name": municipality,
            "stop_place_id": "SPECIAL",
            "stop_service_class": "SPECIAL_SERVICE",
            "walk_time_min": 1.0,
            "reachability_status": "REACHABLE",
        })
    return pd.DataFrame(rows)


def _compile(**overrides):
    args = {
        "structure_layers": _layers(),
        "rt023_realizations": _rt023(),
        "passenger_patterns": _patterns(),
        "walk_matrix": _walk(),
        "expected_layer_counts": {4: 2, 5: 1, 6: 1},
        "expected_population_units": 3,
        "lineage": {"fixture": "controlled_only"},
    }
    args.update(overrides)
    return compile_rt029_e456(**args)


def test_e4_e5_e6_layers_validate_without_topology_prior() -> None:
    structures = validate_structure_layers(_layers(), {4: 2, 5: 1, 6: 1})
    assert structures.groupby("edge_count").size().to_dict() == {4: 2, 5: 1, 6: 1}


def test_passenger_realization_recovers_guaranteed_intermediate_stop() -> None:
    result = _compile()
    row = result.structure_stop_sets.query("structure_id == 'E4_A' and scenario == @DECISION_SCENARIO").iloc[0]
    stops = set(row.ordered_stop_place_ids.split(";"))
    assert "S10" in stops and "S11" not in stops and "S12" not in stops


def test_possible_union_is_diagnostic_only() -> None:
    result = _compile()
    possible = result.structure_stop_sets.query("structure_id == 'E4_A' and scenario == 'POSSIBLE_PASSENGER_STOPS'").iloc[0]
    assert {"S11", "S12"}.issubset(set(possible.ordered_stop_place_ids.split(";")))
    assert possible.decision_eligible == False


def test_same_stop_set_is_evaluated_once() -> None:
    result = _compile()
    decision = result.structure_stop_sets.query("scenario == @DECISION_SCENARIO").set_index("structure_id")
    assert decision.loc["E4_A", "stop_set_id"] == decision.loc["E4_B", "stop_set_id"]
    assert result.audit["decision_passenger_stop_set_count"] < result.audit["structure_count"]


def test_exact_same_stop_set_dominance_removes_longer_structure() -> None:
    result = _compile()
    assert "E4_A" not in set(result.pareto_frontiers.structure_id)
    assert result.audit["post_exact_stop_set_dominance_reduction_count"] < result.audit["structure_count"]


def test_unreachable_population_stays_in_denominator() -> None:
    result = _compile()
    stop_set = result.structure_stop_sets.query("structure_id == 'E4_A' and scenario == @DECISION_SCENARIO").iloc[0].stop_set_id
    core = result.stop_set_accessibility.query("stop_set_id == @stop_set and scope == 'CORE'").iloc[0]
    assert core.reachable_population_share + core.unreachable_population_share == pytest.approx(1.0)


def test_missing_passenger_realization_fails_closed() -> None:
    with pytest.raises(RT029V4ContractError, match="does not exactly match RT-023"):
        _compile(passenger_patterns=_patterns().iloc[:-1].copy())


def test_special_service_cannot_enter_passenger_pattern() -> None:
    bad = _patterns().copy()
    mask = (bad.structural_link_id == "L45") & (bad.direction == "A_TO_B")
    bad.loc[mask, "ordered_passenger_stop_ids"] = "S04;SPECIAL;S05"
    bad.loc[mask, "passenger_stop_count"] = 3
    with pytest.raises(RT029V4ContractError, match="non-conventional"):
        _compile(passenger_patterns=bad)


def test_municipality_identity_uses_code_and_repairs_display_mojibake() -> None:
    result = _compile(walk_matrix=_walk(mojibake=True))
    assert "Santa Maria Hoè" in set(result.stop_set_municipality_accessibility.municipality)
    assert result.audit["display_label_normalization_count"] > 0
    assert result.audit["negative_assertions"]["uses_municipality_name_as_equity_identity"] is False


def test_fast_pareto_equals_bruteforce_on_controlled_frame() -> None:
    frame = pd.DataFrame([
        {"structure_id": "A", "x": 1.0, "y": 4.0},
        {"structure_id": "B", "x": 2.0, "y": 2.0},
        {"structure_id": "C", "x": 4.0, "y": 1.0},
        {"structure_id": "D", "x": 3.0, "y": 3.0},
    ])
    got = set(pareto_front_fast(frame, {"x": "min", "y": "min"}))
    brute = set()
    for _, row in frame.iterrows():
        dominated = False
        for _, other in frame.iterrows():
            if other.structure_id == row.structure_id:
                continue
            if other.x <= row.x and other.y <= row.y and (other.x < row.x or other.y < row.y):
                dominated = True
                break
        if not dominated:
            brute.add(row.structure_id)
    assert got == brute


def test_input_order_invariance_without_random_search() -> None:
    a = _compile()
    reversed_layers = {edge: frame.iloc[::-1].reset_index(drop=True) for edge, frame in _layers().items()}
    b = _compile(
        structure_layers=reversed_layers,
        rt023_realizations=_rt023().iloc[::-1].reset_index(drop=True),
        passenger_patterns=_patterns().iloc[::-1].reset_index(drop=True),
        walk_matrix=_walk().iloc[::-1].reset_index(drop=True),
    )
    pd.testing.assert_frame_equal(a.pareto_frontiers, b.pareto_frontiers)
    assert a.audit["pareto_frontiers_sha256"] == b.audit["pareto_frontiers_sha256"]


def test_no_final_complexity_or_winner_claims() -> None:
    result = _compile()
    negatives = result.audit["negative_assertions"]
    assert negatives["claims_complete_e7_search"] is False
    assert negatives["claims_e6_is_final_complexity_cap"] is False
    assert negatives["selects_primary_or_runner_up"] is False
    assert negatives["uses_weighted_composite_score"] is False
