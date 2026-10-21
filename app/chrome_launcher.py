from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

from .config import ROOT
from .db import log_event

CHROME_PROFILE_DIR = ROOT / "browser-profiles" / "chrome-tiktok-main"


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
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log_event(
            "browser",
            "TikTok opened in normal Google Chrome profile (no Playwright control)."
        )
        return {
            "ok": True,
            "message": "TikTok opened in normal Chrome. Use the Product Hunter Companion extension to connect the tab."
        }
    except Exception as exc:
        log_event("browser", f"Could not open normal Chrome: {exc}", "ERROR")
        return {"ok": False, "message": f"Could not open Chrome: {exc}"}
