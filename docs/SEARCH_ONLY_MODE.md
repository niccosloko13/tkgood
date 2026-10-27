# Search-only operational mode

Direct video enrichment is persistently PAUSED with reason
REPEATED_CHALLENGE_AFTER_VIDEO_NAVIGATION. The backend queue, semantic readers,
Companion navigation guard and pilot entry points enforce the pause. Restarting
services does not enable direct readers. A new explicit human authorization is
required before changing this mode.

No CAPTCHA is automated and no security stop is cleared by this mode. Search
collection is AVAILABLE only with fresh HEALTHY/CONFIRMED home/search evidence and
no global stop or pending target assessment. Existing Stage 1/2 collection remains
unchanged. A new collection batch requires authorization; this change starts none.

TOP CANDIDATES uses only persisted search_observations while paused. Historical
individual enrichment stays separately labelled as history. Derived search-only
projections never overwrite detail, comment, creator or intelligence evidence.
Search counters are used only when numeric evidence exists, without carrying old
metrics forward. Velocity uses timestamped displayed-counter deltas and existing
conflict/interval checks; it is not market demand. Ambiguous timezone timestamps
are excluded from velocity. Recaptures and duplicate density describe local
sampling coverage, not independent product corroboration. Creator recurrence
uses observed card handles, not inferred profile quality. Category relevance and
literal specificity use card caption/query text. Priority buckets schedule possible
future evidence collection; they are not an Opportunity Score or final ranking.

Purchase intent from comments, product quality and creator profile quality remain
INSUFFICIENT in the search-only projection. Missing counters stay unavailable.
Thumbnail metadata is read from saved cards; no image is downloaded.

navigation_challenge_contexts preserves both recorded incidents, their navigation
mode, target, timestamp, stage and retained pre/post evidence. Missing historical
raw samples are explicitly marked as not retained. Target association is context,
not proof that a particular video caused the challenge. The original incidents,
quarantines, metrics and security latch remain preserved.
