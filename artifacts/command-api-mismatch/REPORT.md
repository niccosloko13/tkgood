# Extension/backend command API mismatch

## Root cause, verified before changes

The canonical route **GET /api/dev/commands/next** was present in `app.main.app.routes`
and its router was registered. It was neither removed nor renamed. The extension
caller was correct: `extension/dev_worker.js` calls `api('/commands/next')`, whose
base is `http://127.0.0.1:8000/api/dev`. `background.js` invokes this worker from its
heartbeat tick, normally every three seconds plus browser/content events.

The failure was startup-mode mismatch. Old `run.py` started Uvicorn without setting
PH_DEV_CONTROL=1. `app/dev_control.py:settings()` then deliberately returned HTTP
404, detail **Development control is disabled**, although heartbeat remained a
working public route. A provisioned Companion kept polling that disabled API.
This condition was reproduced locally; route inventory is in `routes-before.json`.
KeyboardInterrupt from a manual stop was not treated as the root bug.

## Fix

- `run.py` direct startup now uses the existing authenticated, owned supervisor
  path, which provisions control/config/build and starts the serving child with
  PH_DEV_CONTROL=1. No second application mode or command endpoint was created.
- The canonical queue URL is unchanged on both sides. Auth token, extension ID,
  loopback/origin restrictions and disabled-mode protection remain.
- Shared contract: api_version **1**, companion_min_version **0.1.6**. Companion
  **0.1.6** sends API version, companion version and build. Contract participates
  in build hashing.
- Heartbeat advertises API version and command-control availability. Incompatible
  or disabled backends suspend worker polling; an unexpected 404 is not retried on
  every tick with an unchanged backend contract. Incompatible command consumption
  is also suspended. Dashboard shows COMPANION DESATUALIZADO explicitly.
- Direct duplicate startup prints **Babi já está rodando em
  http://127.0.0.1:8000** and exits without traceback or another process. A foreign
  listener is reported with owner PID/process when available; none is killed.

## Reload and live API validation

The existing Dev Control reload succeeded. Final loaded Companion:

- Version: **0.1.6**.
- Build: **62545a4cb7c97ac2**.
- API: **1**, compatible: **true**.

In the current supervisor-run log segment at verification:

- **140 POST /api/bridge/heartbeat → 200**.
- **137 GET /api/dev/commands/next → 200**.
- **0 GET /api/dev/commands/next → 404**.

Samples and exact state are in `verification.json`. This includes real extension
polling, not only a manually probed endpoint. Loaded build matches the generated
build after the final worker-only reload. That reload reported zero TikTok tab
refreshes under the active latch; it did not retry the failed home.

## Session UI and actual session result

ABRIR TIKTOK, RENOVAR SESSÃO and VERIFICAR SESSÃO are available on Conexão.
Renewal uses the existing maintenance queue, not a parallel browser API. Verify
uses the existing passive check and never clears the latch. No control changes
cookies/login or performs engagement.

One explicit renewal was executed:
`ee38c83a1f7ec08e278953ab55be1e0d`. It created one home tab in the running Companion
browser. No other Chrome/profile was launched. A transient empty-URL/loading-tab
race initially reported **Renewal tab changed**; ordering was corrected and covered
with a regression test. New security incidents during that wait now fail renewal
explicitly rather than reporting success.

The actual home produced a **new HTTP 403** at
**2026-10-24T15:19:37.832Z**. It was persisted and the old incident archived. No
second renewal, home navigation, refresh, retry or bypass was attempted. A healthy
renewal after this fix is proven with local worker fixtures, not claimed as a
successful authenticated live TikTok session.

State after the final worker-only reload:

- Companion connected and compatible; Chrome connected.
- No TikTok tab detected in the current Companion tab inventory; current URL empty.
  Earlier, the single attempted home was reported at https://www.tiktok.com/.
- Session unconfirmed; passive verification **UNKNOWN** because no document can
  currently be confirmed. This does not negate the separately recorded HTTP 403.
- Security stop active for that new HTTP 403; previous incident/history preserved.

The command API is fixed. The external TikTok session is **not recovered/healthy**.
No unlatch was performed.

## No collection / preservation

Production checkpoint: `checkpoint.db`. Verification compares all existing domain
tables; only expected events, heartbeat/system state, dev commands and passive
check audit records changed. Gold, candidates, reviews, Identity, taxonomy,
category evidence, assets, embeddings/index and temporal observations are unchanged.

- New content/collection commands: **0**.
- New search observations: **0**.
- New trend snapshots: **0**.
- Engagement: **0**.
- No commit.

Original incident is still in history. The current incident remains active. The
presence of a heartbeat/compatible extension never cleared it.

## Tests

- **464 Python passed**, seven existing deprecation warnings, zero failures.
  Task `43fe00b60dd84ca8825e558583e82769`.
- **135 Node/dashboard passed**, zero failures/skips.
  Task `18aed653a3e5423f911ab7b5e4ff4d02`.
- Tests cover canonical routing/negotiation, outdated UI, no continuous 404 polling,
  duplicate/foreign-listener startup, existing queue renewal, single-home creation,
  loading-tab timing, current/new block detection, no retry or unlatch, and passive
  verification. Existing suites were retained.

## Files

`run.py`, `config/companion_api.json`, `app/companion_contract.py`,
`app/session_api.py`, `app/main.py`, `app/dev_control.py`, `app/schemas.py`,
`scripts/dev_supervisor.py`, `extension/manifest.json`, `extension/background.js`,
`extension/dev_worker.js`, existing dashboard HTML, related tests and
`docs/DEV_CONTROL.md`. Generated build/config files remain local.

## Manual action

Inspect the TikTok home/block manually in the Chrome with Companion; automatic
session recovery/navigation remains stopped after the new 403. No manual command
line operation is required from the user.
