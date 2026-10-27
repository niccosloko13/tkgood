# BABI Connection Cleanup Sprint

## Result

The normal Connection screen now has one user-facing connection state:
`CONNECTED`, `ATTENTION`, `BLOCKED`, or `DISCONNECTED`. It uses a read-only
backend adapter over the existing live bridge and safety latch; it does not
detect a session independently and cannot release a latch.

## Files changed

* `app/session_api.py` — added `connection_read_model()` and included its output
  as `connection` in the existing `GET /api/session/state` response.
* `app/static/index.html` — added the compact connection summary, human status
  copy, and collapsed advanced diagnostics. Existing element IDs and actions are
  moved into the diagnostic area rather than duplicated or removed.
* `tests/test_session_panel.py` — covers the adapter's CONNECTED, ATTENTION,
  DISCONNECTED and BLOCKED mappings.
* `tests/connection-panel.test.cjs` — covers the human summary and retained
  diagnostics.

## UX decisions

* The primary view says what the operator needs to know: TikTok, session,
  browser, security, search-only mode and last communication.
* The header uses the same simple state as the Connection page.
* Technical bridge facts, session evidence, detector output, event log and
  command/heartbeat details remain available under **Diagnóstico avançado**.
* “Companion” remains an internal/diagnostic concept; normal copy says
  “Navegador”.
* The normal actions are **Reverificar conexão** and **Abrir TikTok**. The
  pre-existing renewal/refresh controls remain available under diagnostics as
  recovery actions. No reset/release-latch action was exposed.

## Safety and command contracts preserved

* `bridge_commands` remains the single persisted command queue. Its existing
  matching PENDING/DISPATCHED duplicate protection was audited and retained.
* Safety Contract, global latch, target quarantine, security history and manual
  recovery are unchanged.
* Direct Video Enrichment is not changed; search-only remains the mode reported
  by the new read model.
* No Chrome profile, session data, browser state, collection policy, endpoint or
  existing element id was removed.

## Audit and removals

See `AUDIT.md` in this directory. No modules were deleted. Technical components
were moved behind diagnostics because they remain used by support and regression
tests; they are candidates for deprecation only after later caller validation.

## Validation

* Python focused regression: `32 passed` (`test_session_panel`, command API and
  safe-collection suites), followed by the final session-panel check (`3 passed`).
  Four third-party FastAPI/websocket deprecation
  warnings only.
* JavaScript full regression: `176 passed`, `0 failed`.
* A complete Python run was initiated before an external turn interruption; its
  final exit code was not retained by the terminal. It was not represented as a
  pass. Rerun `python -m pytest -q` in a stable terminal session before treating
  the full Python suite as certified.
* Visual browser QA was not run so the Companion's Chrome/TikTok tab would not
  be altered. DOM/UI regression verifies the connection panel composition and
  preserved controls.

## Remaining limitations

* The dashboard is local static HTML, so a browser refresh is required to see
  the revised Connection UI in an already-open dashboard tab.
* The Connection endpoint intentionally still returns raw diagnostics for
  support compatibility. The normal UI does not foreground them.
