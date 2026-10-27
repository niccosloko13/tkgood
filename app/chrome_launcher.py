from __future__ import annotations

import os
import subprocess
import json
import threading
import uuid
from pathlib import Path
from typing import Optional

from .config import ROOT
from .db import log_event, get_state, set_state

CHROME_PROFILE_DIR = ROOT / "browser-profiles" / "chrome-tiktok-main"
_launch_lock = threading.Lock()


def profile_processes():
    """Read-only process inventory scoped to this exact dedicated Chrome profile."""
    if os.name != 'nt':
        raise OSError('Chrome profile inventory currently requires Windows')
    from scripts.process_runtime import hidden_kwargs
    profile=str(CHROME_PROFILE_DIR.resolve()).replace("'", "''")
    command=("Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
             "Where-Object { $_.CommandLine -and $_.CommandLine.Contains('"+profile+"') "
             "-and $_.CommandLine -notmatch '--type=' } | Select-Object -ExpandProperty ProcessId | ConvertTo-Json -Compress")
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],
                          capture_output=True,text=True,timeout=12,**hidden_kwargs())
    if result.returncode:
        raise OSError('Could not verify dedicated Chrome process; refusing duplicate launch')
    value=json.loads(result.stdout) if result.stdout.strip() else []
    return value if isinstance(value,list) else [value]


def _candidate_chrome_paths() -> list[Path]:
    candidates = []

    local = os.environ.get("LOCALAPPDATA")
    program_files = os.environ.get("PROGRAMFILES")
    program_files_x86 = os.environ.get("PROGRAMFILES(X86)")

    if local:
        candidates.append(Path(local) / "Google/Chrome/Application/chrome.exe")
    if program_files:
        candidates.append(Path(program_files) / "Google/Chrome/Application/chrome.exe")
    if program_files_x86:
        candidates.append(Path(program_files_x86) / "Google/Chrome/Application/chrome.exe")

    return candidates


def find_chrome() -> Optional[Path]:
    for p in _candidate_chrome_paths():
        if p.exists():
            return p
    return None


def open_tiktok_in_normal_chrome() -> dict:
    with _launch_lock:
        return _open_tiktok()


def _open_tiktok() -> dict:
    if get_state('browser_security_stop',{}).get('reason'):
        return {'ok':False,'message':'Browser security stop; operator review required'}
    try:
        processes=profile_processes()
    except (OSError,subprocess.TimeoutExpired) as exc:
        log_event('browser',str(exc),'ERROR')
        return {'ok':False,'message':str(exc)}
    if processes:
        set_state('browser_open_request',{'id':uuid.uuid4().hex})
        log_event('browser','Reusing persistent dedicated Chrome; Companion selects existing TikTok tab')
        return {'ok':True,'reused':True,'process_ids':processes,
                'message':'Chrome remains open; reusing the pinned TikTok tab when present.'}
    chrome = find_chrome()
    if not chrome:
        return {
            "ok": False,
            "message": "Google Chrome was not found in the standard Windows locations."
        }

    CHROME_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    args = [
        str(chrome),
        f"--user-data-dir={CHROME_PROFILE_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        "https://www.tiktok.com/",
    ]

    try:
        from pathlib import Path
        log_dir=Path(__file__).resolve().parents[1]/'.runtime/logs'
        log_dir.mkdir(parents=True,exist_ok=True)
        with (log_dir/'chrome.log').open('ab') as log:
            subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        log_event(
            "browser",
            "TikTok opened in normal Google Chrome profile (no Playwright control)."
        )
        return {
            "ok": True,
            "reused": False,
            "message": "TikTok opened in normal Chrome. Use the Product Hunter Companion extension to connect the tab."
        }
    except Exception as exc:
        log_event("browser", f"Could not open normal Chrome: {exc}", "ERROR")
        return {"ok": False, "message": f"Could not open Chrome: {exc}"}
