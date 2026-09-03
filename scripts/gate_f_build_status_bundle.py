#!/usr/bin/env python3
"""Generate a Gate F schema-v2 status bundle directly from exact Git objects."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
GATES = "ABCDE"
VERDICTS = {"PASS", "PROVISIONAL", "FAIL", "IN_PROGRESS"}


def git_bytes(commit: str, path: str) -> bytes:
    check = subprocess.run(["git", "cat-file", "-e", f"{commit}^{{commit}}"], cwd=ROOT, capture_output=True)
    if check.returncode != 0:
        raise ValueError(f"Git commit not available: {commit}")
    result = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=ROOT, capture_output=True)
    if result.returncode != 0:
        raise ValueError(f"Git evidence not available: {commit}:{path}")
    return result.stdout


def parse_spec(raw: str) -> tuple[str, dict]:
    # GATE,VERDICT,COMMIT,BRANCH,PATH ; commas are forbidden in these identifiers.
    parts = [part.strip() for part in raw.split(",")]
    if len(parts) != 5:
        raise ValueError("--gate requires GATE,VERDICT,COMMIT,BRANCH,PATH")
    gate, verdict, commit, branch, path = parts
    gate = gate.upper().replace("GATE_", "").replace("GATE ", "")
    verdict = verdict.upper()
    commit = commit.lower()
    if gate not in GATES:
        raise ValueError(f"Unsupported gate {gate!r}")
    if verdict not in VERDICTS:
        raise ValueError(f"Unsupported verdict {verdict!r}")
    if len(commit) != 40 or any(ch not in "0123456789abcdef" for ch in commit):
        raise ValueError(f"Gate {gate} requires a full 40-hex commit")
    if not branch or not path or path.startswith("/") or ".." in Path(path).parts:
        raise ValueError(f"Gate {gate} branch/path is invalid")
    payload = git_bytes(commit, path)
    return gate, {
        "verdict": verdict,
        "commit_sha": commit,
        "source_branch": branch,
        "evidence_files": [
            {"mode": "GIT_OBJECT", "path": path, "sha256": hashlib.sha256(payload).hexdigest()}
        ],
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--integration-id", required=True)
    p.add_argument("--gate", action="append", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    try:
        gates = {}
        for raw in args.gate:
            gate, entry = parse_spec(raw)
            if gate in gates:
                raise ValueError(f"Duplicate Gate {gate}")
            gates[gate] = entry
        if set(gates) != set(GATES):
            raise ValueError(f"Status bundle requires exactly A-E; got {sorted(gates)}")
        bundle = {"schema_version": 2, "integration_id": args.integration_id, "gates": gates}
        target = args.output if args.output.is_absolute() else ROOT / args.output
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Gate F status bundle written: {target}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"GATE_F_STATUS_BUNDLE_FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
