import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.gate_f_assembly import (
    build_assembly_manifest,
    comparison_scope_audit,
    enforce_verified_assembly_evidence,
    verify_assembly_manifest,
    write_assembly_manifest,
)


def _files(tmp_path):
    paths = {}
    for name in ("catalog", "gate_b", "gate_c", "gate_d", "gate_e"):
        path = tmp_path / f"{name}.csv"
        path.write_text(f"source,{name}\n", encoding="utf-8")
        paths[name] = path
    metrics = tmp_path / "metrics.csv"
    metrics.write_text("scenario_id\nBASE\nALT\n", encoding="utf-8")
    exclusions = tmp_path / "exclusions.csv"
    exclusions.write_text("scenario_id\n", encoding="utf-8")
    eligible = pd.DataFrame([
        {"scenario_id": "BASE", "topology_family": "CURRENT", "is_baseline": True},
        {"scenario_id": "ALT", "topology_family": "RING", "is_baseline": False},
    ])
    excluded = pd.DataFrame(columns=["scenario_id", "topology_family"])
    return paths, metrics, exclusions, eligible, excluded


def test_assembly_manifest_roundtrip_verifies_all_hashes(tmp_path):
    paths, metrics, exclusions, eligible, excluded = _files(tmp_path)
    manifest = build_assembly_manifest(
        repo_root=tmp_path,
        inputs=paths,
        metrics_output=metrics,
        exclusions_output=exclusions,
        eligible=eligible,
        excluded=excluded,
    )
    manifest_path = tmp_path / "manifest.json"
    write_assembly_manifest(manifest_path, manifest)
    verified = verify_assembly_manifest(manifest_path, tmp_path, metrics)
    assert verified["eligible_scenario_ids"] == ["ALT", "BASE"]
    assert verified["baseline_scenario_id"] == "BASE"


def test_tampered_metrics_are_detected(tmp_path):
    paths, metrics, exclusions, eligible, excluded = _files(tmp_path)
    manifest = build_assembly_manifest(repo_root=tmp_path, inputs=paths, metrics_output=metrics, exclusions_output=exclusions, eligible=eligible, excluded=excluded)
    manifest_path = tmp_path / "manifest.json"
    write_assembly_manifest(manifest_path, manifest)
    metrics.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_assembly_manifest(manifest_path, tmp_path, metrics)


def test_tampered_upstream_fragment_is_detected(tmp_path):
    paths, metrics, exclusions, eligible, excluded = _files(tmp_path)
    manifest = build_assembly_manifest(repo_root=tmp_path, inputs=paths, metrics_output=metrics, exclusions_output=exclusions, eligible=eligible, excluded=excluded)
    manifest_path = tmp_path / "manifest.json"
    write_assembly_manifest(manifest_path, manifest)
    paths["gate_c"].write_text("changed\n", encoding="utf-8")
    with pytest.raises(ValueError, match="input:gate_c hash mismatch"):
        verify_assembly_manifest(manifest_path, tmp_path, metrics)


def test_manifest_must_match_requested_metrics_path(tmp_path):
    paths, metrics, exclusions, eligible, excluded = _files(tmp_path)
    manifest = build_assembly_manifest(repo_root=tmp_path, inputs=paths, metrics_output=metrics, exclusions_output=exclusions, eligible=eligible, excluded=excluded)
    manifest_path = tmp_path / "manifest.json"
    write_assembly_manifest(manifest_path, manifest)
    other = tmp_path / "other.csv"
    other.write_text(metrics.read_text(), encoding="utf-8")
    with pytest.raises(ValueError, match="does not match requested input"):
        verify_assembly_manifest(manifest_path, tmp_path, other)


def test_scope_audit_warns_when_only_one_nonbaseline_family():
    eligible = pd.DataFrame([
        {"scenario_id": "BASE", "topology_family": "CURRENT", "is_baseline": True},
        {"scenario_id": "A", "topology_family": "FIGURE_8", "is_baseline": False},
        {"scenario_id": "B", "topology_family": "FIGURE_8", "is_baseline": False},
    ])
    excluded = pd.DataFrame(columns=["scenario_id", "topology_family"])
    audit = comparison_scope_audit(eligible, excluded)
    assert audit["candidate_diversity_warning"] == "FEWER_THAN_TWO_NONBASELINE_TOPOLOGY_FAMILIES"


def test_scope_audit_does_not_prefer_any_topology_label():
    eligible = pd.DataFrame([
        {"scenario_id": "BASE", "topology_family": "CURRENT", "is_baseline": True},
        {"scenario_id": "A", "topology_family": "FIGURE_8", "is_baseline": False},
        {"scenario_id": "B", "topology_family": "RADIAL", "is_baseline": False},
    ])
    excluded = pd.DataFrame(columns=["scenario_id", "topology_family"])
    audit = comparison_scope_audit(eligible, excluded)
    assert audit["candidate_diversity_warning"] is None


def test_unverified_assembly_downgrades_an_otherwise_pass_summary():
    summary = {"verdict": "PASS", "evidence_status": [], "recommended_scenario_id": "ALT", "recommendation_status": "X"}
    blocked = enforce_verified_assembly_evidence(summary, False)
    assert blocked["verdict"] == "PROVISIONAL"
    assert blocked["recommended_scenario_id"] is None
    assert "UNVERIFIED_ASSEMBLY_MANIFEST" in blocked["evidence_status"]
