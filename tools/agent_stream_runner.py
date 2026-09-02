#!/usr/bin/env python3
"""Antigravity CLI Stream Runner with real-time observable console events.

Runs Antigravity CLI with `--output-format stream-json`, formats tool calls,
commands, progress, test executions, and agent text live in the visible console,
detects soft-denials, and writes the complete structured log to file.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# ANSI colors for visible console
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"
MAGENTA = "\033[35m"
GRAY = "\033[90m"

SOFT_DENIAL_PATTERNS = [
    'required the "command" permission that headless mode cannot prompt for',
    "auto-denied",
    "headless mode cannot prompt",
    "permission check failed",
    "user denied permission to run command",
]


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


def format_tool_args(name: str, params: dict) -> str:
    if not params:
        return ""
    if name == "run_command":
        cmd = params.get("CommandLine", "")
        return f"\n      {BOLD}> {cmd}{RESET}"
    if name in ("view_file", "write_to_file", "replace_file_content", "multi_replace_file_content"):
        path = params.get("AbsolutePath") or params.get("TargetFile") or ""
        return f" [{Path(path).name}]"
    if name in ("grep_search", "search_web"):
        query = params.get("Query") or params.get("query") or ""
        return f" \"{query}\""
    if name == "list_dir":
        path = params.get("DirectoryPath") or ""
        return f" [{Path(path).name}]"
    return ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comment-id", required=True)
    parser.add_argument("--prompt-file", required=True)
    parser.add_argument("--log-file", required=True)
    parser.add_argument("--exitcode-file", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--timeout", default="30m")
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    log_file = Path(args.log_file).resolve()
    exitcode_file = Path(args.exitcode_file).resolve()
    prompt_file = Path(args.prompt_file).resolve()

    prompt = prompt_file.read_text(encoding="utf-8")
    agy_bin = find_agy_cmd()

    print(f"{BOLD}{GREEN}=================================================================={RESET}")
    print(f"{BOLD}{GREEN} [ANTIGRAVITY CLI] Elaborazione Review #{args.comment_id}{RESET}")
    print(f"{CYAN} Workspace:{RESET} {workspace}")
    print(f"{CYAN} Log file: {RESET} {log_file}")
    print(f"{CYAN} Modalita: {RESET} stream-json observable execution")
    print(f"{BOLD}{GREEN}=================================================================={RESET}\n")

    cmd = [
        agy_bin,
        "-p", prompt,
        "--add-dir", str(workspace),
        "--output-format", "stream-json",
        "--effort", "high",
        "--print-timeout", args.timeout,
    ]
    if args.model:
        cmd.extend(["--model", args.model])

    ensure_path_has_agy()
    log_f = log_file.open("w", encoding="utf-8")

    soft_denial_detected = False
    soft_denial_reason = ""
    start_time = time.time()

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(workspace),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        for raw_line in proc.stdout:
            line = raw_line.strip()
            log_f.write(raw_line)
            log_f.flush()

            if not line:
                continue

            # Check for soft-denial signatures
            for pattern in SOFT_DENIAL_PATTERNS:
                if pattern in line:
                    soft_denial_detected = True
                    soft_denial_reason = line
                    print(f"\n{BOLD}{RED}[SOFT-DENIAL DETECTED] {line}{RESET}")

            # Try parsing as stream-json event
            if line.startswith("{") and line.endswith("}"):
                try:
                    event_data = json.loads(line)
                    event_type = event_data.get("event")

                    if event_type == "init":
                        init_info = event_data.get("init", {})
                        mode = init_info.get("permission_mode", "unknown")
                        tools = init_info.get("tools", [])
                        print(f"{GRAY}[INIT] Sessione avviata (mode: {mode}, {len(tools)} tools registrati){RESET}")

                    elif event_type == "step_update":
                        step = event_data.get("step_update", {})
                        step_type = step.get("step_type")
                        state = step.get("state")

                        if step_type == "tool":
                            tool_name = step.get("tool_name", "tool")
                            tool_info = step.get("tool_info", {})
                            params = tool_info.get("parameters", {})

                            if state == "ACTIVE":
                                extra = format_tool_args(tool_name, params)
                                print(f"{YELLOW}-> [{tool_name}]{RESET}{extra}")

                            elif state == "DONE":
                                dur = step.get("duration_seconds", 0.0)
                                print(f"{GREEN}   V [{tool_name}] completato in {dur:.2f}s{RESET}")

                            elif state == "ERROR":
                                err = tool_info.get("error", {}).get("message", "Tool error")
                                print(f"{RED}   X [{tool_name}] ERRORE: {err}{RESET}")
                                if any(p in err for p in SOFT_DENIAL_PATTERNS):
                                    soft_denial_detected = True
                                    soft_denial_reason = err

                        elif step_type == "agent_response":
                            delta = step.get("text_delta")
                            if delta:
                                sys.stdout.write(delta)
                                sys.stdout.flush()

                    elif event_type == "result":
                        res = event_data.get("result", {})
                        status = res.get("status", "UNKNOWN")
                        dur = res.get("duration_seconds", 0.0)
                        print(f"\n{BOLD}{CYAN}[RESULT] Stato finale: {status} ({dur:.1f}s){RESET}")

                except json.JSONDecodeError:
                    # Non-JSON output line, print directly
                    print(f"{GRAY}{line}{RESET}")
            else:
                # Regular output or stderr message
                print(f"{GRAY}{line}{RESET}")

        proc.wait()
        raw_exit_code = proc.returncode

    except Exception as e:
        print(f"\n{BOLD}{RED}[RUNNER ERROR] Fallimento esecuzione: {e}{RESET}")
        raw_exit_code = 1
        log_f.write(f"\n[RUNNER ERROR] {e}\n")
    finally:
        log_f.close()

    elapsed = time.time() - start_time

    # Determine final exit code: soft-denial is strictly treated as FAILURE
    if soft_denial_detected:
        final_code = 126
        status_msg = f"FALLITO (Soft-denial rilevato: {soft_denial_reason})"
    elif raw_exit_code != 0:
        final_code = raw_exit_code
        status_msg = f"FALLITO (Process exit code {raw_exit_code})"
    else:
        final_code = 0
        status_msg = "COMPLETATO CON SUCCESSO"

    exitcode_file.write_text(f"{final_code}\n", encoding="utf-8")

    print(f"\n{BOLD}{CYAN}------------------------------------------------------------------{RESET}")
    print(f" Antigravity CLI: {status_msg}")
    print(f" Exit Code: {final_code} | Durata: {elapsed:.1f}s")
    print(f" Log completo salvato in: {log_file}")
    print(f" Chiusura console automatica tra 5 secondi...")
    print(f"{BOLD}{CYAN}------------------------------------------------------------------{RESET}")
    time.sleep(5)
    return final_code


if __name__ == "__main__":
    raise SystemExit(main())
