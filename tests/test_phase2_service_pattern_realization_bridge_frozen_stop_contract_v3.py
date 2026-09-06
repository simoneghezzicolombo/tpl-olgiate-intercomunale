from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from phase2_service_pattern_realization_bridge_certified_v3 import (
    RT023ContractError,
    SPECIAL_STOP_ID,
    compile_certified_rt023_bridge,
)

EPOCH = "TEST_EPOCH"


def _fixture():
    links = pd.DataFrame([{
        "structural_link_id": "LINK_1",
        "terminal_a": "STOP_A",
        "terminal_b": "STOP_B",
        "eligibility_status": "RECIPROCAL_BIDIRECTIONAL_CORRIDOR_AVAILABLE",
        "eligible_for_bidirectional_undirected_structure": True,
        "a_to_b_pair_id": "PAIR_AB",
        "a_to_b_admitted_corridor_count": 1,
        "b_to_a_pair_id": "PAIR_BA",
        "b_to_a_admitted_corridor_count": 1,
    }])
    structures = pd.DataFrame([{
        "structure_id": "STRUCT_1",
        "link_ids": "LINK_1",
        "contract": "ABSTRACT_NETWORK_STRUCTURES_NOT_TERRITORIAL_RECOMMENDATIONS",
    }])
    stops = [
        {
            "stop_place_id": "STOP_A", "service_class": "CONVENTIONAL_TPL",
            "graph_node_id": "N_A", "graph_epoch_id": EPOCH,
            "automatic_materialization_eligible": True,
            "automatic_exclusion_reason": "ELIGIBLE",
        },
        {
            "stop_place_id": "STOP_B", "service_class": "CONVENTIONAL_TPL",
            "graph_node_id": "N_B", "graph_epoch_id": EPOCH,
            "automatic_materialization_eligible": True,
            "automatic_exclusion_reason": "ELIGIBLE",
        },
    ]
    for i in range(33):
        stops.append({
            "stop_place_id": f"DUMMY_{i:02d}", "service_class": "CONVENTIONAL_TPL",
            "graph_node_id": f"N_DUMMY_{i:02d}", "graph_epoch_id": EPOCH,
            "automatic_materialization_eligible": True,
            "automatic_exclusion_reason": "ELIGIBLE",
        })
    stops.append({
        "stop_place_id": SPECIAL_STOP_ID, "service_class": "SPECIAL_SERVICE",
        "graph_node_id": "N_SPECIAL", "graph_epoch_id": EPOCH,
        "automatic_materialization_eligible": False,
        "automatic_exclusion_reason": "SERVICE_CLASS_SPECIAL_SERVICE_NOT_AUTOMATIC",
    })
    stop_attachments = pd.DataFrame(stops)

    corridors = pd.DataFrame([
        {
            "corridor_id": "CORR_AB", "pair_id": "PAIR_AB",
            "source_stop_place_id": "STOP_A", "target_stop_place_id": "STOP_B",
            "path_node_ids": "N_A;TECH_AB;N_B", "path_geometry_sha256": "G_AB",
            "running_minutes_model": 4.0, "distance_m": 1000.0, "edge_count": 2,
            "graph_epoch_id": EPOCH, "admissible_for_corridor_pool": True,
            "elementary_for_structural_reduction": True,
        },
        {
            "corridor_id": "CORR_BA", "pair_id": "PAIR_BA",
            "source_stop_place_id": "STOP_B", "target_stop_place_id": "STOP_A",
            "path_node_ids": "N_B;TECH_BA;N_A", "path_geometry_sha256": "G_BA",
            "running_minutes_model": 4.2, "distance_m": 1020.0, "edge_count": 2,
            "graph_epoch_id": EPOCH, "admissible_for_corridor_pool": True,
            "elementary_for_structural_reduction": True,
        },
    ])
    occurrences = pd.DataFrame([
        {
            "corridor_id": "CORR_AB", "stop_sequence": 1, "path_node_position": 0,
            "stop_place_id": "STOP_A", "stop_occurrence_index": 1,
            "service_class": "CONVENTIONAL_TPL", "graph_node_id": "N_A",
            "graph_epoch_id": EPOCH,
            "materialization_semantics": "EXISTING_FROZEN_STOP_PLACE_ON_EXACT_ORDERED_CORRIDOR_PATH_NODE",
        },
        {
            "corridor_id": "CORR_AB", "stop_sequence": 2, "path_node_position": 2,
            "stop_place_id": "STOP_B", "stop_occurrence_index": 1,
            "service_class": "CONVENTIONAL_TPL", "graph_node_id": "N_B",
            "graph_epoch_id": EPOCH,
            "materialization_semantics": "EXISTING_FROZEN_STOP_PLACE_ON_EXACT_ORDERED_CORRIDOR_PATH_NODE",
        },
        {
            "corridor_id": "CORR_BA", "stop_sequence": 1, "path_node_position": 0,
            "stop_place_id": "STOP_B", "stop_occurrence_index": 1,
            "service_class": "CONVENTIONAL_TPL", "graph_node_id": "N_B",
            "graph_epoch_id": EPOCH,
            "materialization_semantics": "EXISTING_FROZEN_STOP_PLACE_ON_EXACT_ORDERED_CORRIDOR_PATH_NODE",
        },
        {
            "corridor_id": "CORR_BA", "stop_sequence": 2, "path_node_position": 2,
            "stop_place_id": "STOP_A", "stop_occurrence_index": 1,
            "service_class": "CONVENTIONAL_TPL", "graph_node_id": "N_A",
            "graph_epoch_id": EPOCH,
            "materialization_semantics": "EXISTING_FROZEN_STOP_PLACE_ON_EXACT_ORDERED_CORRIDOR_PATH_NODE",
        },
    ])
    return links, structures, stop_attachments, corridors, occurrences


def _compile(frames=None):
    links, structures, stops, corridors, occurrences = frames or _fixture()
    return compile_certified_rt023_bridge(
        reciprocal_links=links,
        structures=structures,
        stop_attachments=stops,
        elementary_corridors=corridors,
        corridor_stop_occurrences=occurrences,
        expected_graph_epoch_id=EPOCH,
        lineage={
            "elementary_corridors_for_reciprocity_sha256": "EVIDENCE_SHA",
            "stop_attachments_sha256": "STOP_SHA",
            "corridor_stop_occurrences_sha256": "OCC_SHA",
        },
    )


def test_certified_wrapper_preserves_36_stop_contract_and_provenance():
    result = _compile()
    assert result.audit["frozen_stop_count"] == 36
    assert result.audit["frozen_conventional_stop_count"] == 35
    assert result.audit["frozen_special_service_stop_count"] == 1
    assert result.audit["frozen_special_service_stop_id"] == SPECIAL_STOP_ID
    assert set(result.realization_catalog["rt018_stop_attachment_layer_sha256"]) == {"STOP_SHA"}
    assert set(result.realization_catalog["rt018_stop_occurrence_corpus_sha256"]) == {"OCC_SHA"}
    assert set(result.realization_catalog["rt021_elementary_corridor_evidence_sha256"]) == {"EVIDENCE_SHA"}


def test_graph_epoch_mismatch_fails_closed():
    frames = list(_fixture())
    frames[2] = frames[2].copy()
    frames[2]["graph_epoch_id"] = "WRONG_EPOCH"
    with pytest.raises(RT023ContractError, match="graph epoch mismatch"):
        _compile(tuple(frames))


def test_old_43_stop_universe_fails_closed():
    frames = list(_fixture())
    extras = []
    for i in range(7):
        extras.append({
            "stop_place_id": f"OLD43_{i}", "service_class": "CONVENTIONAL_TPL",
            "graph_node_id": f"N_OLD43_{i}", "graph_epoch_id": EPOCH,
            "automatic_materialization_eligible": True,
            "automatic_exclusion_reason": "ELIGIBLE",
        })
    frames[2] = pd.concat([frames[2], pd.DataFrame(extras)], ignore_index=True)
    with pytest.raises(RT023ContractError, match="exactly 36"):
        _compile(tuple(frames))


def test_special_service_cannot_be_auto_materialized():
    frames = list(_fixture())
    frames[2] = frames[2].copy()
    frames[2].loc[frames[2].stop_place_id == SPECIAL_STOP_ID, "automatic_materialization_eligible"] = True
    with pytest.raises(RT023ContractError, match="SPECIAL_SERVICE must not"):
        _compile(tuple(frames))


def test_occurrence_outside_frozen_conventional_layer_fails_closed():
    frames = list(_fixture())
    frames[4] = frames[4].copy()
    frames[4].loc[0, "stop_place_id"] = "UNKNOWN_STOP"
    with pytest.raises(RT023ContractError, match="outside frozen 35"):
        _compile(tuple(frames))


def test_unknown_pair_fails_closed():
    frames = list(_fixture())
    frames[0] = frames[0].copy()
    frames[0].loc[0, "a_to_b_pair_id"] = "PAIR_UNKNOWN"
    with pytest.raises(RT023ContractError, match="count mismatch"):
        _compile(tuple(frames))


def test_missing_corridor_occurrence_fails_closed():
    frames = list(_fixture())
    frames[4] = frames[4][frames[4].corridor_id != "CORR_AB"].reset_index(drop=True)
    with pytest.raises(RT023ContractError, match="has no passenger stop occurrences"):
        _compile(tuple(frames))


def test_occurrence_graph_node_drift_fails_closed():
    frames = list(_fixture())
    frames[4] = frames[4].copy()
    frames[4].loc[0, "graph_node_id"] = "WRONG_NODE"
    with pytest.raises(RT023ContractError, match="graph node drift"):
        _compile(tuple(frames))
