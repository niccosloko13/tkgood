# Real authenticated TikTok DOM detection

## Final result — validated on the actual existing tab

- Tab **618200484**, unchanged: `https://www.tiktok.com/`.
- Document **complete**, page **healthy**.
- Session **confirmed**.
- Profile, Messages, Activity, Avatar, authenticated sidebar and followed accounts
  all present; strong logged-out CTA absent.
- Security stop **active**, exactly unchanged from the checkpoint; history unchanged.
- UI action **waiting_for_collection_recovery**, not waiting_for_login.

This result is from the real Companion reading the user's already-open DOM, not
from a Gold label, fixture, screenshot interpretation or another browser session.
No TikTok navigation/reload, logout, cookie/login change, collection or commit.

## Exact root cause

The original profile selector already matched a visible own-account nav link.
The real document, however, uses:

- `button[data-e2e="nav-messages"]`, role=listitem, aria-label=Mensagens.
- `button[data-e2e="nav-activity"]`, role=listitem, aria-label=Atividade.

The old reader searched for `a[href="/messages"]`, message-icon or the old
`inbox-icon`. It found only a **hidden legacy inbox container** (zero width/height),
so the visible Messages control was missed. Activity was unsupported.

The old `session_evidence` array was also emitted **only when the whole confirmation
conjunction passed**. One missing inbox condition discarded positive Profile/Avatar
evidence, making the UI show NO for controls that really existed.

## Real DOM inspection

Authenticated maintenance probe **41731d1151047b4256be0672e8a937d9** succeeded with
zero refreshed tabs. It read the same tab/URL without page actions. Original audit
is in `real-dom-probe.json`; pre-change state in `before.json`.

Observed legacy selectors:

| Old selector group | Matched | Visible |
|---|---:|---:|
| nav-profile/profile-icon own profile | 1 | 1 |
| /messages or old inbox/message-icon | 1 | 0 |

The real navigation inventory contained `nav-profile`, `nav-messages`, `nav-activity`,
`nav-following`, `nav-friends`, `nav-upload` and `following-user-button` elements.
No visible PT/EN menu text is used as the authentication predicate. Aria values are
returned as diagnostics, not as the sole identity proof.

## Current detector evidence

Bounded selector diagnostics from the real DOM-v2 heartbeat:

| Signal | Matched | Visible | Structural evidence |
|---|---:|---:|---|
| profile_route_present | 1 | 1 | nav-profile anchor with own `/@...` route |
| messages_route_present | 1 | 1 | nav-messages button |
| activity_or_inbox_present | 2 | 1 | visible nav-activity; hidden legacy inbox excluded |
| account_avatar_present | 1 | 1 | image under own nav-profile control |
| following_authenticated_present | 5 | 5 | following-user-button profile anchors in a list |
| authenticated_sidebar_present | 1 | 1 | shared account/navigation ancestor |
| logged_out_cta_present | 0 | 0 | no visible strong login CTA/modal |

Selector, matched_count, visible_count, sample_href, sample_aria and sample_data_e2e
are exposed in **Log técnico do detector de sessão**, collapsed by default. Main
evidence/log views show compact signals and transitions rather than technical JSON.
Actual account hrefs remain in the local technical evidence; they are not needed
in the user-facing summary.

## Independent authentication policy

Seven requested booleans are preserved, including partial positives. For the
confirmation gate they are grouped to avoid double-counting correlated controls:

1. Account identity: own navigation profile route and/or account avatar.
2. Account communication: Messages and/or Activity/inbox.
3. Authenticated followed-account list.

The sidebar is contextual corroboration, not an extra independent vote. At least
two families, a complete healthy document and no strong logged-out CTA are required.
Profile+avatar alone or Messages+Activity alone do not confirm. Generic Following
text/route alone and ordinary feed creator links do not confirm.

The backend independently validates the structured families. The old two-token
wire form remains supported for older Companion clients; it is not allowed to
override insufficient structured evidence when the new signal map is present.

## Same-tab activation without reload

Chrome's `scripting` permission was added to the existing Companion/TikTok host
scope. It is used only for fixed packaged read-only session code, never arbitrary
scripts or generic actions. This was necessary to install the corrected detector
in the already-open authenticated document without reloading it.

The new PH_SESSION_SIGNALS observer has one guarded runtime message listener and
no timers. It reads only live DOM/session signals. No cookies, tokens, storage
credentials, hidden app authentication state or network fetch are read.

Existing collection safety objects/latches are not reset. Current DOM page blockers
are evaluated independently of the old incident. Worker reloads were handled by
Dev Control under the active stop and reported **zero TikTok tabs refreshed**.
The same original tab ID and home URL were revalidated afterward.

## Passive check and UI

SAFE_RECOVERY_CHECK **789192d31f878bff9e766d4cafa6d693** returned **HEALTHY** after
two distinct actual heartbeat observations at 19:07:34 and 19:07:37 UTC on the same
tab. `release_json` is **NULL**. No release endpoint was called.

`confirmed-real-session.json`, `live-detector-result.json` and `verification.json`
contain the authoritative runtime state. `ui-real-state-validation.json` uses that
actual state with the served dashboard renderer and verifies:

- Session Confirmed.
- Profile ✓, Messages ✓, Activity ✓, Avatar ✓, Following ✓.
- Logged-out signal ✗.
- ACTION waiting_for_collection_recovery.
- Technical debug collapsed; mini log limited to ten semantic transition entries.

The ACTION setter also refuses stale waiting_for_login when the latest fresh
account state is already confirmed. Security remains a separate operational gate.

## Preservation

72 existing tables were compared to the pre-change checkpoint: 68 identical;
expected differences only in events, heartbeat/system state, dev diagnostic
commands and passive-check audit rows. The current security-stop and incident
history rows are exactly identical. No content commands, search observations,
trend snapshots, Product Identity/Gold/candidate or category records changed.

No browser/profile/tab was created for this validation. No TikTok page was
navigated, refreshed, clicked or scrolled. No login was requested and no engagement
occurred. Only existing document attributes and account-navigation controls were
read. The test fixtures below supplement, not replace, actual-DOM validation.

## Tests

- **474 Python passed**, seven existing deprecation warnings; task
  `ad5f2883e4a84be798f3e52ddb1dd0e3`.
- **147 Node/dashboard passed**, zero failures/skips; task
  `820ab298c6e640ff9d64627df680b43d`.
- New regressions cover current structural nav buttons, hidden legacy inbox,
  partial positives, correlated controls, generic Following rejection, strong
  logged-out override, historical-latch independence, backend family validation,
  fixed same-tab probe audit/idempotence, observer installation without browser
  actions, and confirmed+active-stop UI action.

## Files changed

`extension/session_signals.js`, `session_observer.js`, `session_probe.js`,
`manifest.json`, `background.js`, `dev_worker.js`; `app/schemas.py`,
`main.py`, `browser_safety.py`, `safe_collection.py`, `dev_control.py`;
existing connection dashboard, related tests and `docs/DEV_CONTROL.md`.
No product detector, taxonomy, identity algorithm or collection workflow was run.

## Operational boundary

Session is now confirmed; collection is still stopped. This correction does not
authorize or perform latch release, Stage 1, Stage 2, smoke, Discovery or enrichment.
