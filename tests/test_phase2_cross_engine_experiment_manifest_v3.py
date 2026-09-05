from __future__ import annotations

from dataclasses import replace

import pytest

from src.phase2_cross_engine_experiment_manifest_v3 import (
    EngineExecutionBinding,
    ExperimentSpec,
    ODKey,
    authorize_cross_engine_comparison,
    freeze_experiment,
)


A = "a" * 64
B = "b" * 64
C = "c" * 64


def spec():
    return ExperimentSpec(
        schema_version="RT015_V3",
        candidate_id="CANDIDATE_X",
        candidate_gtfs_sha256=A,
        street_network_sha256=B,
        service_date="2026-10-01",
        timezone="Europe/Paris",
        departure_window_start_sec=21600,
        departure_window_end_sec=32400,
        modes=("walk", "transit"),
        od_keys=(ODKey("O2", "D1"), ODKey("O1", "D2"), ODKey("O1", "D1")),
    )


def test_repeat_and_shuffle_are_identical():
    s = spec()
    a = freeze_experiment(s)
    b = freeze_experiment(replace(s, modes=tuple(reversed(s.modes)), od_keys=tuple(reversed(s.od_keys))))
    assert a.canonical_json == b.canonical_json
    assert a.manifest_sha256 == b.manifest_sha256


@pytest.mark.parametrize(
    "changed",
    [
        {"candidate_gtfs_sha256": C},
        {"street_network_sha256": C},
        {"service_date": "2026-10-02"},
        {"departure_window_end_sec": 36000},
        {"modes": ("WALK",)},
        {"od_keys": (ODKey("O1", "D1"),)},
    ],
)
def test_material_change_changes_hash(changed):
    base = freeze_experiment(spec()).manifest_sha256
    assert freeze_experiment(replace(spec(), **changed)).manifest_sha256 != base


def test_duplicate_od_fails_closed():
    s = spec()
    with pytest.raises(ValueError, match="duplicate OD"):
        freeze_experiment(replace(s, od_keys=(ODKey("O1", "D1"), ODKey("O1", "D1"))))


@pytest.mark.parametrize(
    "changed,match",
    [
        ({"candidate_gtfs_sha256": "ABC"}, "lowercase SHA256"),
        ({"candidate_gtfs_sha256": "A" * 64}, "lowercase SHA256"),
        ({"service_date": "01-10-2026"}, "YYYY-MM-DD"),
        ({"timezone": "Not/AZone"}, "IANA"),
        ({"departure_window_start_sec": -1}, "non-negative"),
        ({"departure_window_start_sec": 40000}, "reversed"),
        ({"modes": ()}, "must not be empty"),
    ],
)
def test_invalid_manifest_fields_fail_closed(changed, match):
    with pytest.raises(ValueError, match=match):
        freeze_experiment(replace(spec(), **changed))


def test_same_manifest_authorizes_two_distinct_engines():
    frozen = freeze_experiment(spec())
    assert authorize_cross_engine_comparison(
        (
            EngineExecutionBinding("ENGINE_A", frozen.manifest_sha256),
            EngineExecutionBinding("ENGINE_B", frozen.manifest_sha256),
        ),
        expected_manifest_sha256=frozen.manifest_sha256,
    )


def test_manifest_mismatch_fails_before_discrepancy_analysis():
    frozen = freeze_experiment(spec())
    with pytest.raises(ValueError, match="EXPERIMENT_IDENTITY_MISMATCH"):
        authorize_cross_engine_comparison(
            (
                EngineExecutionBinding("ENGINE_A", frozen.manifest_sha256),
                EngineExecutionBinding("ENGINE_B", C),
            ),
            expected_manifest_sha256=frozen.manifest_sha256,
        )


def test_duplicate_engine_labels_fail_closed():
    frozen = freeze_experiment(spec())
    with pytest.raises(ValueError, match="distinct"):
        authorize_cross_engine_comparison(
            (
                EngineExecutionBinding("ENGINE_A", frozen.manifest_sha256),
                EngineExecutionBinding("ENGINE_A", frozen.manifest_sha256),
            ),
            expected_manifest_sha256=frozen.manifest_sha256,
        )
