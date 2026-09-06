from __future__ import annotations

import pandas as pd

from src import phase2_rt021_parallel_driver_v3 as parallel
from src.phase2_rt021_parallel_driver_v3 import partition_manifest


def test_source_partition_preserves_every_pair_once_without_splitting_sources():
    rows = []
    for source in ["A", "B", "C", "D", "E"]:
        for target in ["X", "Y", "Z"]:
            rows.append(
                {
                    "pair_id": f"{source}->{target}",
                    "source_routing_terminal_id": source,
                    "target_routing_terminal_id": target,
                }
            )
    manifest = pd.DataFrame(rows)
    parts = partition_manifest(manifest, workers=3)
    combined = pd.concat(parts, ignore_index=True)
    assert set(combined["pair_id"]) == set(manifest["pair_id"])
    assert len(combined) == len(manifest)
    assert combined["pair_id"].nunique() == len(manifest)
    source_to_part = {}
    for index, part in enumerate(parts):
        for source in set(part["source_routing_terminal_id"]):
            assert source not in source_to_part
            source_to_part[source] = index
    assert set(source_to_part) == {"A", "B", "C", "D", "E"}


def test_partition_is_input_order_invariant_at_pair_set_level():
    rows = [
        {"pair_id": "B->X", "source_routing_terminal_id": "B", "target_routing_terminal_id": "X"},
        {"pair_id": "A->Y", "source_routing_terminal_id": "A", "target_routing_terminal_id": "Y"},
        {"pair_id": "A->X", "source_routing_terminal_id": "A", "target_routing_terminal_id": "X"},
        {"pair_id": "B->Y", "source_routing_terminal_id": "B", "target_routing_terminal_id": "Y"},
    ]
    forward = partition_manifest(pd.DataFrame(rows), workers=2)
    reverse = partition_manifest(pd.DataFrame(list(reversed(rows))), workers=2)
    assert [set(part["pair_id"]) for part in forward] == [set(part["pair_id"]) for part in reverse]


def test_worker_uses_original_grid_router_even_if_bounded_module_is_monkeypatched(monkeypatch):
    manifest = pd.DataFrame(
        [
            {
                "pair_id": "A->B",
                "source_routing_terminal_id": "A",
                "target_routing_terminal_id": "B",
            }
        ]
    )
    sentinel_corridors = pd.DataFrame([{"corridor_id": "C"}])
    sentinel_status = pd.DataFrame([{"pair_id": "A->B"}])
    sentinel_audit = {"ok": True}

    def fake_original(*args, **kwargs):
        assert len(args[0]) == 1
        assert kwargs["epoch_id"] == "EPOCH"
        return sentinel_corridors, sentinel_status, sentinel_audit

    def recursive_dispatch_should_never_run(*args, **kwargs):
        raise AssertionError("worker called monkeypatched bounded.route_corpus")

    monkeypatch.setattr(parallel, "ORIGINAL_GRID_ROUTE_CORPUS", fake_original)
    monkeypatch.setattr(parallel.bounded, "route_corpus", recursive_dispatch_should_never_run)

    result = parallel._route_partition(
        (
            manifest,
            pd.DataFrame(),
            pd.DataFrame(),
            pd.DataFrame(),
            pd.DataFrame(),
            pd.DataFrame(),
            "EPOCH",
        )
    )
    assert result[0].equals(sentinel_corridors)
    assert result[1].equals(sentinel_status)
    assert result[2] == sentinel_audit
