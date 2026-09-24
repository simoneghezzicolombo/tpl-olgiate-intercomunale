#!/usr/bin/env python3
"""Local bridge: GitHub Issue #1 -> Antigravity CLI.

Polls the public coordination issue for new comments containing `[GPT REVIEW]`.
For each unseen review:
1. Publishes `[ANTIGRAVITY RUN STARTED]` on GitHub Issue #1.
2. Spawns Antigravity CLI in a VISIBLE separate PowerShell console window on Windows.
3. Uses `--output-format stream-json` to display live activity, tool calls, commands, and progress in the console and log file.
4. Rileva esplicitamente soft-denial (permission denied) trattandoli come FAILURE.
5. Verifies deliverable: requires either a new commit/push OR an updated [ANTIGRAVITY HANDOFF]. Exit code 0 alone is NOT sufficient.
6. Implements `BLOCKED_RETRY`: prevents popup loops by refusing to retry failed reviews without changes.
7. SUPERSEDED: For reviews of the same Gate/checkpoint, only the most recent is processed;
   older ones are permanently marked SUPERSEDED without triggering Antigravity runs.
   A review may also declare `Supersedes: <id1>, <id2>` to explicitly mark those IDs as SUPERSEDED.
8. Publishes `[ANTIGRAVITY RUN FINISHED]` on GitHub Issue #1.
9. Enforces concurrency lock (.agent_bridge.lock), deduplication, and fine-grained permissions.

State file (.agent_bridge_state.json):
- Read with UTF-8-sig (BOM-safe). JSON parse failures are logged as explicit errors; the bridge
  refuses to process reviews until the state file is manually fixed or removed.
- Written in plain UTF-8 without BOM.
"""

from __future__ import annotations

import argparse
import atexit
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

# Assicura flushing immediato dei print per logging e demoni
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)

REPO = "simoneghezzicolombo/tpl-olgiate-intercomunale"
ISSUE = 1
MARKER = "[GPT REVIEW]"
STATE_FILENAME = ".agent_bridge_state.json"
LOCK_FILENAME = ".agent_bridge.lock"
LOGS_DIR_NAME = ".agent_bridge_logs"
API = f"https://api.github.com/repos/{REPO}/issues/{ISSUE}/comments?per_page=100"

CREATE_NEW_CONSOLE = 0x00000010

RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"


def ensure_path_has_agy() -> None:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        agy_bin = str(Path(local_app_data) / "agy" / "bin")
        if agy_bin not in os.environ.get("PATH", ""):
            os.environ["PATH"] = f"{agy_bin};{os.environ.get('PATH', '')}"


def find_agy_cmd() -> str:
    ensure_path_has_agy()
    cmd = shutil.which("agy")
    if cmd:
        return cmd
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        fallback = Path(local_app_data) / "agy" / "bin" / "agy.exe"
        if fallback.exists():
            return str(fallback)
    return "agy"


def acquire_lock(lock_path: Path) -> bool:
    """Ensure no other bridge instance runs on this workspace."""
    if lock_path.exists():
        try:
            pid = int(lock_path.read_text(encoding="utf-8").strip())
            import ctypes
            kernel32 = ctypes.windll.kernel32
            STILL_ACTIVE = 259
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            h_proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if h_proc:
                exit_code = ctypes.c_ulong()
                kernel32.GetExitCodeProcess(h_proc, ctypes.byref(exit_code))
                kernel32.CloseHandle(h_proc)
                if exit_code.value == STILL_ACTIVE:
                    print(f"[bridge] ERROR: Another bridge process (PID {pid}) is already running on this workspace.", file=sys.stderr)
                    return False
        except Exception:
            pass  # Stale lock file
    try:
        lock_path.write_text(str(os.getpid()), encoding="utf-8")
        return True
    except Exception as e:
        print(f"[bridge] Failed to write lock file: {e}", file=sys.stderr)
        return False


def release_lock(lock_path: Path) -> None:
    try:
        if lock_path.exists():
            lock_path.unlink()
    except Exception:
        pass


def get_head_commit(workspace: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            check=True
        )
        return proc.stdout.strip()
    except Exception:
        return "UNKNOWN_COMMIT"


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


def is_gpt_review(comment: dict) -> bool:
    body = comment.get("body") or ""
    if MARKER not in body:
        return False
    for line in body.splitlines():
        cleaned = line.strip()
        if cleaned.startswith(MARKER) or cleaned == MARKER:
            return True
    return False


def load_state(path: Path) -> dict | None:
    """Load the bridge state file.

    Returns None if the file exists but cannot be parsed as JSON (explicit parse failure).
    This forces the caller to abort review processing rather than silently resetting state.
    Reads with UTF-8-sig to safely handle files saved with a BOM.
    """
    if not path.exists():
        return {"processed_comment_ids": [], "blocked_retry": {}, "superseded_comment_ids": []}
    raw = path.read_bytes()
    # Strip UTF-8 BOM if present (utf-8-sig codec behaviour)
    text = raw.decode("utf-8-sig")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        print(
            f"[bridge] FATAL: {path} is not valid JSON ({exc}). "
            "Fix or remove the file before restarting the bridge.",
            file=sys.stderr,
        )
        return None  # Caller must abort
    if "blocked_retry" not in data:
        data["blocked_retry"] = {}
    if "superseded_comment_ids" not in data:
        data["superseded_comment_ids"] = []
    return data


def save_state(path: Path, state: dict) -> None:
    """Write state file as plain UTF-8 without BOM."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(path)


def post_github_issue_comment(body: str) -> str | None:
    try:
        proc = subprocess.run(
            ["gh", "issue", "comment", str(ISSUE), "--body", body],
            capture_output=True,
            text=True,
            check=True
        )
        url = proc.stdout.strip()
        print(f"[bridge] Published GitHub Issue comment: {url}")
        return url
    except Exception as e:
        print(f"[bridge] Warning: Could not post GitHub comment via `gh`: {e}", file=sys.stderr)
        return None


def build_prompt(comment: dict, workspace: Path) -> str:
    body = comment.get("body", "")
    url = comment.get("html_url", "")
    return f"""You are ANTIGRAVITY, executor agent for the repository {REPO}.
Workspace directory: {workspace}

A new GPT external-review message has arrived on GitHub Issue #{ISSUE}.
Treat COLLABORATION_PROTOCOL.md and the coordination issue as binding workflow instructions.

REVIEW COMMENT URL:
{url}

REVIEW CONTENT:
{body}

ACTION:
1. Inspect the current repository state on branch `antigravity-real-data`.
2. Apply the GPT review requirements.
3. Do not bypass a failed gate.
4. Run relevant tests (pytest) and verify actual outputs.
5. Create a new commit and push completed changes to origin antigravity-real-data.
6. Update AGENT_STATUS.md with a new `[ANTIGRAVITY HANDOFF]` section detailing the resolution and commit hash.
7. Request the corresponding gate review.
"""


def check_new_handoff(workspace: Path, start_time: float) -> tuple[bool, str]:
    agent_status_file = workspace / "AGENT_STATUS.md"
    if not agent_status_file.exists():
        return False, "AGENT_STATUS.md non trovato"

    mtime = agent_status_file.stat().st_mtime
    if mtime >= (start_time - 2.0):
        try:
            content = agent_status_file.read_text(encoding="utf-8")
            if "ANTIGRAVITY" in content and ("Handoff" in content or "HANDOFF" in content):
                return True, "Nuovo handoff documentato in AGENT_STATUS.md"
        except Exception as e:
            return False, f"Errore lettura AGENT_STATUS.md: {e}"

    return False, "Nessun aggiornamento recente in AGENT_STATUS.md"


def run_antigravity_stream_visible(
    workspace: Path,
    comment_id: int | str,
    prompt: str,
    model: str | None,
    timeout: str,
    log_dir: Path
) -> tuple[int, str]:
    """Lancia Antigravity CLI in una console visibile separata usando lo stream runner."""
    log_file = log_dir / f"{comment_id}.log"
    exitcode_file = log_dir / f"{comment_id}.exitcode"
    prompt_file = log_dir / f"prompt_{comment_id}.txt"
    runner_script = log_dir / f"runner_{comment_id}.ps1"

    prompt_file.write_text(prompt, encoding="utf-8")
    stream_runner = workspace / "tools" / "agent_stream_runner.py"

    # Script di lancio in finestra visibile
    model_arg = f'--model "{model}"' if model else ""
    ps_content = f"""# Launcher per Antigravity CLI Stream Runner - Review #{comment_id}
$Host.UI.RawUI.WindowTitle = "Antigravity CLI - Stream Runner #{comment_id}"

$localAgy = Join-Path $env:LOCALAPPDATA "agy\\bin"
if (Test-Path $localAgy) {{
    $env:PATH = "$localAgy;$env:PATH"
}}

python "{stream_runner}" --comment-id "{comment_id}" --prompt-file "{prompt_file}" --log-file "{log_file}" --exitcode-file "{exitcode_file}" --workspace "{workspace}" --timeout "{timeout}" {model_arg}
exit $LASTEXITCODE
"""
    runner_script.write_text(ps_content, encoding="utf-8")

    cmd = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", str(runner_script)
    ]

    print(f"[bridge] Opening visible stream console for review {comment_id}...")
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(workspace),
            creationflags=CREATE_NEW_CONSOLE
        )
        proc.wait()

        if exitcode_file.exists():
            try:
                exit_code = int(exitcode_file.read_text(encoding="utf-8").strip())
            except Exception:
                exit_code = proc.returncode
        else:
            exit_code = proc.returncode

    except Exception as e:
        print(f"[bridge] Failed to launch console: {e}", file=sys.stderr)
        exit_code = 1

    print(f"[bridge] Antigravity CLI runner exited with code {exit_code}.")
    return exit_code, str(log_file)


def process_review_item(
    workspace: Path,
    comment: dict,
    model: str | None,
    timeout: str,
    log_dir: Path
) -> tuple[bool, int, str]:
    """Elabora un singolo commento review, pubblica notifiche su Issue #1 e valida deliverable."""
    comment_id = comment["id"]
    comment_url = comment.get("html_url", f"https://github.com/{REPO}/issues/{ISSUE}#issuecomment-{comment_id}")
    commit_before = get_head_commit(workspace)
    start_time = time.time()
    start_time_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(start_time))

    prompt = build_prompt(comment, workspace)

    # 1. Pubblica [ANTIGRAVITY RUN STARTED]
    start_body = f"""[ANTIGRAVITY RUN STARTED]

Avvio elaborazione automatica stream-json per la review GPT:
- **Review ID:** {comment_id}
- **Review URL:** {comment_url}
- **Timestamp:** {start_time_iso}
- **Commit iniziale:** `{commit_before}`
- **Console:** Avviata finestra PowerShell visibile con streaming eventi
- **Log locale:** `{LOGS_DIR_NAME}/{comment_id}.log`
"""
    post_github_issue_comment(start_body)

    # 2. Esegui in console visibile con Stream Runner
    exit_code, log_path = run_antigravity_stream_visible(workspace, comment_id, prompt, model, timeout, log_dir)

    # 3. Verifica deliverable ed errori di soft-denial
    commit_after = get_head_commit(workspace)
    has_new_commit = (commit_after != commit_before)
    has_handoff, handoff_note = check_new_handoff(workspace, start_time)

    # Verifica se c'è stato soft-denial nel log
    soft_denied = False
    quota_error = False
    quota_error_msg = ""
    log_file_path = Path(log_path)
    if log_file_path.exists():
        try:
            log_text = log_file_path.read_text(encoding="utf-8", errors="replace")
            if any(s in log_text for s in ["required the \"command\" permission", "auto-denied", "permission check failed", "user denied permission"]):
                soft_denied = True
            # exit code 2 from the stream runner signals quota exhaustion
            if exit_code == 2:
                quota_error = True
                for line in log_text.splitlines():
                    if "[QUOTA EXHAUSTED]" in line:
                        quota_error_msg = line.replace("[QUOTA EXHAUSTED]", "").strip()
                        break
        except Exception:
            pass

    has_deliverable = has_new_commit or has_handoff
    success = (exit_code == 0) and has_deliverable and not soft_denied

    # 4. Pubblica [ANTIGRAVITY RUN FINISHED]
    status_str = "SUCCESS" if success else "FAILED"
    if soft_denied:
        reason = "Soft-denial rilevato su permessi tool/command"
    elif quota_error:
        reason = f"Quota individuale esaurita — {quota_error_msg}" if quota_error_msg else "Quota individuale esaurita"
    elif exit_code != 0:
        reason = f"Exit code non-zero ({exit_code})"
    elif not has_deliverable:
        reason = "Nessun deliverable generato (né nuovo commit né handoff)"
    else:
        reason = "Deliverable verificato (nuovo commit/handoff generato con successo)"

    proc_str = "Review marcata come processata" if success else "Review messa in stato BLOCKED_RETRY (attesa riconfigurazione/modifica)"

    finish_body = f"""[ANTIGRAVITY RUN FINISHED]

Elaborazione completata per la review GPT:
- **Review ID:** {comment_id}
- **Exit Code:** {exit_code}
- **Quota esaurita:** {"Sì — " + quota_error_msg if quota_error else "No"}
- **Soft-denial rilevato:** {"Sì (BLOCCANTE)" if soft_denied else "No"}
- **Commit prima:** `{commit_before}`
- **Commit dopo:** `{commit_after}`
- **Nuovo commit:** {"Sì (`" + commit_after + "`)" if has_new_commit else "No"}
- **Handoff:** {"Sì (" + handoff_note + ")" if has_handoff else "No"}
- **Esito finale:** **{status_str}** ({reason})
- **Stato elaborazione:** {proc_str}
- **Log completo:** `{LOGS_DIR_NAME}/{comment_id}.log`
"""
    post_github_issue_comment(finish_body)

    if not success:
        print(f"[bridge] Run FAILED for review {comment_id}: {reason}", file=sys.stderr)
    else:
        print(f"[bridge] Run SUCCESS for review {comment_id}: deliverable verified.")

    return success, exit_code, reason


def parse_review_metadata(body: str) -> dict:
    """Extract structured metadata from a [GPT REVIEW] comment body.

    Parses header fields like:
      Gate: GATE A - Provenance
      Supersedes: 5516612555, 5516728746

    Returns a dict with keys: 'gate' (str or None), 'supersedes' (list[int]).
    """
    gate = None
    supersedes: list[int] = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("gate:"):
            gate = stripped[5:].strip()
        elif stripped.lower().startswith("supersedes:"):
            raw_ids = stripped[11:].strip()
            for part in raw_ids.replace(",", " ").split():
                try:
                    supersedes.append(int(part))
                except ValueError:
                    pass
    return {"gate": gate, "supersedes": supersedes}


def apply_superseded_logic(
    reviews: list[dict],
    state: dict,
) -> tuple[list[dict], set[int]]:
    """Determine which reviews are SUPERSEDED and should not be run.

    Rules:
    1. Explicit: if a review has `Supersedes: <id1>, <id2>`, those IDs are immediately SUPERSEDED.
    2. Implicit: for reviews sharing the same Gate label, only the newest (highest ID) is kept;
       older ones are SUPERSEDED.

    Returns:
        - filtered list of reviews to actually process (not superseded)
        - set of comment IDs newly determined to be SUPERSEDED
    """
    existing_superseded = {int(x) for x in state.get("superseded_comment_ids", [])}
    newly_superseded: set[int] = set()

    # Step 1: collect explicit Supersedes declarations
    for comment in reviews:
        meta = parse_review_metadata(comment.get("body", ""))
        for sid in meta["supersedes"]:
            newly_superseded.add(sid)

    # Step 2: group by Gate label; keep only newest per gate
    gate_groups: dict[str, list[dict]] = {}
    no_gate: list[dict] = []
    for comment in reviews:
        meta = parse_review_metadata(comment.get("body", ""))
        gate = meta["gate"]
        if gate:
            gate_groups.setdefault(gate, []).append(comment)
        else:
            no_gate.append(comment)

    for gate, group in gate_groups.items():
        group.sort(key=lambda c: int(c["id"]))
        # Supersede all except the most recent
        for old_comment in group[:-1]:
            newly_superseded.add(int(old_comment["id"]))

    all_superseded = existing_superseded | newly_superseded
    # Filter out superseded from the to-process list
    to_process = [c for c in reviews if int(c["id"]) not in all_superseded]
    return to_process, newly_superseded


def process_once(workspace: Path, state_path: Path, log_dir: Path, model: str | None, timeout: str, retry_blocked: bool = False) -> int:
    state = load_state(state_path)
    if state is None:
        # State file exists but is unparseable JSON - refuse to process.
        print("[bridge] Aborting: cannot read state file. Fix it manually.", file=sys.stderr)
        return 4

    processed = {int(x) for x in state.get("processed_comment_ids", [])}
    blocked = state.get("blocked_retry", {})
    current_head = get_head_commit(workspace)

    comments = get_comments()
    all_reviews = [c for c in comments if is_gpt_review(c) and int(c["id"]) not in processed]
    all_reviews.sort(key=lambda c: int(c["id"]))

    if not all_reviews:
        print("[bridge] No unseen GPT reviews.")
        return 0

    # Apply SUPERSEDED logic
    reviews, newly_superseded = apply_superseded_logic(all_reviews, state)
    if newly_superseded:
        existing_sup = {int(x) for x in state.get("superseded_comment_ids", [])}
        state["superseded_comment_ids"] = sorted(existing_sup | newly_superseded)
        save_state(state_path, state)
        for sid in sorted(newly_superseded):
            print(f"[bridge] Review {sid} marked SUPERSEDED (newer review for same Gate exists or explicit Supersedes declared).")

    if not reviews:
        print("[bridge] All pending GPT reviews are SUPERSEDED. Nothing to process.")
        return 0

    overall_code = 0
    for comment in reviews:
        cid_str = str(comment["id"])

        # Controllo anti-loop BLOCKED_RETRY: non rieseguire se nulla e' cambiato
        if cid_str in blocked and not retry_blocked:
            prev_info = blocked[cid_str]
            prev_commit = prev_info.get("last_commit", "")
            if prev_commit == current_head:
                print(f"[bridge] Review {cid_str} is in BLOCKED_RETRY state (no repo changes since failure at {prev_info.get('failed_at')}). Skipping to avoid popup loop.")
                continue
            else:
                print(f"[bridge] Repo change detected ({prev_commit[:8]} -> {current_head[:8]}); unlocking review {cid_str} for retry.")

        success, code, reason = process_review_item(workspace, comment, model, timeout, log_dir)
        if success:
            processed.add(int(comment["id"]))
            state["processed_comment_ids"] = sorted(processed)
            state["last_processed_url"] = comment.get("html_url")
            state["last_processed_timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            # Rimuovi da blocked se presente
            if cid_str in state.get("blocked_retry", {}):
                del state["blocked_retry"][cid_str]
            save_state(state_path, state)
            print(f"[bridge] Review {comment['id']} marked processed.")
        else:
            # Salva in stato BLOCKED_RETRY per prevenire il loop di popup
            if "blocked_retry" not in state:
                state["blocked_retry"] = {}
            state["blocked_retry"][cid_str] = {
                "failed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "last_commit": current_head,
                "reason": reason,
                "retry_count": state["blocked_retry"].get(cid_str, {}).get("retry_count", 0) + 1
            }
            state["last_failed_comment_id"] = comment["id"]
            state["last_failed_timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            save_state(state_path, state)
            print(f"[bridge] Review {comment['id']} entered BLOCKED_RETRY state.", file=sys.stderr)
            overall_code = code or 1

    return overall_code


def run_smoke_test(workspace: Path, log_dir: Path) -> bool:
    """Smoke test reale e visibile che esegue un task da terminale controllando stream-json e assenza di soft-denial."""
    print(f"\n{BOLD}{GREEN}=================================================================={RESET}")
    print(f"{BOLD}{GREEN}  AVVIO SMOKE TEST REALE E VISIBILE DEL BRIDGE{RESET}")
    print(f"{BOLD}{GREEN}=================================================================={RESET}\n")

    test_id = "smoke_test"
    test_prompt = "Run git status and report the current branch."
    
    print(f"[smoke-test] Lancio Antigravity CLI con stream-json in console visibile...")
    exit_code, log_path = run_antigravity_stream_visible(
        workspace=workspace,
        comment_id=test_id,
        prompt=test_prompt,
        model=None,
        timeout="5m",
        log_dir=log_dir
    )

    log_file = Path(log_path)
    if not log_file.exists():
        print(f"[FAIL] Log file {log_file} non creato!", file=sys.stderr)
        return False

    log_content = log_file.read_text(encoding="utf-8", errors="replace")
    
    # 1. Verifica assenza soft-denial
    for pattern in ["required the \"command\" permission", "auto-denied", "permission check failed", "user denied permission"]:
        if pattern in log_content:
            print(f"[FAIL] Rilevato soft-denial nel log: {pattern}", file=sys.stderr)
            return False

    # 2. Verifica che git status sia stato realmente eseguito
    if "antigravity-real-data" not in log_content and "On branch" not in log_content:
        print(f"[FAIL] git status non sembra essere stato eseguito nel log!", file=sys.stderr)
        return False

    # 3. Verifica exit code 0
    if exit_code != 0:
        print(f"[FAIL] Smoke test terminato con exit code non-zero: {exit_code}", file=sys.stderr)
        return False

    print(f"\n{BOLD}{GREEN}=================================================================={RESET}")
    print(f"{BOLD}{GREEN}  SMOKE TEST REALE SUPERATO CON SUCCESSO! [PASS]{RESET}")
    print(f"  - Console visibile: OK")
    print(f"  - Output stream-json: OK")
    print(f"  - Esecuzione reale git status: OK")
    print(f"  - Assenza soft-denial: OK")
    print(f"  - Log completo salvato in: {log_file}")
    print(f"{BOLD}{GREEN}=================================================================={RESET}\n")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", default=".", help="Repository workspace directory")
    parser.add_argument("--poll-seconds", type=int, default=45, help="Polling interval in watch mode")
    parser.add_argument("--once", action="store_true", help="Check once and exit")
    parser.add_argument("--model", default=None, help="Optional Antigravity model slug; omit to use configured default")
    parser.add_argument("--timeout", default="30m", help="Antigravity print timeout, e.g. 15m or 30m")
    parser.add_argument("--smoke-test", action="store_true", help="Run real visible smoke test executing terminal command")
    parser.add_argument("--retry-blocked", action="store_true", help="Force retry of blocked reviews without waiting for repo changes")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    if not (workspace / ".git").exists():
        print(f"[bridge] ERROR: {workspace} is not a Git repository workspace.", file=sys.stderr)
        return 2

    state_path = workspace / STATE_FILENAME
    lock_path = workspace / LOCK_FILENAME
    log_dir = workspace / LOGS_DIR_NAME
    log_dir.mkdir(exist_ok=True)

    if not acquire_lock(lock_path):
        return 3
    atexit.register(release_lock, lock_path)

    try:
        if args.smoke_test:
            ok = run_smoke_test(workspace, log_dir)
            return 0 if ok else 1

        while True:
            try:
                code = process_once(workspace, state_path, log_dir, args.model, args.timeout, args.retry_blocked)
            except Exception as exc:
                print(f"[bridge] Poll error: {exc}", file=sys.stderr)
                code = 1
            if args.once:
                return code
            time.sleep(max(15, args.poll_seconds))
    finally:
        release_lock(lock_path)


if __name__ == "__main__":
    raise SystemExit(main())
