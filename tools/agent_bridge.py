#!/usr/bin/env python3
"""Local bridge: GitHub Issue #1 -> Antigravity CLI.

Polls the public coordination issue for new comments containing `[GPT REVIEW]`.
For each unseen review, launches Antigravity CLI headlessly in the repository workspace.

The bridge is intentionally one-way and conservative:
- GitHub comments are read-only via the public REST API.
- Only comments containing the exact marker `[GPT REVIEW]` trigger Antigravity.
- Processed comment IDs are stored locally and never committed.
- No `--dangerously-skip-permissions` flag is used.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO = "simoneghezzicolombo/tpl-olgiate-intercomunale"
ISSUE = 1
MARKER = "[GPT REVIEW]"
STATE_FILENAME = ".agent_bridge_state.json"
API = f"https://api.github.com/repos/{REPO}/issues/{ISSUE}/comments?per_page=100"


def get_comments() -> list[dict]:
    req = urllib.request.Request(
        API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "tpl-olgiate-agent-bridge/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"processed_comment_ids": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"processed_comment_ids": []}


def save_state(path: Path, state: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(path)


def build_prompt(comment: dict) -> str:
    body = comment.get("body", "")
    url = comment.get("html_url", "")
    return f"""You are ANTIGRAVITY, executor agent for the repository {REPO}.

A new GPT external-review message has arrived on GitHub Issue #{ISSUE}.
Treat COLLABORATION_PROTOCOL.md and the coordination issue as binding workflow instructions.

REVIEW COMMENT URL:
{url}

REVIEW CONTENT:
{body}

ACTION:
1. Read the current repository state and latest comments in Issue #{ISSUE} if accessible.
2. Apply the GPT review to branch `antigravity-real-data`.
3. Do not bypass a failed gate.
4. Fix only what is required plus clearly independent non-dependent work.
5. Run the relevant tests and inspect actual outputs, not just exit codes.
6. Commit and push completed changes.
7. Publish a new `[ANTIGRAVITY HANDOFF]` comment in Issue #{ISSUE} if GitHub issue commenting is available in your environment. If not, update AGENT_STATUS.md with the exact handoff so the external reviewer can detect it.
8. Stop work that depends on the gate and request the corresponding review.
9. If a true policy/design decision is needed, mark `HUMAN DECISION REQUIRED` rather than inventing a choice.

Do not use synthetic placeholders as factual inputs. Do not modify numbers merely to restore a preferred recommendation.
"""


def run_antigravity(workspace: Path, comment: dict, model: str | None, timeout: str) -> int:
    prompt = build_prompt(comment)
    cmd = ["agy", "-p", prompt, "--effort", "high", "--print-timeout", timeout]
    if model:
        cmd.extend(["--model", model])

    print(f"[bridge] Launching Antigravity for GPT review comment {comment['id']}...")
    try:
        proc = subprocess.run(cmd, cwd=str(workspace), check=False)
    except FileNotFoundError:
        print("[bridge] ERROR: `agy` not found in PATH. Install/authenticate Antigravity CLI first.", file=sys.stderr)
        return 127
    print(f"[bridge] Antigravity exited with code {proc.returncode}.")
    return proc.returncode


def process_once(workspace: Path, state_path: Path, model: str | None, timeout: str) -> int:
    state = load_state(state_path)
    processed = {int(x) for x in state.get("processed_comment_ids", [])}
    comments = get_comments()
    reviews = [c for c in comments if MARKER in (c.get("body") or "") and int(c["id"]) not in processed]
    reviews.sort(key=lambda c: int(c["id"]))

    if not reviews:
        print("[bridge] No unseen GPT reviews.")
        return 0

    for comment in reviews:
        code = run_antigravity(workspace, comment, model, timeout)
        if code != 0:
            print(f"[bridge] Review {comment['id']} NOT marked processed because Antigravity failed.", file=sys.stderr)
            return code
        processed.add(int(comment["id"]))
        state["processed_comment_ids"] = sorted(processed)
        state["last_processed_url"] = comment.get("html_url")
        save_state(state_path, state)
        print(f"[bridge] Review {comment['id']} marked processed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", default=".", help="Repository workspace directory")
    parser.add_argument("--poll-seconds", type=int, default=45, help="Polling interval in watch mode")
    parser.add_argument("--once", action="store_true", help="Check once and exit")
    parser.add_argument("--model", default=None, help="Optional Antigravity model slug; omit to use configured default")
    parser.add_argument("--timeout", default="30m", help="Antigravity print timeout, e.g. 15m or 30m")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    if not (workspace / ".git").exists():
        print(f"[bridge] ERROR: {workspace} is not a Git repository workspace.", file=sys.stderr)
        return 2
    state_path = workspace / STATE_FILENAME

    while True:
        try:
            code = process_once(workspace, state_path, args.model, args.timeout)
        except Exception as exc:
            print(f"[bridge] Poll error: {exc}", file=sys.stderr)
            code = 1
        if args.once:
            return code
        time.sleep(max(15, args.poll_seconds))


if __name__ == "__main__":
    raise SystemExit(main())
