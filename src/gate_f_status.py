"""Gate F status-evidence validation.

A definitive Gate F PASS cannot be unlocked by manually typing A=PASS...E=PASS.
It requires a machine-readable bundle that points to hashed evidence files for
all upstream gates. This validates evidence integrity, not the substantive truth
of an upstream audit, which remains the responsibility of each gate review.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Mapping


REQUIRED_GATES = ("A", "B", "C", "D", "E")
ALLOWED_VERDICTS = {"PASS", "PROVISIONAL", "FAIL", "IN_PROGRESS"}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_repo_path(repo_root: Path, raw_path: str) -> Path:
    if not raw_path or Path(raw_path).is_absolute():
        raise ValueError(f"Evidence path must be a non-empty repository-relative path: {raw_path!r}")
    root = repo_root.resolve()
    resolved = (root / raw_path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Evidence path escapes repository root: {raw_path}") from exc
    return resolved


def load_gate_status_bundle(path: str | Path, repo_root: str | Path) -> tuple[dict[str, str], dict]:
    bundle_path = Path(path)
    root = Path(repo_root)
    try:
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read Gate F status bundle: {exc}") from exc

    if bundle.get("schema_version") != 1:
        raise ValueError("Gate F status bundle schema_version must equal 1")
    integration_id = str(bundle.get("integration_id", "")).strip()
    if not integration_id:
        raise ValueError("Gate F status bundle requires a non-empty integration_id")
    gates = bundle.get("gates")
    if not isinstance(gates, dict):
        raise ValueError("Gate F status bundle requires a gates object")
    if set(gates) != set(REQUIRED_GATES):
        raise ValueError(
            f"Gate F status bundle must contain exactly A-E; missing={sorted(set(REQUIRED_GATES)-set(gates))}, "
            f"extra={sorted(set(gates)-set(REQUIRED_GATES))}"
        )

    statuses: dict[str, str] = {}
    for gate in REQUIRED_GATES:
        entry = gates[gate]
        if not isinstance(entry, dict):
            raise ValueError(f"Gate {gate} status entry must be an object")
        verdict = str(entry.get("verdict", "")).strip().upper()
        if verdict not in ALLOWED_VERDICTS:
            raise ValueError(f"Gate {gate} has unsupported verdict: {verdict!r}")
        commit_sha = str(entry.get("commit_sha", "")).strip().lower()
        if not SHA_RE.fullmatch(commit_sha):
            raise ValueError(f"Gate {gate} commit_sha must be a full 40-hex SHA")
        source_branch = str(entry.get("source_branch", "")).strip()
        if not source_branch:
            raise ValueError(f"Gate {gate} requires source_branch")
        evidence_files = entry.get("evidence_files")
        if not isinstance(evidence_files, list) or not evidence_files:
            raise ValueError(f"Gate {gate} requires at least one evidence file")
        for evidence in evidence_files:
            if not isinstance(evidence, dict):
                raise ValueError(f"Gate {gate} evidence entries must be objects")
            raw_path = str(evidence.get("path", "")).strip()
            expected_hash = str(evidence.get("sha256", "")).strip().lower()
            if not HASH_RE.fullmatch(expected_hash):
                raise ValueError(f"Gate {gate} evidence {raw_path!r} requires a 64-hex sha256")
            evidence_path = _safe_repo_path(root, raw_path)
            if not evidence_path.is_file():
                raise ValueError(f"Gate {gate} evidence file is missing: {raw_path}")
            actual_hash = sha256_file(evidence_path)
            if actual_hash != expected_hash:
                raise ValueError(
                    f"Gate {gate} evidence hash mismatch for {raw_path}: expected {expected_hash}, got {actual_hash}"
                )
        statuses[gate] = verdict
    return statuses, bundle


def enforce_verified_status_evidence(summary: Mapping[str, object], verified: bool) -> dict:
    """Downgrade an otherwise definitive result when gate evidence was not verified."""
    out = dict(summary)
    if verified or out.get("verdict") != "PASS":
        return out
    evidence = list(out.get("evidence_status") or [])
    if "UNVERIFIED_GATE_STATUS_EVIDENCE" not in evidence:
        evidence.append("UNVERIFIED_GATE_STATUS_EVIDENCE")
    out["verdict"] = "PROVISIONAL"
    out["evidence_status"] = evidence
    out["recommendation_status"] = "BLOCKED_UNVERIFIED_GATE_STATUS_EVIDENCE"
    out["recommended_scenario_id"] = None
    out["reason"] = (
        "All typed gate statuses appear PASS, but no verified hashed status-evidence bundle was supplied; "
        "a definitive Gate F recommendation is not permitted."
    )
    return out
