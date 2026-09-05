import pandas as pd

from src.phase2_complete_directed_pairs_v3 import (
    CAP_STATUS,
    EXECUTION_BLOCKED,
    audit_pair_execution_completeness,
    build_complete_directed_pair_manifest,
    directed_pair_id,
)


def terminals(ids):
    return pd.DataFrame({"routing_terminal_id": ids})


def test_five_terminals_generate_exactly_twenty_directed_pairs():
    result = build_complete_directed_pair_manifest(terminals(["A", "B", "C", "D", "E"]))
    assert result["complete"] is True
    assert result["directed_pair_count"] == 20
    assert result["unordered_pair_count"] == 10
    manifest = result["manifest"]
    assert len(manifest) == 20
    assert not (manifest["source_routing_terminal_id"] == manifest["target_routing_terminal_id"]).any()


def test_every_pair_has_exactly_one_reverse_pair():
    manifest = build_complete_directed_pair_manifest(terminals(["A", "B", "C", "D"]))["manifest"]
    ids = set(manifest["pair_id"])
    assert manifest["pair_id"].is_unique
    for row in manifest.itertuples(index=False):
        assert row.reverse_pair_id in ids
        reverse = manifest.loc[manifest["pair_id"] == row.reverse_pair_id].iloc[0]
        assert reverse["source_routing_terminal_id"] == row.target_routing_terminal_id
        assert reverse["target_routing_terminal_id"] == row.source_routing_terminal_id
        assert reverse["reverse_pair_id"] == row.pair_id


def test_terminal_input_order_does_not_change_manifest():
    first = build_complete_directed_pair_manifest(terminals(["D", "A", "C", "B"]))["manifest"]
    second = build_complete_directed_pair_manifest(terminals(["A", "B", "C", "D"]))["manifest"]
    assert first.to_dict("records") == second.to_dict("records")


def test_pair_id_is_deterministic_and_directional():
    assert directed_pair_id("A", "B") == directed_pair_id("A", "B")
    assert directed_pair_id("A", "B") != directed_pair_id("B", "A")


def test_scale_cap_fails_closed_without_partial_manifest():
    result = build_complete_directed_pair_manifest(
        terminals(["A", "B", "C", "D", "E"]),
        max_directed_pairs=19,
    )
    assert result["status"] == CAP_STATUS
    assert result["complete"] is False
    assert result["required_directed_pair_count"] == 20
    assert result["manifest"].empty
    assert result["partial_manifest_returned"] is False


def test_complete_execution_passes_even_when_some_routes_are_not_found():
    manifest = build_complete_directed_pair_manifest(terminals(["A", "B", "C"]))["manifest"]
    results = manifest[[
        "pair_id",
        "source_routing_terminal_id",
        "target_routing_terminal_id",
    ]].copy()
    results["gate_d_route_found"] = [True, False, True, True, False, True]
    audit = audit_pair_execution_completeness(manifest, results)
    assert audit["status"] == "PASS_COMPLETE_PAIR_EXECUTION"
    assert audit["complete"] is True


def test_missing_result_is_incomplete_execution_not_no_route():
    manifest = build_complete_directed_pair_manifest(terminals(["A", "B", "C"]))["manifest"]
    results = manifest.iloc[:-1][[
        "pair_id",
        "source_routing_terminal_id",
        "target_routing_terminal_id",
    ]].copy()
    audit = audit_pair_execution_completeness(manifest, results)
    assert audit["status"] == EXECUTION_BLOCKED
    assert audit["complete"] is False
    assert len(audit["missing_result_pair_ids"]) == 1
    assert audit["missing_result_semantics"] == "MISSING_OUTPUT_IS_INCOMPLETE_EXECUTION_NOT_NO_ROUTE"


def test_duplicate_result_is_detected():
    manifest = build_complete_directed_pair_manifest(terminals(["A", "B", "C"]))["manifest"]
    base = manifest[[
        "pair_id",
        "source_routing_terminal_id",
        "target_routing_terminal_id",
    ]].copy()
    results = pd.concat([base, base.iloc[[0]]], ignore_index=True)
    audit = audit_pair_execution_completeness(manifest, results)
    assert audit["status"] == EXECUTION_BLOCKED
    assert audit["result_duplicate_pair_ids"] == [base.iloc[0]["pair_id"]]


def test_unexpected_result_is_detected():
    manifest = build_complete_directed_pair_manifest(terminals(["A", "B"]))["manifest"]
    results = manifest[[
        "pair_id",
        "source_routing_terminal_id",
        "target_routing_terminal_id",
    ]].copy()
    extra = pd.DataFrame([
        {
            "pair_id": "UNREQUESTED",
            "source_routing_terminal_id": "X",
            "target_routing_terminal_id": "Y",
        }
    ])
    audit = audit_pair_execution_completeness(manifest, pd.concat([results, extra], ignore_index=True))
    assert audit["status"] == EXECUTION_BLOCKED
    assert audit["unexpected_result_pair_ids"] == ["UNREQUESTED"]


def test_endpoint_mismatch_is_detected():
    manifest = build_complete_directed_pair_manifest(terminals(["A", "B", "C"]))["manifest"]
    results = manifest[[
        "pair_id",
        "source_routing_terminal_id",
        "target_routing_terminal_id",
    ]].copy()
    results.loc[0, "target_routing_terminal_id"] = "WRONG"
    audit = audit_pair_execution_completeness(manifest, results)
    assert audit["status"] == EXECUTION_BLOCKED
    assert audit["endpoint_mismatch_pair_ids"] == [manifest.iloc[0]["pair_id"]]


def test_blank_or_duplicate_terminal_ids_rejected():
    for ids in [["A", ""], ["A", "A"]]:
        try:
            build_complete_directed_pair_manifest(terminals(ids))
        except ValueError:
            pass
        else:
            raise AssertionError("invalid terminal universe should fail")
