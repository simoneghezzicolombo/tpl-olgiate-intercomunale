from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from phase2_service_pattern_realization_bridge_v3 import (
    RT023ContractError,
    build_rt014_service_pattern_from_fragment,
    compile_rt023_bridge,
)


EPOCH = "TEST_EPOCH"


def _frames():
    links = pd.DataFrame(
        [
            {
                "structural_link_id": "LINK_1",
                "terminal_a": "STOP_A",
                "terminal_b": "STOP_B",
                "eligibility_status": "RECIPROCAL_BIDIRECTIONAL_CORRIDOR_AVAILABLE",
                "eligible_for_bidirectional_undirected_structure": True,
                "a_to_b_pair_id": "PAIR_AB",
                "a_to_b_admitted_corridor_count": 2,
                "b_to_a_pair_id": "PAIR_BA",
                "b_to_a_admitted_corridor_count": 1,
            }
        ]
    )
    structures = pd.DataFrame(
        [
            {
                "structure_id": "STRUCT_1",
                "link_ids": "LINK_1",
                "contract": "ABSTRACT_NETWORK_STRUCTURES_NOT_TERRITORIAL_RECOMMENDATIONS",
            }
        ]
    )
    corridors = pd.DataFrame(
        [
            {
                "corridor_id": "CORR_AB_1",
                "pair_id": "PAIR_AB",
                "source_stop_place_id": "STOP_A",
                "target_stop_place_id": "STOP_B",
                "path_node_ids": "N_A;TECH_1;N_B",
                "path_geometry_sha256": "G_AB_1",
                "running_minutes_model": 4.0,
                "distance_m": 1000.0,
                "edge_count": 2,
                "graph_epoch_id": EPOCH,
                "admissible_for_corridor_pool": True,
                "elementary_for_structural_reduction": True,
            },
            {
                "corridor_id": "CORR_AB_2",
                "pair_id": "PAIR_AB",
                "source_stop_place_id": "STOP_A",
                "target_stop_place_id": "STOP_B",
                "path_node_ids": "N_A;TECH_2;N_B",
                "path_geometry_sha256": "G_AB_2",
                "running_minutes_model": 4.5,
                "distance_m": 1100.0,
                "edge_count": 2,
                "graph_epoch_id": EPOCH,
                "admissible_for_corridor_pool": True,
                "elementary_for_structural_reduction": True,
            },
            {
                "corridor_id": "CORR_BA_1",
                "pair_id": "PAIR_BA",
                "source_stop_place_id": "STOP_B",
                "target_stop_place_id": "STOP_A",
                "path_node_ids": "N_B;TECH_RETURN;N_A",
                "path_geometry_sha256": "G_BA_1",
                "running_minutes_model": 5.0,
                "distance_m": 1200.0,
                "edge_count": 2,
                "graph_epoch_id": EPOCH,
                "admissible_for_corridor_pool": True,
                "elementary_for_structural_reduction": True,
            },
            {
                "corridor_id": "CORR_AB_NON_ELEM",
                "pair_id": "PAIR_AB",
                "source_stop_place_id": "STOP_A",
                "target_stop_place_id": "STOP_B",
                "path_node_ids": "N_A;N_X;N_B",
                "path_geometry_sha256": "G_BAD",
                "running_minutes_model": 3.0,
                "distance_m": 900.0,
                "edge_count": 2,
                "graph_epoch_id": EPOCH,
                "admissible_for_corridor_pool": False,
                "elementary_for_structural_reduction": False,
            },
        ]
    )
    occurrence_rows = []
    for cid, source, target, endpos in [
        ("CORR_AB_1", "STOP_A", "STOP_B", 2),
        ("CORR_AB_2", "STOP_A", "STOP_B", 2),
        ("CORR_BA_1", "STOP_B", "STOP_A", 2),
        ("CORR_AB_NON_ELEM", "STOP_A", "STOP_B", 2),
    ]:
        occurrence_rows += [
            {
                "corridor_id": cid,
                "stop_sequence": 1,
                "path_node_position": 0,
                "stop_place_id": source,
                "stop_occurrence_index": 1,
                "service_class": "CONVENTIONAL_TPL",
                "graph_node_id": f"N_{source}",
                "graph_epoch_id": EPOCH,
                "materialization_semantics": "EXISTING_FROZEN_STOP_PLACE_ON_EXACT_ORDERED_CORRIDOR_PATH_NODE",
            },
            {
                "corridor_id": cid,
                "stop_sequence": 2,
                "path_node_position": endpos,
                "stop_place_id": target,
                "stop_occurrence_index": 1,
                "service_class": "CONVENTIONAL_TPL",
                "graph_node_id": f"N_{target}",
                "graph_epoch_id": EPOCH,
                "materialization_semantics": "EXISTING_FROZEN_STOP_PLACE_ON_EXACT_ORDERED_CORRIDOR_PATH_NODE",
            },
        ]
    return links, structures, corridors, pd.DataFrame(occurrence_rows)


def _compile(frames=None):
    links, structures, corridors, occurrences = frames or _frames()
    return compile_rt023_bridge(
        reciprocal_links=links,
        structures=structures,
        elementary_corridors=corridors,
        corridor_stop_occurrences=occurrences,
        expected_graph_epoch_id=EPOCH,
        lineage={"test": "fixture"},
    )


def test_preserves_all_elementary_alternatives_and_independent_directions():
    result = _compile()
    catalog = result.realization_catalog
    assert len(catalog) == 3
    ab = catalog[catalog.direction == "A_TO_B"]
    ba = catalog[catalog.direction == "B_TO_A"]
    assert set(ab.corridor_id) == {"CORR_AB_1", "CORR_AB_2"}
    assert set(ba.corridor_id) == {"CORR_BA_1"}
    assert ba.iloc[0].path_node_ids == "N_B;TECH_RETURN;N_A"
    assert ba.iloc[0].path_node_ids != ";".join(reversed(ab.iloc[0].path_node_ids.split(";")))


def test_technical_waypoints_are_not_promoted_to_passenger_stops():
    result = _compile()
    row = result.realization_catalog[result.realization_catalog.corridor_id == "CORR_AB_1"].iloc[0]
    assert row.ordered_passenger_stop_place_ids == "STOP_A;STOP_B"
    assert "TECH_1" in row.path_node_ids
    assert "TECH_1" not in row.ordered_passenger_stop_place_ids


def test_structure_manifest_is_lazy_not_cartesian():
    result = _compile()
    assert len(result.structure_link_manifest) == 1
    assert result.structure_link_manifest.iloc[0].composition_semantics == (
        "LAZY_LINK_REFERENCE_NO_REALIZATION_CARTESIAN_PRODUCT"
    )
    assert len(result.realization_catalog) == 3


def test_deterministic_under_input_row_permutation():
    frames = _frames()
    baseline = _compile(frames)
    shuffled = tuple(
        frame.sample(frac=1.0, random_state=i + 100).reset_index(drop=True)
        for i, frame in enumerate(frames)
    )
    repeated = _compile(shuffled)
    assert baseline.audit["realization_catalog_sha256"] == repeated.audit["realization_catalog_sha256"]
    assert baseline.audit["structure_link_manifest_sha256"] == repeated.audit["structure_link_manifest_sha256"]
    assert baseline.audit["rt014_pattern_fragments_sha256"] == repeated.audit["rt014_pattern_fragments_sha256"]
    pd.testing.assert_frame_equal(baseline.realization_catalog, repeated.realization_catalog)


def test_unknown_structure_link_fails_closed():
    frames = list(_frames())
    frames[1] = frames[1].copy()
    frames[1].loc[0, "link_ids"] = "LINK_UNKNOWN"
    with pytest.raises(RT023ContractError, match="unknown links"):
        _compile(tuple(frames))


def test_directional_count_mismatch_fails_closed():
    frames = list(_frames())
    frames[0] = frames[0].copy()
    frames[0].loc[0, "a_to_b_admitted_corridor_count"] = 3
    with pytest.raises(RT023ContractError, match="count mismatch"):
        _compile(tuple(frames))


def test_nonconventional_automatic_occurrence_fails_closed():
    frames = list(_frames())
    frames[3] = frames[3].copy()
    mask = frames[3].corridor_id == "CORR_AB_1"
    frames[3].loc[mask, "service_class"] = "SPECIAL_SERVICE"
    with pytest.raises(RT023ContractError, match="non-conventional"):
        _compile(tuple(frames))


def test_rt014_adapter_requires_explicit_service_inputs_and_preserves_stop_order():
    result = _compile()
    fragment = result.rt014_pattern_fragments.iloc[0].to_dict()
    pattern = build_rt014_service_pattern_from_fragment(
        fragment,
        pattern_id="P_EXPLICIT",
        route_id="R_EXPLICIT",
        service_id="S_EXPLICIT",
        direction_id=0,
        cumulative_times_sec=(0, 240),
        departures_sec=(8 * 3600,),
    )
    assert pattern.pattern_id == "P_EXPLICIT"
    assert pattern.route_id == "R_EXPLICIT"
    assert pattern.service_id == "S_EXPLICIT"
    assert [c.stop_id for c in pattern.stop_calls] == fragment["ordered_passenger_stop_place_ids"].split(";")
    assert [c.cumulative_time_sec for c in pattern.stop_calls] == [0, 240]
    assert pattern.departures_sec == (8 * 3600,)
