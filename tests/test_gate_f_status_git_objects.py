import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.gate_f_status import load_gate_status_bundle


def _run(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip()


def _git_repo(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(repo, "init")
    _run(repo, "config", "user.email", "gate-f-test@example.invalid")
    _run(repo, "config", "user.name", "Gate F Test")
    hashes = {}
    for gate in "ABCDE":
        path = repo / f"gate_{gate.lower()}_pass.md"
        path.write_text(f"Gate {gate} PASS evidence\n", encoding="utf-8")
        hashes[gate] = hashlib.sha256(path.read_bytes()).hexdigest()
    _run(repo, "add", ".")
    _run(repo, "commit", "-m", "test evidence")
    commit = _run(repo, "rev-parse", "HEAD")
    return repo, commit, hashes


def _bundle(repo: Path, commit: str, hashes: dict[str, str]) -> Path:
    gates = {}
    for gate in "ABCDE":
        gates[gate] = {
            "verdict": "PASS",
            "commit_sha": commit,
            "source_branch": f"gate-{gate.lower()}-workstream",
            "evidence_files": [
                {
                    "mode": "GIT_OBJECT",
                    "path": f"gate_{gate.lower()}_pass.md",
                    "sha256": hashes[gate],
                }
            ],
        }
    path = repo / "status.json"
    path.write_text(
        json.dumps({"schema_version": 2, "integration_id": "GIT_OBJECT_TEST", "gates": gates}),
        encoding="utf-8",
    )
    return path


def test_git_object_evidence_survives_worktree_tampering(tmp_path):
    repo, commit, hashes = _git_repo(tmp_path)
    status = _bundle(repo, commit, hashes)
    (repo / "gate_c_pass.md").write_text("tampered worktree copy\n", encoding="utf-8")
    statuses, bundle = load_gate_status_bundle(status, repo)
    assert statuses == {gate: "PASS" for gate in "ABCDE"}
    assert bundle["schema_version"] == 2


def test_git_object_hash_mismatch_fails_closed(tmp_path):
    repo, commit, hashes = _git_repo(tmp_path)
    status = _bundle(repo, commit, hashes)
    payload = json.loads(status.read_text(encoding="utf-8"))
    payload["gates"]["D"]["evidence_files"][0]["sha256"] = "0" * 64
    status.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_gate_status_bundle(status, repo)


def test_git_object_missing_commit_fails_closed(tmp_path):
    repo, commit, hashes = _git_repo(tmp_path)
    status = _bundle(repo, commit, hashes)
    payload = json.loads(status.read_text(encoding="utf-8"))
    payload["gates"]["B"]["commit_sha"] = "f" * 40
    status.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="commit is not available"):
        load_gate_status_bundle(status, repo)


def test_v1_cannot_request_git_object_mode(tmp_path):
    repo, commit, hashes = _git_repo(tmp_path)
    status = _bundle(repo, commit, hashes)
    payload = json.loads(status.read_text(encoding="utf-8"))
    payload["schema_version"] = 1
    status.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="schema v1 supports WORKTREE"):
        load_gate_status_bundle(status, repo)
