from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from playwright.sync_api import sync_playwright

from .config import PROFILE_DIR
from .db import get_state, init_db, log_event, set_state
from .policy import ReadOnlyPolicy

policy = ReadOnlyPolicy()

AUTH_COOKIE_NAMES = {
    "sessionid",
    "sessionid_ss",
    "sid_tt",
    "uid_tt",
    "sid_guard",
}


@dataclass
class BrowserCommand:
    name: str
    response: queue.Queue


class TikTokBrowserManager:
    def __init__(self) -> None:
        self._commands: queue.Queue[BrowserCommand] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._started = threading.Event()
        self._running = threading.Event()
        self._last_error: dict[str, Any] | None = get_state("browser_last_error", None)
        self._last_session = get_state(
            "tiktok_session",
            {
                "state": "UNKNOWN",
                "authenticated": False,
                "detail": "Session has not been checked yet.",
                "verified_at": None,
            },
        )

    def start(self) -> dict[str, Any]:
        if self.is_running():
            return {"ok": True, "message": "TikTok browser is already open."}

        self._last_error = None
        set_state("browser_last_error", {})

        self._started.clear()
        self._thread = threading.Thread(
            target=self._worker,
            name="tiktok-browser-worker",
            daemon=True,
        )
        self._thread.start()

        self._started.wait(timeout=12)
        if not self._running.is_set():
            detail = (
                self._last_error.get("message")
                if isinstance(self._last_error, dict) and self._last_error
                else "Browser did not start. Check the dashboard diagnostic."
            )
            return {"ok": False, "message": detail}

        return {
            "ok": True,
            "message": "TikTok opened. Complete authentication manually if needed.",
        }

    def is_running(self) -> bool:
        return bool(
            self._thread
            and self._thread.is_alive()
            and self._running.is_set()
        )

    def last_error(self):
        return self._last_error or None

    def session_snapshot(self) -> dict[str, Any]:
        return dict(self._last_session or {})

    def _persist_session(self, result: dict[str, Any]) -> dict[str, Any]:
        result = dict(result)
        result["verified_at"] = datetime.now(timezone.utc).isoformat()
        self._last_session = result
        set_state("tiktok_session", result)
        return result

    def check_session(self, timeout: float = 8.0) -> dict[str, Any]:
        if not self.is_running():
            result = {
                "state": "BROWSER_CLOSED",
                "authenticated": False,
                "detail": "Open TikTok first, then run a live session check.",
                "verified_at": None,
                "last_known": self.session_snapshot(),
            }
            log_event("session", result["detail"], "WARN")
            return result

        response: queue.Queue = queue.Queue(maxsize=1)
        self._commands.put(BrowserCommand("check_session", response))

        try:
            return response.get(timeout=timeout)
        except queue.Empty:
            result = {
                "state": "CHECK_TIMEOUT",
                "authenticated": False,
                "detail": "Session check timed out.",
            }
            return self._persist_session(result)

    def health_check(self, timeout: float = 12.0) -> dict[str, Any]:
        if not self.is_running():
            return {
                "ok": False,
                "state": "BROWSER_CLOSED",
                "message": "Open TikTok before running the health test.",
            }

        response: queue.Queue = queue.Queue(maxsize=1)
        self._commands.put(BrowserCommand("health_check", response))

        try:
            return response.get(timeout=timeout)
        except queue.Empty:
            return {
                "ok": False,
                "state": "TIMEOUT",
                "message": "TikTok health test timed out.",
            }

    def close(self, timeout: float = 8.0) -> dict[str, Any]:
        if not self.is_running():
            return {"ok": True, "message": "TikTok browser is already closed."}

        response: queue.Queue = queue.Queue(maxsize=1)
        self._commands.put(BrowserCommand("close", response))

        try:
            return response.get(timeout=timeout)
        except queue.Empty:
            return {"ok": False, "message": "Timed out while closing browser."}

    def _worker(self) -> None:
        decision = policy.check("open_tiktok", "https://www.tiktok.com/")
        if not decision.allowed:
            self._record_error("POLICY_DENIED", decision.reason)
            self._started.set()
            return

        try:
            log_event("browser", "Opening TikTok in persistent Chromium profile.")

            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(PROFILE_DIR),
                    headless=False,
                    viewport={"width": 1440, "height": 900},
                    args=["--start-maximized"],
                )

                page = context.pages[0] if context.pages else context.new_page()
                page.goto("https://www.tiktok.com/", wait_until="domcontentloaded")

                self._running.set()
                self._started.set()

                log_event(
                    "browser",
                    "TikTok window opened. Authentication is handled manually.",
                )

                while self._running.is_set():
                    if not context.pages:
                        break

                    try:
                        command = self._commands.get(timeout=0.35)
                    except queue.Empty:
                        continue

                    if command.name == "check_session":
                        command.response.put(self._check_live_session(context))
                    elif command.name == "health_check":
                        command.response.put(self._health_check(context))
                    elif command.name == "close":
                        try:
                            context.close()
                        except Exception:
                            pass
                        self._running.clear()
                        command.response.put(
                            {"ok": True, "message": "TikTok browser closed."}
                        )
                        break

                try:
                    context.close()
                except Exception:
                    pass

        except Exception as exc:
            self._record_error(
                type(exc).__name__,
                f"{type(exc).__name__}: {exc}",
            )
            self._started.set()

        finally:
            self._running.clear()
            log_event("browser", "TikTok Chromium session closed.")

    def _record_error(self, code: str, message: str) -> None:
        result = {
            "code": code,
            "message": message,
            "at": datetime.now(timezone.utc).isoformat(),
        }
        self._last_error = result
        set_state("browser_last_error", result)
        log_event("browser", f"Browser error: {message}", "ERROR")

    def _check_live_session(self, context) -> dict[str, Any]:
        try:
            cookies = context.cookies("https://www.tiktok.com/")
            present_names = {c.get("name", "").lower() for c in cookies}
            auth_cookie_present = bool(present_names & AUTH_COOKIE_NAMES)

            if auth_cookie_present:
                result = self._persist_session(
                    {
                        "state": "AUTHENTICATED",
                        "authenticated": True,
                        "detail": "TikTok authentication cookies detected in the live session.",
                    }
                )
                log_event("session", "TikTok live session verified: AUTHENTICATED.")
                return result

            result = self._persist_session(
                {
                    "state": "NOT_AUTHENTICATED",
                    "authenticated": False,
                    "detail": "No TikTok authentication cookie was detected.",
                }
            )
            log_event("session", "TikTok live session check: NOT_AUTHENTICATED.", "WARN")
            return result

        except Exception as exc:
            result = self._persist_session(
                {
                    "state": "CHECK_ERROR",
                    "authenticated": False,
                    "detail": f"Could not verify live session: {type(exc).__name__}.",
                }
            )
            log_event("session", result["detail"], "ERROR")
            return result

    def _health_check(self, context) -> dict[str, Any]:
        try:
            page = context.pages[0] if context.pages else context.new_page()

            # Read-only diagnostic: no social interaction and no account mutation.
            if "tiktok.com" not in page.url:
                page.goto("https://www.tiktok.com/", wait_until="domcontentloaded")

            title = page.title()
            url = page.url
            ready_state = page.evaluate("document.readyState")
            body_text = page.locator("body").inner_text(timeout=5000)[:3000]

            lower = body_text.lower()
            signals = {
                "has_search_text": ("pesquisar" in lower or "search" in lower),
                "has_tiktok_text": "tiktok" in lower,
                "has_login_text": ("entrar" in lower or "log in" in lower or "login" in lower),
                "playback_error_visible": (
                    "problemas para reproduzir este vídeo" in lower
                    or "problem playing this video" in lower
                ),
            }

            page_ok = (
                "tiktok.com" in url
                and ready_state in {"interactive", "complete"}
                and (signals["has_tiktok_text"] or signals["has_search_text"])
            )

            result = {
                "ok": bool(page_ok),
                "state": "HEALTHY" if page_ok else "DEGRADED",
                "title": title,
                "url": url,
                "ready_state": ready_state,
                "signals": signals,
                "message": (
                    "TikTok page is responding and readable."
                    if page_ok
                    else "TikTok loaded, but expected page signals were not confirmed."
                ),
            }

            if signals["playback_error_visible"]:
                result["state"] = "DEGRADED"
                result["message"] = (
                    "TikTok is readable, but a video playback error is visible on the page."
                )

            set_state("tiktok_health", result)
            log_event(
                "health",
                f"TikTok health test: {result['state']} · {result['message']}",
                "INFO" if result["state"] == "HEALTHY" else "WARN",
            )
            return result

        except Exception as exc:
            result = {
                "ok": False,
                "state": "ERROR",
                "message": f"TikTok health test failed: {type(exc).__name__}: {exc}",
            }
            set_state("tiktok_health", result)
            log_event("health", result["message"], "ERROR")
            return result


def profile_has_state() -> bool:
    if not PROFILE_DIR.exists():
        return False

    meaningful = [
        p for p in PROFILE_DIR.rglob("*")
        if p.is_file() and p.stat().st_size > 0
    ]
    return len(meaningful) > 5


# Ensure DB schema/migrations exist before BrowserManager reads persisted state.
init_db()
browser_manager = TikTokBrowserManager()
