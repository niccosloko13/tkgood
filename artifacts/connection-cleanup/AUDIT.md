# Connection Cleanup Audit

## Scope and checkpoint

This audit was taken before the cleanup changes. The existing project worktree was
already dirty; no pre-existing file was removed or reset. Checkpoint files in this
directory record the status and diff-stat at the start of the sprint.

## Current operational chain

`Dashboard -> local backend -> bridge_commands -> Companion extension -> content script -> TikTok tab`

The real Chrome tab remains authoritative. The dashboard has no direct page-control
path; its actions use the backend command/recovery APIs.

## Components and classification

| Item | Classification | Finding |
| --- | --- | --- |
| `app/main.py:live_bridge` | KEEP | Canonical freshness/bridge adapter; combines persisted heartbeat and latch state. |
| `app/session_api.py` | MERGE | Existing small, read-only session endpoint is the correct place for a UI read model. |
| `app/db.py:bridge_commands` | KEEP | Canonical persisted command queue; deduplicates matching PENDING/DISPATCHED commands. |
| `app/db.py:claim_command/finish_command` | KEEP | The sole dispatch/result transition path. |
| `app/browser_safety.py` | KEEP | Global security latch and historical stop mechanism. |
| `app/target_safety.py` | KEEP | Target-level quarantine; distinct from global latch. |
| `app/safe_collection.py` | KEEP | Bounded search-only/recovery guard. |
| `app/manual_captcha_recovery.py` | KEEP | Explicit, audited human recovery only. |
| Legacy connection facts / heartbeat/event blocks in `index.html` | MOVE_TO_DIAGNOSTICS | Useful to support and tests, too technical for normal operation. |
| Companion label in normal UI | DEPRECATE | Retain only in advanced diagnostics; use “Navegador” in user-facing state. |
| Technical mini-log | MOVE_TO_DIAGNOSTICS | Preserve bounded log, hide by default. |
| Recovery/latch controls | KEEP_INTERNAL | No automatic release and no normal-user reset control are introduced. |

## Overlap review

* **Connection:** `live_bridge()` supplies internal facts; the new session read model
  translates those facts for UI. This is an adapter, not a second detector.
* **Session/page health:** heartbeat payload and `live_bridge()` remain the source;
  UI no longer independently infers user-facing status.
* **Safety:** `browser_safety`, `target_safety`, and `safe_collection` have separate
  responsibilities (global latch, per-target quarantine, bounded collection). No
  merge is safe or needed in this sprint.
* **Commands:** `bridge_commands` already has command id, type, timestamps, status,
  detail/result hash and duplicate suppression. No parallel queue was found.

## Removal risk

No module meets the required deletion criteria. In particular, the technical UI
nodes are referenced by current regression tests and serve support diagnostics.
They are therefore moved/hidden from the normal flow, not deleted.
