from __future__ import annotations

import pandas as pd
import pytest

from src.phase2_reduced_path_matrix_v2 import _group_existing_evidence


def test_core_gtfs_records_preserve_fact_reference_status():
    group = pd.DataFrame({
        "epistemic_status": [
            "FACT_OFFICIAL_GTFS_REFERENCE_PERIOD_NOT_CURRENT_SERVICE",
            "FACT_OFFICIAL_GTFS_REFERENCE_PERIOD_NOT_CURRENT_SERVICE",
        ],
        "source_scope": ["GATE_B_CORE_GTFS_RECORD", "GATE_B_CORE_GTFS_RECORD"],
    })
    evidence, scope = _group_existing_evidence(group)
    assert evidence == "FACT_OFFICIAL_GTFS_REFERENCE_PERIOD_NOT_CURRENT_SERVICE"
    assert scope == "GATE_B_CORE_GTFS_RECORD"


def test_context_centroid_is_not_promoted_to_exact_fact():
    group = pd.DataFrame({
        "epistemic_status": ["FACT_OFFICIAL_GTFS_REFERENCE_PERIOD_CLUSTER_CENTROID"],
        "source_scope": ["ANALYSIS_ENVELOPE_GATE_D_GTFS_CLUSTER_CENTROID"],
    })
    evidence, scope = _group_existing_evidence(group)
    assert evidence == "DERIVED_OFFICIAL_GTFS_REFERENCE_PERIOD_CLUSTER_CENTROID"
    assert scope == "ANALYSIS_ENVELOPE_GATE_D_GTFS_CLUSTER_CENTROID"


def test_unexpected_existing_status_is_rejected():
    group = pd.DataFrame({
        "epistemic_status": ["ESTIMATE_UNKNOWN"],
        "source_scope": ["GATE_B_CORE_GTFS_RECORD"],
    })
    with pytest.raises(ValueError, match="Unexpected existing-stop epistemic statuses"):
        _group_existing_evidence(group)
