# Experimental recent-24h search — blocked safely

## Preflight

- `tiktok_tab=true`
- `PAGE=HEALTHY`
- `SESSION=CONFIRMED`
- `GLOBAL SECURITY=OK` (no browser-security latch)
- `DIRECT VIDEO ENRICHMENT=PAUSED`

## Attempt

One requested experimental query, `new viral products`, was submitted through
the existing read-only search command. It was rejected before command creation
and before any navigation:

```text
409 Safe recovery guard: only explicitly bounded collection is allowed
```

## Why collection did not run

The active Safety Contract permits only explicitly authorized bounded collection.
The canonical `DiscoveryRunner` additionally permits Stage 2 only for the
already-authorized Casa query pack and rejects unobserved queries in Stage 1.
The requested experimental queries are not in that pack.

No guard was disabled, no query pack was edited, and no alternate navigation or
retry was attempted.

## Results

- Queries navigated: 0
- Search captures: 0
- New videos: 0
- Duplicates: 0
- New observations/snapshots: 0 / 0
- Confirmed `RECENT_24H_CONFIRMED`: 0
- `RECENCY_UNKNOWN`: 0
- New creators/candidates: 0 / 0
- Top Opportunities changes: none

## Final state

The attempted request did not create a command or alter the TikTok page. The
last verified state remains healthy/confirmed with global security OK and direct
video enrichment paused.

## Required next decision

To run this experiment safely, the user must explicitly authorize a change to
the existing bounded collection policy/configuration that adds a finite
experimental query pack. That change should define the exact query list, query
limit, retention/reporting behavior, and authorization path; it must not weaken
the Safety Contract or enable direct-video enrichment.
