import pandas as pd
import pytest

from src.phase2_complete_directed_pairs_v3 import build_complete_directed_pair_manifest
from src.phase2_corridor_reciprocity_v3 import build_reciprocal_structural_links
from src.phase2_elementary_corridor_reduction_v3 import (
    build_pair_query_anchor_table,
    classify_elementary_corridors,
    filter_elementary_corridors_for_reciprocity,
)
from src.phase2_final_stop_materialization_v3 import materialize_stop_occurrences
from src.phase2_territorial_structural_search_v3 import (
    BLOCKED_FRONTIER,
    FIXTURE_PASS_STATUS,
    PREPARED_STATUS,
    canonical_frame_sha256,
    prepared_status_record,
    run_rt022_orchestrator,
    validate_rt021_bundle,
)


def _attachments() -> pd.DataFrame:
    municipality_counts = {
        "Brivio": 10,
        "Calco": 9,
        "La Valletta Brianza": 4,
        "Olgiate Molgora": 5,
        "Santa Maria Hoè": 7,
    }
    rows = []
    counter = 0
    for municipality, count in municipality_counts.items():
        for _ in range(count):
            counter += 1
            rows.append(
                {
                    "stop_place_id": f"S{counter:02d}",
                    "stop_name": f"Controlled stop {counter:02d}",
                    "municipality": municipality,
                    "service_class": "CONVENTIONAL_TPL",
                    "lat": 45.7000 + counter * 0.0001,
                    "lon": 9.3000 + counter * 0.0001,
                    "graph_node_id": f"N{counter:02d}",
                    "route_ready": True,
                    "attachment_status": "ROUTE_READY_LE_75M",
                    "graph_epoch_id": "EPOCH_TEST",
                }
            )
    rows.append(
        {
            "stop_place_id": "SPECIAL01",
            "stop_name": "Controlled special stop",
            "municipality": "Olgiate Molgora",
            "service_class": "SPECIAL_SERVICE",
            "lat": 45.7500,
            "lon": 9.4000,
            "graph_node_id": "NSPECIAL",
            "route_ready": True,
            "attachment_status": "ROUTE_READY_LE_75M",
            "graph_epoch_id": "EPOCH_TEST",
        }
    )
    return pd.DataFrame(rows)


def _policy_representatives(attachments: pd.DataFrame) -> list[str]:
    conventional = attachments[attachments["service_class"] == "CONVENTIONAL_TPL"]
    out = []
    for municipality in [
        "Brivio",
        "Calco",
        "La Valletta Brianza",
        "Olgiate Molgora",
        "Santa Maria Hoè",
    ]:
        out.append(
            conventional.loc[
                conventional["municipality"] == municipality, "stop_place_id"
            ].iloc[0]
        )
    return out


def _bundle():
    attachments = _attachments()
    anchors = build_pair_query_anchor_table(attachments)
    manifest = build_complete_directed_pair_manifest(anchors)["manifest"]
    pair_results = manifest[
        [
            "pair_id",
            "source_routing_terminal_id",
            "target_routing_terminal_id",
        ]
    ].copy()
    pair_results["gate_d_route_found"] = False

    node_by_stop = dict(
        zip(attachments["stop_place_id"], attachments["graph_node_id"])
    )
    representatives = _policy_representatives(attachments)
    reciprocal_edges = list(zip(representatives[:-1], representatives[1:]))
    corridor_rows = []
    pair_lookup = manifest.set_index(
        ["source_routing_terminal_id", "target_routing_terminal_id"]
    )
    index_by_pair_id = pair_results.set_index("pair_id").index

    for u, v in reciprocal_edges:
        for source, target in ((u, v), (v, u)):
            pair = pair_lookup.loc[(source, target)]
            pair_id = str(pair["pair_id"])
            pair_results.loc[
                pair_results["pair_id"] == pair_id, "gate_d_route_found"
            ] = True
            corridor_rows.append(
                {
                    "corridor_id": f"C_{source}_{target}",
                    "pair_id": pair_id,
                    "source_routing_terminal_id": source,
                    "target_routing_terminal_id": target,
                    "path_node_ids": f"{node_by_stop[source]};{node_by_stop[target]}",
                    "admissible_for_corridor_pool": True,
                    "graph_epoch_id": "EPOCH_TEST",
                }
            )

    assert len(index_by_pair_id) == 1190
    corridors = pd.DataFrame(corridor_rows)
    metadata = {
        "status": "PASS_CONTROLLED_TEST_FIXTURE",
        "graph_epoch_id": "EPOCH_TEST",
        "evidence_kind": "CONTROLLED_TEST_FIXTURE",
    }
    return attachments, manifest, pair_results, corridors, metadata


def test_exact_35_anchor_1190_pair_contract_and_special_exclusion():
    attachments, manifest, pair_results, corridors, metadata = _bundle()
    validated = validate_rt021_bundle(
        attachments, manifest, pair_results, corridors, metadata
    )
    anchors = validated["anchors"]
    assert len(attachments) == 36
    assert len(anchors) == 35
    assert len(validated["pair_manifest"]) == 1190
    assert "SPECIAL01" not in set(anchors["stop_place_id"])
    assert not anchors["service_terminal_status_claimed"].any()


def test_missing_pair_result_fails_closed():
    attachments, manifest, pair_results, corridors, metadata = _bundle()
    with pytest.raises(ValueError, match="pair execution is incomplete"):
        validate_rt021_bundle(
            attachments,
            manifest,
            pair_results.iloc[:-1].copy(),
            corridors,
            metadata,
        )


def test_attachment_graph_epoch_mismatch_fails_closed():
    attachments, manifest, pair_results, corridors, metadata = _bundle()
    attachments = attachments.copy()
    attachments.loc[attachments.index[0], "graph_epoch_id"] = "OTHER_EPOCH"
    with pytest.raises(ValueError, match="one graph epoch|same graph epoch"):
        validate_rt021_bundle(
            attachments, manifest, pair_results, corridors, metadata
        )


def test_corridor_pair_endpoint_mismatch_fails_closed():
    attachments, manifest, pair_results, corridors, metadata = _bundle()
    corridors = corridors.copy()
    corridors.loc[corridors.index[0], "target_routing_terminal_id"] = "S35"
    with pytest.raises(ValueError, match="corridor endpoint mismatch"):
        validate_rt021_bundle(
            attachments, manifest, pair_results, corridors, metadata
        )


def test_exact_occurrence_order_and_a_to_c_via_b_is_decomposable():
    attachments = _attachments()
    stop_ids = attachments.loc[
        attachments["service_class"] == "CONVENTIONAL_TPL", "stop_place_id"
    ].tolist()
    a, b, c = stop_ids[:3]
    node = dict(zip(attachments["stop_place_id"], attachments["graph_node_id"]))
    corridors = pd.DataFrame(
        [
            {
                "corridor_id": "CAB",
                "pair_id": "PAB",
                "source_routing_terminal_id": a,
                "target_routing_terminal_id": b,
                "path_node_ids": f"{node[a]};{node[b]}",
                "admissible_for_corridor_pool": True,
            },
            {
                "corridor_id": "CAC",
                "pair_id": "PAC",
                "source_routing_terminal_id": a,
                "target_routing_terminal_id": c,
                "path_node_ids": f"{node[a]};{node[b]};{node[c]}",
                "admissible_for_corridor_pool": True,
            },
        ]
    )
    occurrences = pd.concat(
        [
            materialize_stop_occurrences(
                row.corridor_id,
                str(row.path_node_ids).split(";"),
                attachments,
            )
            for row in corridors.itertuples(index=False)
        ],
        ignore_index=True,
    )
    ac = occurrences[occurrences["corridor_id"] == "CAC"]
    assert ac["stop_place_id"].tolist() == [a, b, c]
    classification = classify_elementary_corridors(corridors, occurrences)
    by_id = classification.set_index("corridor_id")
    assert bool(by_id.loc["CAB", "elementary_for_structural_reduction"])
    assert not bool(by_id.loc["CAC", "elementary_for_structural_reduction"])
    assert by_id.loc["CAC", "via_stop_place_ids_ordered_unique"] == b


def test_directional_elementary_asymmetry_blocks_reciprocal_link():
    attachments, manifest, pair_results, corridors, metadata = _bundle()
    first = corridors.iloc[0]
    source = str(first["source_routing_terminal_id"])
    target = str(first["target_routing_terminal_id"])
    reverse_mask = (
        (corridors["source_routing_terminal_id"] == target)
        & (corridors["target_routing_terminal_id"] == source)
    )
    reverse_index = corridors.index[reverse_mask][0]
    third = next(
        stop_id
        for stop_id in attachments.loc[
            attachments["service_class"] == "CONVENTIONAL_TPL", "stop_place_id"
        ]
        if stop_id not in {source, target}
    )
    node = dict(zip(attachments["stop_place_id"], attachments["graph_node_id"]))
    corridors = corridors.copy()
    corridors.loc[
        reverse_index, "path_node_ids"
    ] = f"{node[target]};{node[third]};{node[source]}"

    occurrences = pd.concat(
        [
            materialize_stop_occurrences(
                row.corridor_id,
                str(row.path_node_ids).split(";"),
                attachments,
            )
            for row in corridors.itertuples(index=False)
        ],
        ignore_index=True,
    )
    classification = classify_elementary_corridors(corridors, occurrences)
    filtered = filter_elementary_corridors_for_reciprocity(corridors, classification)
    reciprocity = build_reciprocal_structural_links(pair_results, filtered)
    pair_audit = reciprocity["pair_audit"]
    audited = pair_audit[
        pair_audit.apply(
            lambda row: {row["terminal_a"], row["terminal_b"]} == {source, target},
            axis=1,
        )
    ].iloc[0]
    assert not bool(audited["eligible_for_bidirectional_undirected_structure"])


def test_controlled_chain_covers_all_policy_groups_and_is_topology_neutral():
    attachments, manifest, pair_results, corridors, metadata = _bundle()
    result = run_rt022_orchestrator(
        attachments,
        manifest,
        pair_results,
        corridors,
        metadata,
        max_edges=4,
        max_states=1000,
        max_structures=100,
    )
    assert result["status"] == FIXTURE_PASS_STATUS
    assert result["complete"] is True
    assert len(result["structural_links"]) == 4
    assert len(result["structures"]) == 1
    structure = result["structures"].iloc[0]
    assert structure["topology_class"] == "PATH"
    assert structure["shape_flags"] == ""
    params = result["frontier_metadata"]["technical_parameters"]
    assert "topology" not in params
    assert "figure" not in params


def test_rt008_cap_hit_is_blocked_and_returns_no_partial_structures():
    attachments, manifest, pair_results, corridors, metadata = _bundle()
    result = run_rt022_orchestrator(
        attachments,
        manifest,
        pair_results,
        corridors,
        metadata,
        max_edges=4,
        max_states=1,
        max_structures=100,
    )
    assert result["status"] == BLOCKED_FRONTIER
    assert result["complete"] is False
    assert result["structures"].empty


def test_input_order_invariance_preserves_digests_and_structure_identity():
    attachments, manifest, pair_results, corridors, metadata = _bundle()
    first = run_rt022_orchestrator(
        attachments,
        manifest,
        pair_results,
        corridors,
        metadata,
        max_edges=4,
        max_states=1000,
        max_structures=100,
    )
    second = run_rt022_orchestrator(
        attachments.iloc[::-1].reset_index(drop=True),
        manifest.iloc[::-1].reset_index(drop=True),
        pair_results.iloc[::-1].reset_index(drop=True),
        corridors.iloc[::-1].reset_index(drop=True),
        metadata,
        max_edges=4,
        max_states=1000,
        max_structures=100,
    )
    assert first["digests"] == second["digests"]
    assert first["structures"].to_dict("records") == second["structures"].to_dict("records")


def test_real_mode_rejects_controlled_fixture_metadata():
    attachments, manifest, pair_results, corridors, metadata = _bundle()
    with pytest.raises(ValueError, match="controlled/synthetic fixture"):
        run_rt022_orchestrator(
            attachments,
            manifest,
            pair_results,
            corridors,
            metadata,
            require_real_rt021_pass=True,
            max_edges=4,
        )


def test_prepared_status_makes_no_territorial_claim():
    status = prepared_status_record()
    assert status["status"] == PREPARED_STATUS
    assert status["territorial_result_claimed"] is False
    assert status["rt021_required"] is True
    assert status["topology_prior"] is False
    assert status["service_terminal_selection"] is False


def test_canonical_frame_digest_is_row_order_invariant():
    frame = pd.DataFrame(
        [
            {"id": "B", "value": 2},
            {"id": "A", "value": 1},
        ]
    )
    assert canonical_frame_sha256(frame, sort_by=["id"]) == canonical_frame_sha256(
        frame.iloc[::-1].reset_index(drop=True), sort_by=["id"]
    )
