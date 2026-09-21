import json

import pytest

from scripts import phase2_build_rt031_full_18h_surface_v4 as module


def test_compact_context_retains_robust_transfer_and_miss_axes():
    row = {"engineering_cases": [{}], "departures_min": [360],
           "robust_min_transfer_quality": 0.2,
           "worst_deterministic_bus_to_rail_miss_share_by_runtime_stress_min":
               {"0": 0.1}}
    assert module.compact_context(row) == {
        "robust_min_transfer_quality": 0.2,
        "worst_deterministic_bus_to_rail_miss_share_by_runtime_stress_min":
            {"0": 0.1}}


def test_aggregate_rejects_missing_candidate_phase(monkeypatch, tmp_path):
    monkeypatch.setattr(module, "SHARD_COUNT", 2)
    monkeypatch.setattr(module, "PROFILE_COUNT", 4)
    lineage = {"typed_audit": module.TYPED_SHA256}
    paths = []
    for shard_index in range(2):
        payload = {
            "contract": "RT031_FULL_MUNICIPAL_18H_PHASE_SHARD_V4",
            "status": "PASS_FULL_SHARD_NON_DECISIONAL",
            "shard_index": shard_index, "shard_count": 2,
            "profile_count": 2, "context_count": 60,
            "engineering_cases_per_context": 27,
            "template_id": module.TEMPLATE_ID,
            "input_sha256": lineage, "network_selected": False,
            "contexts": [],
        }
        path = tmp_path / f"{shard_index}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        paths.append(path)
    with pytest.raises(ValueError, match="coverage drift"):
        module.aggregate_shards(paths, ["a", "b", "c", "d"])
