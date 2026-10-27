# Controlled Stage 2 search pilot

The explicit operator request authorizes one small Casa batch, not enrichment.
The fixed `controlled-stage2` background task uses five existing HOME_DISCOVERY_V1
queries: home gadgets, home finds, useful home products, kitchen gadgets, and
cleaning gadgets. The backend accepts only a matching expressly authorized pack,
a passed Stage 1 and a new two-sample authenticated healthy home/search check.
No incident is cleared. The fresh check binds the currently provisioned Companion
build; the historical Stage 1 record remains unchanged.

Each command reads one visible viewport, maximum ten visible link candidates,
with zero scroll, detail, comments, profiles, image capture or engagement. New
video capacity is reduced to the remaining budget. Global limits are five queries,
thirty new videos and 180 seconds. At least 35 seconds must remain before another
query starts, so there is room for its bounded command. The worker receives the
batch deadline. Each completed query pauses; the fixed runner issues a separate
explicit next-query request within the user's five-query authorization. A failed
or uncertain command is never resubmitted. Complete-page health/session failure
stops Stage 2 at its first diagnostic sample; loading documents are not read.

Quarantined video references can be persisted if visibly present, but their URLs
are never opened. `blocked` is a subset of valid result references, not an extra
result count. Before every query the runner consults quarantine and refuses any
global latch, target-health hold, unconfirmed session or unhealthy general page.

`safe_query_metrics` stores immutable command-keyed results, new/duplicate videos,
blocked references, invalid visible video-link candidates, unique visible creator
usernames, deterministic primary-home category matches, actual observation time,
and snapshot source coverage. Invalid counts refer only to visible candidates
examined within the viewport cap. Creator/category counts reflect available
evidence and are not inferred from missing metadata. Planner aggregate query
metrics include these successful bounded captures alongside discovery sessions.

The existing search-observation hook calls record_trend_snapshot for each new
temporal observation, including duplicate library videos. Source keys make result
delivery idempotent. Missing numeric metrics remain null. Stage 2 runs only the
existing deterministic category classifier for its query metrics and schedules no
identity/resolver or enrichment jobs.

The runner saves intent before each content POST and records its outcome under
`artifacts/controlled-stage2/run-20261025.json`. A second launch with that intent
present is refused. Task lifecycle/results are in `.runtime/logs/task-ID.json`
and `task-ID.log`. There is no Stage 3 continuation.

## Explicit stability-only resumption

The later explicit operator request permits one resumption of the interrupted
home-finds command. It is accepted only for a transient session-stability failure
with zero saved observations. Hard-stop failures and already completed queries
cannot resume. The same batch, successful command records, counters and capture
IDs remain intact; only the failed zero-data cursor is restored. The old failed
command remains immutable. A unique resumption record archives the original batch
state and makes repeated resume POSTs return the same initial command ID.

The 180-second active execution budget retains time already consumed before the
interruption and excludes the human authorization pause. It is not reset to 180
seconds; original query and new-video caps also remain in force. Terminal elapsed
time freezes at completion. A new passive healthy check binds the loaded build,
without changing or clearing security state.

Before each remaining navigation the worker requires two consecutive real
HEALTHY/CONFIRMED samples separated by normal pacing. After the one navigation,
it permits the bounded settle interval and waits for another healthy pair.
UNKNOWN, incomplete documents and a removed content-script receiver are transient
within this interval, not proof of logout. The shared 25-second command stability
deadline and sample bound end with SESSION_NOT_STABLE. Actual HTTP 403, challenge,
CAPTCHA, confirmed login-required/logout and unexpected hosts stop immediately;
an unexpected route gets only a three-second grace (a known pending search
navigation is allowed to finish within the overall deadline). No navigation or
card capture is retried. Each query's pre-health, navigation state, settle samples,
final health and stop reason are durably attached to its command result.

Use the fixed `resume-stage2` background task once. Its exclusive intent/report is
`artifacts/controlled-stage2/resume-20261025.json`; the original report remains
unchanged. This task skips home gadgets and cannot create another search batch.
