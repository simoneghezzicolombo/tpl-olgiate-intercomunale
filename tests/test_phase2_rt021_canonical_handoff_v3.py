from __future__ import annotations

import pandas as pd

from scripts.phase2_rt021_canonical_handoff_v3 import canonicalize_frames
from src.phase2_complete_directed_pairs_v3 import directed_pair_id


def test_canonical_handoff_changes_identity_only_and_preserves_explicit_failure():
    pair_status = pd.DataFrame(
        [
            {
                "pair_id": "INTERNAL_A_B",
                "source_routing_terminal_id": "STOP_PLACE::A",
                "target_routing_terminal_id": "STOP_PLACE::B",
                "corridor_count": 1,
                "failure_reason": "",
                "running_minutes_model": "1.000000000",
            },
            {
                "pair_id": "INTERNAL_B_A",
                "source_routing_terminal_id": "STOP_PLACE::B",
                "target_routing_terminal_id": "STOP_PLACE::A",
                "corridor_count": 0,
                "failure_reason": "NO_PHYSICAL_LOOPLESS_CORRIDOR_ADMITTED_WITHIN_VALIDATED_RT006_PARAMETER_GRID",
                "running_minutes_model": "1.100000000",
            },
        ]
    )
    corridors = pd.DataFrame(
        [
            {
                "corridor_id": "INTERNAL_CORRIDOR",
                "pair_id": "INTERNAL_A_B",
                "source_routing_terminal_id": "STOP_PLACE::A",
                "target_routing_terminal_id": "STOP_PLACE::B",
                "path_edge_ids": "e1;e2",
                "path_node_ids": "n1;n2;n3",
                "running_minutes_model": "1.000000000",
                "distance_m": "100.000000",
            }
        ]
    )

    p, c = canonicalize_frames(pair_status, corridors)

    assert list(p["source_routing_terminal_id"]) == ["A", "B"]
    assert list(p["target_routing_terminal_id"]) == ["B", "A"]
    assert list(p["pair_id"]) == [directed_pair_id("A", "B"), directed_pair_id("B", "A")]
    assert p["gate_d_route_found"].tolist() == [True, True]
    assert p.loc[1, "failure_reason"].startswith("NO_PHYSICAL_LOOPLESS_CORRIDOR")

    assert c.loc[0, "pair_id"] == directed_pair_id("A", "B")
    assert c.loc[0, "source_routing_terminal_id"] == "A"
    assert c.loc[0, "target_routing_terminal_id"] == "B"
    assert c.loc[0, "path_edge_ids"] == "e1;e2"
    assert c.loc[0, "path_node_ids"] == "n1;n2;n3"
    assert c.loc[0, "running_minutes_model"] == "1.000000000"
    assert c.loc[0, "distance_m"] == "100.000000"
    assert bool(c.loc[0, "admissible_for_corridor_pool"]) is True
