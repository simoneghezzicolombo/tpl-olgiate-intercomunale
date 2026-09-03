import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.gate_f_status import enforce_verified_status_evidence, load_gate_status_bundle


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bundle(tmp_path):
    gates = {}
    for gate in "ABCDE":
        evidence = tmp_path / f"gate_{gate.lower()}_pass.md"
        evidence.write_text(f"Gate {gate} evidence\n", encoding="utf-8")
        gates[gate] = {
            "verdict": "PASS",
            "commit_sha": (gate.lower() if gate.lower() in "abcdef" else "a") * 40,
            "source_branch": f"gate-{gate.lower()}-workstream",
            "evidence_files": [{"path": evidence.name, "sha256": _hash(evidence)}],
        }
    payload = {"schema_version": 1, "integration_id": "TEST_INTEGRATION", "gates": gates}
    bundle_path = tmp_path / "status.json"
    bundle_path.write_text(json.dumps(payload), encoding="utf-8")
    return bundle_path, payload


def test_valid_hashed_bundle_unlocks_verified_statuses(tmp_path):
    path, _ = _bundle(tmp_path)
    statuses, bundle = load_gate_status_bundle(path, tmp_path)
    assert statuses == {g: "PASS" for g in "ABCDE"}
    assert bundle["integration_id"] == "TEST_INTEGRATION"


def test_evidence_hash_mismatch_fails_closed(tmp_path):
    path, payload = _bundle(tmp_path)
    evidence = tmp_path / "gate_b_pass.md"
    evidence.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_gate_status_bundle(path, tmp_path)


def test_missing_evidence_file_fails_closed(tmp_path):
    path, payload = _bundle(tmp_path)
    (tmp_path / "gate_c_pass.md").unlink()
    with pytest.raises(ValueError, match="evidence file is missing"):
        load_gate_status_bundle(path, tmp_path)


def test_short_commit_sha_is_rejected(tmp_path):
    path, payload = _bundle(tmp_path)
    payload["gates"]["D"]["commit_sha"] = "abc123"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="40-hex"):
        load_gate_status_bundle(path, tmp_path)


def test_missing_gate_is_rejected(tmp_path):
    path, payload = _bundle(tmp_path)
    del payload["gates"]["E"]
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="exactly A-E"):
        load_gate_status_bundle(path, tmp_path)


def test_evidence_path_cannot_escape_repo(tmp_path):
    path, payload = _bundle(tmp_path)
    payload["gates"]["A"]["evidence_files"][0]["path"] = "../outside.md"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="escapes repository root"):
        load_gate_status_bundle(path, tmp_path)


def test_manual_all_pass_summary_is_downgraded_without_verified_bundle():
    summary = {
        "verdict": "PASS",
        "dependency_status": [],
        "evidence_status": [],
        "recommendation_status": "UNIQUE_ROBUST_PARETO_DOMINANT",
        "recommended_scenario_id": "ALT",
        "reason": "test",
    }
    blocked = enforce_verified_status_evidence(summary, verified=False)
    assert blocked["verdict"] == "PROVISIONAL"
    assert blocked["recommended_scenario_id"] is None
    assert "UNVERIFIED_GATE_STATUS_EVIDENCE" in blocked["evidence_status"]


def test_verified_bundle_does_not_modify_summary():
    summary = {"verdict": "PASS", "recommendation_status": "X", "recommended_scenario_id": "ALT"}
    assert enforce_verified_status_evidence(summary, verified=True) == summary
