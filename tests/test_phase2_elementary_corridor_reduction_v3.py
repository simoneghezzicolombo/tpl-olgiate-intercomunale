from __future__ import annotations

import pandas as pd
import pytest

from src.phase2_complete_directed_pairs_v3 import (
    build_complete_directed_pair_manifest,
    directed_pair_id,
)
from src.phase2_elementary_corridor_reduction_v3 import (
    build_directional_elementary_availability,
    build_pair_query_anchor_table,
    build_reciprocal_elementary_structural_links,
    classify_elementary_corridors,
    filter_elementary_corridors_for_reciprocity,
)


def attachment_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "stop_place_id": f"STOP::{i:02d}",
                "stop_name": f"Stop {i:02d}",
                "municipality": "M1" if i < 10 else "M2",
                "service_class": "SPECIAL_SERVICE" if i == 25 else "CONVENTIONAL_TPL",
                "graph_node_id": f"N::{i:02d}",
                "route_ready": True,
                "attachment_status": "ROUTE_READY_LE_75M",
                "graph_epoch_id": "fixture-epoch",
            }
            for i in range(1, 37)
        ]
    )


def corridor(cid: str, source: str, target: str, nodes: list[str], *, admitted: bool = True) -> dict:
    return {
        "corridor_id": cid,
        "pair_id": directed_pair_id(source, target),
        "source_routing_terminal_id": source,
        "target_routing_terminal_id": target,
        "path_node_ids": ";".join(nodes),
        "admissible_for_corridor_pool": admitted,
        "running_minutes_model": 5.0,
        "distance_m": 1000.0,
    }


def occurrence(cid: str, seq: int, pos: int, stop_id: str, service_class: str = "CONVENTIONAL_TPL") -> dict:
    return {
        "corridor_id": cid,
        "stop_sequence": seq,
        "path_node_position": pos,
        "stop_place_id": stop_id,
        "service_class": service_class,
    }


def pair_row(source: str, target: str) -> dict:
    return {
        "pair_id": directed_pair_id(source, target),
        "source_routing_terminal_id": source,
        "target_routing_terminal_id": target,
        "gate_d_route_found": True,
    }


def test_anchor_manifest_is_35_conventional_order_invariant_and_not_service_termini() -> None:
    source = attachment_fixture()
    a = build_pair_query_anchor_table(source)
    b = build_pair_query_anchor_table(source.iloc[::-1].reset_index(drop=True))
    pd.testing.assert_frame_equal(a, b)
    assert len(a) == 35
    assert "STOP::25" not in set(a["stop_place_id"])
    assert a["routing_terminal_id"].tolist() == a["stop_place_id"].tolist()
    assert a["service_terminal_status_claimed"].eq(False).all()
    assert a["terminal_evidence_status"].eq("TECHNICAL_QUERY_ANCHOR_NOT_SERVICE_TERMINUS").all()


def test_anchor_manifest_fails_closed_if_conventional_stop_is_not_route_ready() -> None:
    source = attachment_fixture()
    source.loc[source["stop_place_id"] == "STOP::03", "route_ready"] = False
    with pytest.raises(ValueError, match="must all be route-ready"):
        build_pair_query_anchor_table(source)


def test_rt010_complete_manifest_is_1190_for_35_technical_query_anchors() -> None:
    anchors = build_pair_query_anchor_table(attachment_fixture())
    result = build_complete_directed_pair_manifest(anchors)
    assert result["complete"] is True
    assert result["terminal_count"] == 35
    assert result["directed_pair_count"] == 1190
    assert result["unordered_pair_count"] == 595


def test_simple_corridor_is_elementary_and_third_stop_makes_it_decomposable() -> None:
    corridors = pd.DataFrame([
        corridor("C_AB", "A", "B", ["NA", "NX", "NB"]),
        corridor("C_AC", "A", "C", ["NA", "NB", "NC"]),
    ])
    occurrences = pd.DataFrame([
        occurrence("C_AB", 1, 0, "A"),
        occurrence("C_AB", 2, 2, "B"),
        occurrence("C_AC", 1, 0, "A"),
        occurrence("C_AC", 2, 1, "B"),
        occurrence("C_AC", 3, 2, "C"),
    ])
    result = classify_elementary_corridors(corridors, occurrences).set_index("corridor_id")
    assert bool(result.loc["C_AB", "elementary_for_structural_reduction"])
    assert not bool(result.loc["C_AC", "elementary_for_structural_reduction"])
    assert result.loc["C_AC", "via_stop_place_occurrences"] == "B"


def test_endpoint_revisits_do_not_create_false_third_stops() -> None:
    corridors = pd.DataFrame([corridor("C_LOOP", "A", "B", ["NA", "NX", "NY", "NB"])])
    occurrences = pd.DataFrame([
        occurrence("C_LOOP", 1, 0, "A"),
        occurrence("C_LOOP", 2, 1, "A"),
        occurrence("C_LOOP", 3, 2, "B"),
        occurrence("C_LOOP", 4, 3, "B"),
    ])
    row = classify_elementary_corridors(corridors, occurrences).iloc[0]
    assert bool(row["elementary_for_structural_reduction"])
    assert row["strict_intermediate_occurrence_count"] == 0


def test_repeated_third_stop_occurrences_remain_explicit() -> None:
    corridors = pd.DataFrame([corridor("C_REPEAT", "A", "C", ["NA", "NB1", "NB2", "NC"])])
    occurrences = pd.DataFrame([
        occurrence("C_REPEAT", 1, 0, "A"),
        occurrence("C_REPEAT", 2, 1, "B"),
        occurrence("C_REPEAT", 3, 2, "B"),
        occurrence("C_REPEAT", 4, 3, "C"),
    ])
    row = classify_elementary_corridors(corridors, occurrences).iloc[0]
    assert not bool(row["elementary_for_structural_reduction"])
    assert row["strict_intermediate_occurrence_count"] == 2
    assert row["strict_intermediate_unique_stop_count"] == 1
    assert row["via_stop_place_occurrences"] == "B|B"
    assert row["via_stop_place_ids_ordered_unique"] == "B"


def test_special_service_occurrence_does_not_decompose_default_conventional_corridor() -> None:
    corridors = pd.DataFrame([corridor("C_SPECIAL", "A", "B", ["NA", "NS", "NB"])])
    occurrences = pd.DataFrame([
        occurrence("C_SPECIAL", 1, 0, "A"),
        occurrence("C_SPECIAL", 2, 1, "SPECIAL", "SPECIAL_SERVICE"),
        occurrence("C_SPECIAL", 3, 2, "B"),
    ])
    row = classify_elementary_corridors(corridors, occurrences).iloc[0]
    assert bool(row["elementary_for_structural_reduction"])


def test_missing_endpoint_occurrence_blocks_elementarity() -> None:
    corridors = pd.DataFrame([corridor("C_MISSING", "A", "B", ["NA", "NB"])])
    occurrences = pd.DataFrame([occurrence("C_MISSING", 1, 0, "A")])
    row = classify_elementary_corridors(corridors, occurrences).iloc[0]
    assert not bool(row["elementary_for_structural_reduction"])
    assert row["elementary_status"] == "BLOCKED_ENDPOINT_OCCURRENCE_MISSING"


def test_pair_direction_remains_available_if_any_admitted_alternative_is_elementary() -> None:
    corridors = pd.DataFrame([
        corridor("C_AB_VIA_X", "A", "B", ["NA", "NX", "NB"]),
        corridor("C_AB_DIRECT", "A", "B", ["NA", "NQ", "NB"]),
    ])
    occurrences = pd.DataFrame([
        occurrence("C_AB_VIA_X", 1, 0, "A"),
        occurrence("C_AB_VIA_X", 2, 1, "X"),
        occurrence("C_AB_VIA_X", 3, 2, "B"),
        occurrence("C_AB_DIRECT", 1, 0, "A"),
        occurrence("C_AB_DIRECT", 2, 2, "B"),
    ])
    classified = classify_elementary_corridors(corridors, occurrences)
    row = build_directional_elementary_availability(classified).iloc[0]
    assert row["admitted_corridor_count"] == 2
    assert row["elementary_admitted_corridor_count"] == 1
    assert bool(row["has_elementary_admitted_corridor"])
    assert row["elementary_corridor_ids"] == "C_AB_DIRECT"


def test_rt009_reciprocity_requires_elementary_availability_in_both_directions() -> None:
    pairs = pd.DataFrame([pair_row("A", "C"), pair_row("C", "A")])
    corridors = pd.DataFrame([
        corridor("C_AC", "A", "C", ["NA", "NC"]),
        corridor("C_CA", "C", "A", ["NC", "NB", "NA"]),
    ])
    occurrences = pd.DataFrame([
        occurrence("C_AC", 1, 0, "A"),
        occurrence("C_AC", 2, 1, "C"),
        occurrence("C_CA", 1, 0, "C"),
        occurrence("C_CA", 2, 1, "B"),
        occurrence("C_CA", 3, 2, "A"),
    ])
    result = build_reciprocal_elementary_structural_links(pairs, corridors, occurrences)
    assert result["structural_links"].empty
    assert result["pair_audit"].iloc[0]["eligibility_status"] == "NO_ADMITTED_CORRIDOR_IN_DIRECTION"
    assert result["metadata"]["service_terminal_status_claimed"] is False


def test_reciprocal_elementary_paths_create_one_structural_link() -> None:
    pairs = pd.DataFrame([pair_row("A", "B"), pair_row("B", "A")])
    corridors = pd.DataFrame([
        corridor("C_AB", "A", "B", ["NA", "NB"]),
        corridor("C_BA", "B", "A", ["NB", "NA"]),
    ])
    occurrences = pd.DataFrame([
        occurrence("C_AB", 1, 0, "A"),
        occurrence("C_AB", 2, 1, "B"),
        occurrence("C_BA", 1, 0, "B"),
        occurrence("C_BA", 2, 1, "A"),
    ])
    result = build_reciprocal_elementary_structural_links(pairs, corridors, occurrences)
    assert len(result["structural_links"]) == 1


def test_filter_retains_all_evidence_but_only_exposes_elementary_paths_to_rt009() -> None:
    corridors = pd.DataFrame([
        corridor("C1", "A", "B", ["NA", "NB"]),
        corridor("C2", "A", "B", ["NA", "NX", "NB"]),
    ])
    occurrences = pd.DataFrame([
        occurrence("C1", 1, 0, "A"),
        occurrence("C1", 2, 1, "B"),
        occurrence("C2", 1, 0, "A"),
        occurrence("C2", 2, 1, "X"),
        occurrence("C2", 3, 2, "B"),
    ])
    classified = classify_elementary_corridors(corridors, occurrences)
    filtered = filter_elementary_corridors_for_reciprocity(corridors, classified)
    assert len(filtered) == 2
    assert dict(zip(filtered["corridor_id"], filtered["admissible_for_corridor_pool"])) == {"C1": True, "C2": False}
    assert dict(zip(filtered["corridor_id"], filtered["original_admissible_for_corridor_pool"])) == {"C1": True, "C2": True}


def test_classification_is_input_order_invariant() -> None:
    corridors = pd.DataFrame([
        corridor("C2", "A", "C", ["NA", "NB", "NC"]),
        corridor("C1", "A", "B", ["NA", "NB"]),
    ])
    occurrences = pd.DataFrame([
        occurrence("C2", 3, 2, "C"),
        occurrence("C2", 2, 1, "B"),
        occurrence("C1", 2, 1, "B"),
        occurrence("C2", 1, 0, "A"),
        occurrence("C1", 1, 0, "A"),
    ])
    a = classify_elementary_corridors(corridors, occurrences)
    b = classify_elementary_corridors(corridors.iloc[::-1].reset_index(drop=True), occurrences.iloc[::-1].reset_index(drop=True))
    pd.testing.assert_frame_equal(a, b)


def test_not_admitted_corridor_never_becomes_elementary_structural_candidate() -> None:
    corridors = pd.DataFrame([corridor("C_NO", "A", "B", ["NA", "NB"], admitted=False)])
    occurrences = pd.DataFrame([
        occurrence("C_NO", 1, 0, "A"),
        occurrence("C_NO", 2, 1, "B"),
    ])
    row = classify_elementary_corridors(corridors, occurrences).iloc[0]
    assert not bool(row["elementary_for_structural_reduction"])
    assert row["elementary_status"] == "NOT_ADMITTED_NOT_STRUCTURAL_CANDIDATE"
