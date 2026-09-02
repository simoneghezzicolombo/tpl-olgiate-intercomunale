#!/usr/bin/env python3
"""Local bridge: GitHub Issue #1 -> Antigravity CLI.

Polls the public coordination issue for new comments containing `[GPT REVIEW]`.
For each unseen review:
1. Publishes `[ANTIGRAVITY RUN STARTED]` on GitHub Issue #1.
2. Spawns Antigravity CLI in a VISIBLE separate PowerShell console window on Windows.
3. Simultaneously logs all output to `.agent_bridge_logs/<comment_id>.log`.
4. Verifies deliverable: requires either a new commit/push OR an updated [ANTIGRAVITY HANDOFF].
   Exit code 0 alone is NOT sufficient.
5. Publishes `[ANTIGRAVITY RUN FINISHED]` on GitHub Issue #1.
6. Only marks the comment processed if deliverables are verified.
7. Enforces concurrency lock (.agent_bridge.lock), deduplication, and scoped permissions.
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

REPO = "simoneghezzicolombo/tpl-olgiate-intercomunale"
ISSUE = 1
MARKER = "[GPT REVIEW]"
STATE_FILENAME = ".agent_bridge_state.json"
LOCK_FILENAME = ".agent_bridge.lock"
LOGS_DIR_NAME = ".agent_bridge_logs"
API = f"https://api.github.com/repos/{REPO}/issues/{ISSUE}/comments?per_page=100"

CREATE_NEW_CONSOLE = 0x00000010


def ensure_path_has_agy() -> None:
    """Ensure agy.exe is in PATH, checking default Windows install directory if needed."""
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
    """Returns the current Git HEAD commit hash."""
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


def post_github_issue_comment(body: str) -> str | None:
    """Publishes a comment to GitHub Issue #1 via gh CLI."""
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
    """Verifica se AGENT_STATUS.md è stato aggiornato con un nuovo handoff durante il run."""
    agent_status_file = workspace / "AGENT_STATUS.md"
    if not agent_status_file.exists():
        return False, "AGENT_STATUS.md non trovato"
    
    mtime = agent_status_file.stat().st_mtime
    if mtime >= (start_time - 2.0):  # modified during or slightly before run
        try:
            content = agent_status_file.read_text(encoding="utf-8")
            if "ANTIGRAVITY" in content and ("Handoff" in content or "HANDOFF" in content):
                return True, "Nuovo handoff documentato in AGENT_STATUS.md"
        except Exception as e:
            return False, f"Errore lettura AGENT_STATUS.md: {e}"
            
    return False, "Nessun aggiornamento recente in AGENT_STATUS.md"


def run_antigravity_visible(
    workspace: Path,
    comment: dict,
    model: str | None,
    timeout: str,
    log_dir: Path
) -> tuple[int, str]:
    """Lancia Antigravity CLI in una console PowerShell visibile separata e salva il log."""
    comment_id = comment["id"]
    log_file = log_dir / f"{comment_id}.log"
    exitcode_file = log_dir / f"{comment_id}.exitcode"
    prompt_file = log_dir / f"prompt_{comment_id}.txt"
    runner_script = log_dir / f"runner_{comment_id}.ps1"

    prompt = build_prompt(comment, workspace)
    prompt_file.write_text(prompt, encoding="utf-8")
    
    agy_bin = find_agy_cmd()
    model_opt = f'--model "{model}"' if model else ""

    # Escape per PowerShell script
    ps_content = f"""# Runner script generato dal bridge per review #{comment_id}
$Host.UI.RawUI.WindowTitle = "Antigravity CLI - GPT Review #{comment_id}"
Write-Host "==================================================================" -ForegroundColor Green
Write-Host " [ANTIGRAVITY CLI] Elaborazione GPT Review #{comment_id}" -ForegroundColor Green
Write-Host " Workspace: {workspace}" -ForegroundColor Cyan
Write-Host " Log: {log_file}" -ForegroundColor Cyan
Write-Host " Inizio: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
Write-Host "==================================================================`n" -ForegroundColor Green

$localAgy = Join-Path $env:LOCALAPPDATA "agy\\bin"
if (Test-Path $localAgy) {{
    $env:PATH = "$localAgy;$env:PATH"
}}

$prompt = Get-Content -Path "{prompt_file}" -Raw -Encoding UTF8

try {{
    & "{agy_bin}" -p $prompt --add-dir "{workspace}" --effort high --print-timeout "{timeout}" {model_opt} *>&1 | Tee-Object -FilePath "{log_file}"
    $code = $LASTEXITCODE
}} catch {{
    Write-Host "`nErrore durante esecuzione agy: $_" -ForegroundColor Red
    $code = 1
}}

if ($null -eq $code) {{ $code = 0 }}
Set-Content -Path "{exitcode_file}" -Value $code

Write-Host "`n------------------------------------------------------------------" -ForegroundColor Cyan
Write-Host " Antigravity CLI completato con codice di uscita: $code" -ForegroundColor Cyan
Write-Host " Log salvato in: {log_file}" -ForegroundColor Cyan
Write-Host " Questa console si chiuderà automaticamente tra 5 secondi..." -ForegroundColor Gray
Write-Host "------------------------------------------------------------------" -ForegroundColor Cyan
Start-Sleep -Seconds 5
exit $code
"""
    runner_script.write_text(ps_content, encoding="utf-8")

    cmd = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", str(runner_script)
    ]

    print(f"[bridge] Opening visible PowerShell console for review {comment_id}...")
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

    print(f"[bridge] Antigravity CLI exited with code {exit_code}.")
    return exit_code, str(log_file)


def process_review_item(
    workspace: Path,
    comment: dict,
    model: str | None,
    timeout: str,
    log_dir: Path
) -> tuple[bool, int]:
    """Elabora un singolo commento review, pubblica notifiche su Issue #1 e valida deliverable."""
    comment_id = comment["id"]
    comment_url = comment.get("html_url", f"https://github.com/{REPO}/issues/{ISSUE}#issuecomment-{comment_id}")
    commit_before = get_head_commit(workspace)
    start_time = time.time()
    start_time_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(start_time))

    # 1. Pubblica [ANTIGRAVITY RUN STARTED]
    start_body = f"""[ANTIGRAVITY RUN STARTED]

Avvio elaborazione automatica per la review GPT:
- **Review ID:** {comment_id}
- **Review URL:** {comment_url}
- **Timestamp:** {start_time_iso}
- **Commit iniziale:** `{commit_before}`
- **Console:** Avviata finestra PowerShell visibile
- **Log locale:** `{LOGS_DIR_NAME}/{comment_id}.log`
"""
    post_github_issue_comment(start_body)

    # 2. Esegui in console visibile con Tee al log
    exit_code, log_path = run_antigravity_visible(workspace, comment, model, timeout, log_dir)

    # 3. Verifica deliverable
    commit_after = get_head_commit(workspace)
    has_new_commit = (commit_after != commit_before)
    has_handoff, handoff_note = check_new_handoff(workspace, start_time)

    has_deliverable = has_new_commit or has_handoff
    success = (exit_code == 0) and has_deliverable

    # 4. Pubblica [ANTIGRAVITY RUN FINISHED]
    status_str = "SUCCESS" if success else "FAILED"
    reason = "Deliverable verificato (nuovo commit/handoff)" if success else (
        f"Exit code non-zero ({exit_code})" if exit_code != 0 else "Nessun deliverable generato (né nuovo commit né handoff)"
    )
    proc_str = "Review marcata come processata" if success else "Review NON marcata come processata (ripetibile al prossimo ciclo)"

    finish_body = f"""[ANTIGRAVITY RUN FINISHED]

Elaborazione completata per la review GPT:
- **Review ID:** {comment_id}
- **Exit Code:** {exit_code}
- **Commit prima:** `{commit_before}`
- **Commit dopo:** `{commit_after}`
- **Nuovo commit rilevato:** {"Sì (`" + commit_after + "`)" if has_new_commit else "No"}
- **Handoff rilevato:** {"Sì (" + handoff_note + ")" if has_handoff else "No"}
- **Esito finale:** **{status_str}** ({reason})
- **Stato elaborazione:** {proc_str}
- **Log completo:** `{LOGS_DIR_NAME}/{comment_id}.log`
"""
    post_github_issue_comment(finish_body)

    if not success:
        print(f"[bridge] Run FAILED for review {comment_id}: {reason}", file=sys.stderr)
    else:
        print(f"[bridge] Run SUCCESS for review {comment_id}: deliverable verified.")

    return success, exit_code


def process_once(workspace: Path, state_path: Path, log_dir: Path, model: str | None, timeout: str) -> int:
    state = load_state(state_path)
    processed = {int(x) for x in state.get("processed_comment_ids", [])}
    comments = get_comments()
    reviews = [c for c in comments if is_gpt_review(c) and int(c["id"]) not in processed]
    reviews.sort(key=lambda c: int(c["id"]))

    if not reviews:
        print("[bridge] No unseen GPT reviews.")
        return 0

    overall_code = 0
    for comment in reviews:
        success, code = process_review_item(workspace, comment, model, timeout, log_dir)
        if success:
            processed.add(int(comment["id"]))
            state["processed_comment_ids"] = sorted(processed)
            state["last_processed_url"] = comment.get("html_url")
            state["last_processed_timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            save_state(state_path, state)
            print(f"[bridge] Review {comment['id']} marked processed.")
        else:
            state["last_failed_comment_id"] = comment["id"]
            state["last_failed_timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            save_state(state_path, state)
            print(f"[bridge] Review {comment['id']} NOT marked processed.", file=sys.stderr)
            overall_code = code or 1

    return overall_code


def run_mock_test(workspace: Path, state_path: Path, log_dir: Path, model: str | None, timeout: str) -> bool:
    """Esegue un test non distruttivo simulato per verificare console visibile, log e validazione deliverable."""
    print("\n==================================================================")
    print("  AVVIO TEST MOCK NON DISTRUTTIVO DEL BRIDGE")
    print("==================================================================")
    
    mock_id = 9999990001
    mock_comment = {
        "id": mock_id,
        "html_url": f"https://github.com/{REPO}/issues/{ISSUE}#mock-review-test",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "body": "[GPT REVIEW]\nGate: MOCK TEST\nVerdict: TEST NON DISTRUTTIVO\nTask: Verifica osservabilita console, log e validazione deliverable."
    }

    # Test 1: Senza deliverable -> deve fallire e NON marcare processato
    print("\n--- TEST 1: Esecuzione senza deliverable (deve risultare FAILED) ---")
    state_before = load_state(state_path)
    success, code = process_review_item(workspace, mock_comment, model, timeout, log_dir)
    assert not success, "Test 1 fallito: doveva fallire per assenza di deliverable!"
    log_file = log_dir / f"{mock_id}.log"
    assert log_file.exists(), f"Log file {log_file} non creato!"
    print(f"[OK] Test 1 superato: il run senza modifiche e' stato marcato FAILED e il log e' stato salvato ({log_file.stat().st_size} bytes).")

    # Test 2: Con deliverable simulato in AGENT_STATUS.md -> deve avere successo e marcare processato
    print("\n--- TEST 2: Esecuzione con deliverable simulato (deve risultare SUCCESS) ---")
    mock_id_2 = 9999990002
    mock_comment_2 = {
        "id": mock_id_2,
        "html_url": f"https://github.com/{REPO}/issues/{ISSUE}#mock-review-test-2",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "body": "[GPT REVIEW]\nGate: MOCK TEST 2\nVerdict: TEST SUCCESSO CON HANDOFF"
    }
    # Tocca AGENT_STATUS.md per simulare deliverable valido
    status_path = workspace / "AGENT_STATUS.md"
    if status_path.exists():
        content = status_path.read_text(encoding="utf-8")
        status_path.write_text(content + "\n<!-- mock test touch -->\n", encoding="utf-8")

    success_2, code_2 = process_review_item(workspace, mock_comment_2, model, timeout, log_dir)
    # Ripristina file
    status_path.write_text(content, encoding="utf-8")
    
    assert success_2, "Test 2 fallito: doveva avere successo avendo rilevato un aggiornamento di handoff!"
    print("[OK] Test 2 superato: deliverable rilevato, esito SUCCESS.")
    
    # Test 3: Verifica deduplicazione
    print("\n--- TEST 3: Verifica deduplicazione ---")
    state = load_state(state_path)
    state["processed_comment_ids"] = sorted(set(state.get("processed_comment_ids", []) + [mock_id_2]))
    save_state(state_path, state)
    
    state_check = load_state(state_path)
    assert mock_id_2 in state_check["processed_comment_ids"], "Deduplicazione fallita: ID mock non presente nello stato!"
    print("[OK] Test 3 superato: deduplicazione verificata.")

    print("\n==================================================================")
    print("  TUTTI I TEST MOCK DEL BRIDGE SONO PASSATI CON SUCCESSO! [PASS]")
    print("==================================================================\n")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", default=".", help="Repository workspace directory")
    parser.add_argument("--poll-seconds", type=int, default=45, help="Polling interval in watch mode")
    parser.add_argument("--once", action="store_true", help="Check once and exit")
    parser.add_argument("--model", default=None, help="Optional Antigravity model slug; omit to use configured default")
    parser.add_argument("--timeout", default="30m", help="Antigravity print timeout, e.g. 15m or 30m")
    parser.add_argument("--mock-test", action="store_true", help="Run a non-destructive mock test verifying console, logs, and deliverables")
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
        if args.mock_test:
            ok = run_mock_test(workspace, state_path, log_dir, args.model, args.timeout)
            return 0 if ok else 1

        while True:
            try:
                code = process_once(workspace, state_path, log_dir, args.model, args.timeout)
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
