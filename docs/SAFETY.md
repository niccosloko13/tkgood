# TikTok Safety Model — v0.1.4

The company account is STRICT READ ONLY.

Local development maintenance is explicitly authorized: an owned backend process
may restart, the installed Companion may self-reload, and existing TikTok tabs
may refresh. DEV operations require opt-in development mode, loopback, local token
and pinned Companion identity. They use a separate queue and cannot activate page
controls. No additional Chrome permissions are requested. See DEV_CONTROL.md.

The TikTok tab runs in normal Google Chrome, not in Playwright-controlled Chromium.

The Product Hunter Companion extension may:
- read current URL
- read document title
- read visible page text for coarse state signals
- send heartbeat to localhost
- navigate an existing TikTok tab to the fixed /search route for an explicit SEARCH command
- read only the visible DOM of the current /search page for an explicit READ_SEARCH_RESULTS command
- send at most 100 unique visible video observations per manual capture to localhost
- navigate to an already-collected public video for explicit READ_VIDEO_DETAIL and read visible metadata/counts, without activating any engagement control

It may not:
- activate any engagement control or expose a generic click command
- like
- dislike
- comment
- reply
- follow/unfollow
- share/repost
- save/favorite
- send messages
- publish
- edit profile/settings
- edit account/settings
- read passwords
- read authentication cookie values
- bypass CAPTCHA/security checks

No stealth or browser-fingerprint manipulation is part of this project.

Search Capture never clicks, scrolls, expands cards, opens comments, follows result
links, inspects page scripts/internal state, or requests TikTok APIs. The only
network destination used by the extension is the local backend. SEARCH and the
explicitly authorized READ_VIDEO_DETAIL navigate the existing normal Chrome tab.
No Playwright is added to this flow.

Video links must be HTTPS TikTok /@username/video/numeric-id URLs. Tracking query
parameters and fragments are removed for deduplication. Text and metrics must be
rendered inside the viewport; absent or hidden fields stay null. Usernames are
not inferred from video URLs; visible profile hrefs inside a card may identify
the creator with explicit field evidence. Reading metric labels does not activate buttons.
No generic click(selector), cookie/token/password access, CAPTCHA bypass, stealth,
webdriver modification, fingerprint spoofing, AI or product scoring is provided.

Enrichment saves only public, visible card data and bounded sanitized card
fragments. Inputs, forms, hidden content, scripts, event handlers and URL
attributes are excluded from HTML evidence. No full page is stored. Thumbnail
URLs may be saved; the extractor/backend do not download image files. Following
explicit user authorization, detail pages may supply visible metadata and counts.
Internal TikTok data is not collected. Public comment bodies are collected only
through the explicitly authorized bounded comments command below. Evidence confidence is
deterministic method quality; missing fields remain null. No new browser
permissions are added.

v2 visibility diagnostics store only bounded node counts and rectangles when a
field is unavailable. They never collect offscreen field values. Sibling metadata
may be read only inside the same single-video logical card; no page/global text
is used to fill fields. Library/current/new/duplicate counters never delete or
reset historical records. Visible metric evidence may include favorites; this
does not activate any save/favorite or other engagement control.

Numeric detail extraction reads only visible semantic count nodes, their own
small action region and accessible labels. Rendering a local CSS-generated count
may supply its literal text; hidden fields and arbitrary data attributes do not.
No global page text supplies metric values. Placeholder labels never become zero.
The existing video window may be focused/restored for rendering, with one bounded
recovery; no action button is clicked. Missing numbers remain null. Security
challenges stop the read rather than being bypassed. See VIDEO_DETAIL_METRICS.md.

## Authorized visible comments sampling

READ_COMMENTS_SAMPLE is restricted to an existing, enriched library video.
It may activate only the fixed semantic comments-section opener and scroll only
the identified comments container. It never scrolls the body/feed, expands replies,
opens a reply composer, likes a comment or activates any other engagement control.
The initial target is 30, absolute maximum 100, with bounded waits/scroll attempts.
Hidden/offscreen comment text is excluded; metadata is read only within its row.
Accessible numeric labels may provide visible comment likes without activating
their button. Missing values stay null. No cookies, credentials, full page HTML,
TikTok API requests, profile collection, AI or sentiment analysis are introduced.
See COMMENTS.md for raw evidence and the real three-video validation.

## Authorized creator / profile enrichment

READ_CREATOR_PROFILE may open only the public profile resolved from a previously
observed library video's creator. It reads the visible logical profile header,
public counts/bio/avatar/links and returns to that video. It never clicks any
profile control, follows an external link, scrolls a profile/feed, opens profiles
from sampled comments, or traverses related accounts. Existing VIDEO DETAIL and
comment readers are unchanged. A security challenge stops the read.

Only public field evidence is stored; no cookies, credentials, account settings,
page scripts/internal state or TikTok APIs. Public commercial contact text may
appear verbatim in a creator's visible bio. URL validation rejects credentials
and sensitive parameters. Creator Independence is a transparent deterministic
heuristic, not AI, causal proof or a product score. See CREATORS.md.
