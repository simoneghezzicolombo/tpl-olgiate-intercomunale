"""Deterministic Gate F assembly manifest and comparison-scope audit."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

import pandas as pd

from src.gate_f_inputs import strict_bool_series
from src.gate_f_status import sha256_file


INPUT_KEYS = ("catalog", "gate_b", "gate_c", "gate_d", "gate_e")


def _repo_relative(path: str | Path, repo_root: str | Path) -> tuple[Path, str]:
    root = Path(repo_root).resolve()
    resolved = Path(path).resolve()
    try:
        rel = resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Gate F assembly artifact must be inside repository root: {resolved}") from exc
    return resolved, rel.as_posix()


def artifact_record(path: str | Path, repo_root: str | Path) -> dict[str, str]:
    resolved, rel = _repo_relative(path, repo_root)
    if not resolved.is_file():
        raise ValueError(f"Gate F assembly artifact missing: {rel}")
    return {"path": rel, "sha256": sha256_file(resolved)}


def comparison_scope_audit(eligible: pd.DataFrame, excluded: pd.DataFrame) -> dict[str, object]:
    if eligible.empty:
        raise ValueError("Gate F comparison scope has no eligible scenarios")
    baseline = strict_bool_series(eligible["is_baseline"], "is_baseline")
    if int(baseline.sum()) != 1:
        raise ValueError("Gate F comparison scope requires exactly one eligible baseline")
    eligible_families = sorted(set(eligible["topology_family"].astype(str)))
    nonbaseline = eligible.loc[~baseline]
    nonbaseline_families = sorted(set(nonbaseline["topology_family"].astype(str)))
    all_frames = [eligible[["scenario_id", "topology_family"]]]
    if not excluded.empty:
        all_frames.append(excluded[["scenario_id", "topology_family"]])
    catalog = pd.concat(all_frames, ignore_index=True)
    catalog_families = sorted(set(catalog["topology_family"].astype(str)))
    return {
        "catalog_scenario_count": int(len(catalog)),
        "eligible_scenario_count": int(len(eligible)),
        "excluded_scenario_count": int(len(excluded)),
        "catalog_topology_families": catalog_families,
        "eligible_topology_families": eligible_families,
        "nonbaseline_eligible_topology_families": nonbaseline_families,
        "candidate_diversity_warning": (
            "FEWER_THAN_TWO_NONBASELINE_TOPOLOGY_FAMILIES"
            if len(nonbaseline_families) < 2
            else None
        ),
        "note": (
            "Topology diversity is an audit warning, not an optimization preference. "
            "Human review must confirm that serious alternatives were not omitted."
        ),
    }


def build_assembly_manifest(
    *,
    repo_root: str | Path,
    inputs: Mapping[str, str | Path],
    metrics_output: str | Path,
    exclusions_output: str | Path,
    eligible: pd.DataFrame,
    excluded: pd.DataFrame,
) -> dict:
    if set(inputs) != set(INPUT_KEYS):
        raise ValueError(f"Assembly inputs must be exactly {INPUT_KEYS}")
    baseline_mask = strict_bool_series(eligible["is_baseline"], "is_baseline")
    baseline_id = str(eligible.loc[baseline_mask, "scenario_id"].iloc[0])
    return {
        "schema_version": 1,
        "inputs": {key: artifact_record(inputs[key], repo_root) for key in INPUT_KEYS},
        "outputs": {
            "scenario_metrics": artifact_record(metrics_output, repo_root),
            "exclusions": artifact_record(exclusions_output, repo_root),
        },
        "baseline_scenario_id": baseline_id,
        "eligible_scenario_ids": sorted(eligible["scenario_id"].astype(str).tolist()),
        "excluded_scenario_ids": sorted(excluded["scenario_id"].astype(str).tolist()),
        "comparison_scope": comparison_scope_audit(eligible, excluded),
    }


def write_assembly_manifest(path: str | Path, manifest: Mapping[str, object]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _verify_record(record: object, repo_root: Path, label: str) -> Path:
    if not isinstance(record, dict):
        raise ValueError(f"Assembly manifest {label} must be an object")
    raw_path = str(record.get("path", "")).strip()
    expected = str(record.get("sha256", "")).strip().lower()
    if len(expected) != 64 or any(ch not in "0123456789abcdef" for ch in expected):
        raise ValueError(f"Assembly manifest {label} has invalid sha256")
    root = repo_root.resolve()
    candidate = (root / raw_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Assembly manifest {label} path escapes repository: {raw_path}") from exc
    if not candidate.is_file():
        raise ValueError(f"Assembly manifest {label} file missing: {raw_path}")
    actual = sha256_file(candidate)
    if actual != expected:
        raise ValueError(f"Assembly manifest {label} hash mismatch: expected {expected}, got {actual}")
    return candidate


def verify_assembly_manifest(
    path: str | Path,
    repo_root: str | Path,
    expected_metrics_path: str | Path | None = None,
) -> dict:
    try:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read Gate F assembly manifest: {exc}") from exc
    if manifest.get("schema_version") != 1:
        raise ValueError("Gate F assembly manifest schema_version must equal 1")
    inputs = manifest.get("inputs")
    outputs = manifest.get("outputs")
    if not isinstance(inputs, dict) or set(inputs) != set(INPUT_KEYS):
        raise ValueError("Gate F assembly manifest inputs must be exactly catalog/B/C/D/E")
    if not isinstance(outputs, dict) or set(outputs) != {"scenario_metrics", "exclusions"}:
        raise ValueError("Gate F assembly manifest outputs must be scenario_metrics and exclusions")
    root = Path(repo_root)
    for key in INPUT_KEYS:
        _verify_record(inputs[key], root, f"input:{key}")
    metrics = _verify_record(outputs["scenario_metrics"], root, "output:scenario_metrics")
    _verify_record(outputs["exclusions"], root, "output:exclusions")
    if expected_metrics_path is not None and metrics != Path(expected_metrics_path).resolve():
        raise ValueError(
            f"Assembly manifest scenario_metrics path {metrics} does not match requested input {Path(expected_metrics_path).resolve()}"
        )
    eligible_ids = manifest.get("eligible_scenario_ids")
    if not isinstance(eligible_ids, list) or len(eligible_ids) < 2 or len(set(eligible_ids)) != len(eligible_ids):
        raise ValueError("Assembly manifest requires at least two unique eligible scenario IDs")
    baseline_id = str(manifest.get("baseline_scenario_id", ""))
    if baseline_id not in eligible_ids:
        raise ValueError("Assembly manifest baseline_scenario_id must be eligible")
    return manifest


def enforce_verified_assembly_evidence(summary: Mapping[str, object], verified: bool) -> dict:
    out = dict(summary)
    if verified or out.get("verdict") != "PASS":
        return out
    evidence = list(out.get("evidence_status") or [])
    if "UNVERIFIED_ASSEMBLY_MANIFEST" not in evidence:
        evidence.append("UNVERIFIED_ASSEMBLY_MANIFEST")
    out["verdict"] = "PROVISIONAL"
    out["evidence_status"] = evidence
    out["recommendation_status"] = "BLOCKED_UNVERIFIED_ASSEMBLY_MANIFEST"
    out["recommended_scenario_id"] = None
    out["reason"] = (
        "Scenario metrics were not verified against a deterministic Gate F assembly manifest; "
        "a definitive recommendation is not permitted."
    )
    return out
