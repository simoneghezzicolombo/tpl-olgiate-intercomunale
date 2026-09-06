from __future__ import annotations

import pandas as pd

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
