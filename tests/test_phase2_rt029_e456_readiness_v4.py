from __future__ import annotations

import pandas as pd
import pytest

from phase2_candidate_accessibility_pareto_v4 import (
    RT029V4ContractError,
    readiness_audit,
)
from test_phase2_candidate_accessibility_pareto_v4 import _layers, _rt023, _walk


def _ready(**overrides):
    args = {
        "structure_layers": _layers(),
        "rt023_realizations": _rt023(),
        "walk_matrix": _walk(),
        "expected_layer_counts": {4: 2, 5: 1, 6: 1},
        "expected_population_units": 3,
        "lineage": {"fixture": "controlled_only"},
    }
    args.update(overrides)
    return readiness_audit(**args)


def test_readiness_waits_for_certified_passenger_stop_realization() -> None:
    audit = _ready()
    assert audit["status"] == "PASS_PREPARED_WAITING_PASSENGER_STOP_REALIZATION"
    assert audit["structure_count"] == 4
    assert audit["pareto_run_performed"] is False
    assert audit["passenger_stop_realization_required"] is True
    assert audit["final_passenger_stop_set_count"] is None
    assert all(value is False for value in audit["negative_assertions"].values())


def test_readiness_missing_rt023_direction_fails_closed() -> None:
    bad = _rt023()
    bad = bad[~((bad.structural_link_id == "L45") & (bad.direction == "B_TO_A"))]
    with pytest.raises(RT029V4ContractError, match="both A_TO_B and B_TO_A"):
        _ready(rt023_realizations=bad)


def test_readiness_rejects_cross_layer_duplicate_structure_id() -> None:
    layers = _layers()
    layers[5] = layers[5].copy()
    layers[5].loc[0, "structure_id"] = "E4_A"
    with pytest.raises(RT029V4ContractError, match="not disjoint"):
        _ready(structure_layers=layers)


def test_readiness_is_input_order_invariant() -> None:
    a = _ready()
    layers = {edge: frame.iloc[::-1].reset_index(drop=True) for edge, frame in _layers().items()}
    b = _ready(
        structure_layers=layers,
        rt023_realizations=_rt023().iloc[::-1].reset_index(drop=True),
        walk_matrix=_walk().iloc[::-1].reset_index(drop=True),
    )
    for key in (
        "structure_count", "layer_counts", "required_structural_link_count",
        "rt023_realization_count", "population_unit_count", "rt028_stop_count",
        "current_vertex_set_count_diagnostic_only",
    ):
        assert a[key] == b[key]
