from __future__ import annotations

import pandas as pd
import pytest

from src.phase2_territorial_structural_search_rt006_compat_v3 import (
    REAL_RT006_EXPLICIT_FAILURE,
    explicit_rt006_missing_corridor_pair_ids,
)


def _pairs(reason: str, corridor_count: int = 0) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "pair_id": "P_AB",
                "source_routing_terminal_id": "A",
                "target_routing_terminal_id": "B",
                "gate_d_route_found": True,
                "corridor_count": corridor_count,
                "failure_reason": reason,
            },
            {
                "pair_id": "P_BA",
                "source_routing_terminal_id": "B",
                "target_routing_terminal_id": "A",
                "gate_d_route_found": True,
                "corridor_count": 1,
                "failure_reason": "",
            },
        ]
    )


def _corridors() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "pair_id": "P_BA",
                "corridor_id": "C_BA",
            }
        ]
    )


def test_explicit_rt006_failure_keeps_gate_d_reachability_true():
    pairs = _pairs(REAL_RT006_EXPLICIT_FAILURE)
    missing = explicit_rt006_missing_corridor_pair_ids(
        pairs,
        _corridors(),
        require_real_rt021_pass=True,
    )
    assert missing == {"P_AB"}
    assert bool(pairs.loc[pairs["pair_id"].eq("P_AB"), "gate_d_route_found"].iloc[0]) is True


def test_silent_missing_corridor_fails_closed():
    with pytest.raises(ValueError, match="no explicit RT-006 failure"):
        explicit_rt006_missing_corridor_pair_ids(
            _pairs(""),
            _corridors(),
            require_real_rt021_pass=True,
        )


def test_nonzero_corridor_count_without_corridor_record_fails_closed():
    with pytest.raises(ValueError, match="nonzero corridor_count"):
        explicit_rt006_missing_corridor_pair_ids(
            _pairs(REAL_RT006_EXPLICIT_FAILURE, corridor_count=1),
            _corridors(),
            require_real_rt021_pass=True,
        )


def test_real_mode_rejects_unknown_missing_corridor_reason():
    with pytest.raises(ValueError, match="unrecognized failure reason"):
        explicit_rt006_missing_corridor_pair_ids(
            _pairs("SOME_OTHER_FAILURE"),
            _corridors(),
            require_real_rt021_pass=True,
        )
