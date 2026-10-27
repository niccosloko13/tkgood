# Virality + Quality Intelligence v1

`app/intelligence_signals.py` extends the existing Intelligence Core's read model.
It does not run identity resolution, change candidates, create entities, call a
provider, or read Gold labels. `card.intelligence` is the canonical versioned
dimension view. Legacy `quality` remains compatible with existing clients and
historical decision evidence; it is not silently rewritten.

Run the bounded, entirely offline pilot and library materialization:

```
.\.venv\Scripts\python.exe scripts/virality_quality.py
```

The pilot is videos 1, 3, 18 plus the current REVIEW videos, deduplicated. It runs
before the remaining local library. Repeated identical results reuse snapshots;
changed results append history in `intelligence_dimension_snapshots`. The CLI
verifies protected tables against the sprint checkpoint. No browser work is queued.
The dashboard computes the current read model without database writes.

## Evidence and coverage

Policy is centralized in `config/virality_quality.json`. Purchase Intent v2 uses
normalized author + text, across captures and inconsistent platform comment IDs.
Different known authors expressing the same request remain distinct demand
signals; anonymous duplicates of attributed text add no demand. An author can
appear in several intent types but counts once in the unique intent-author total.
Anonymous comments contribute to comment ratios, not author counts. Author names
are identifiers reported by the source, not verified independent people.

Measured intent needs 10 unique comments and 70% attributed-comment coverage.
STRONG also needs 5 intent authors and 35% of sampled authors; MODERATE needs 2
and 15%. Missing samples have null strength and ratios. These are transparent
operational heuristics, not probabilities or measured sales. PT/EN/ES matching is
lexical, with limited negation handling; sarcasm, bots, dialects and ownership
cannot reliably be established.

Every dimension contains status, classification, coverage, sample size, unique
sources, confidence status, reason codes and evidence IDs. Source counts describe
local evidence channels; they do not assert independent third-party corroboration.
Cross-source agreement remains null when it has not been established.

Signal Quality reports single-video/creator dependence, missing creator diversity,
capture duration, deduplication and commenter coverage independently of identity.
Only approved entity occurrences may expand a product scope. Candidate recurrence
is retained as an unconfirmed hint, never a same-product association.

Product Quality separates reactions, complaints and usability statements. A
PROMISING/CONCERNING verdict needs 30 comments, 15 authors, 2 confirmed videos
and 2 creators, plus the documented positive/complaint criteria. MIXED may describe
contradictory self-reports with partial coverage; it is not a verified product verdict.

## Creative versus product

Creative DNA and Viral Potential expose features, not a combined score. Captions
can suggest function or a CTA. Persisted visual-provider observations can describe
visibility. A still image cannot establish opening timing, video transformation,
novelty, shareability, ASMR or a satisfying moment. Those remain insufficient.
No provider inference is performed in this sprint.

Repeatability is a creative hypothesis: HIGH requires 3 explicitly evidenced
observed features; MEDIUM needs 2 supported features. One partial caption signal
does not justify LOW or HIGH; it remains INSUFFICIENT. No creative performance is
inferred from missing data.

Saturation is LOCAL_EVIDENCE_ONLY. No market saturation claim is made. Trend
readiness needs at least 3 distinct numeric engagement captures spanning 24 hours.
UI labels such as "Curtida" are not numeric observations. Dates of capture are not
publication or consumer activity dates. Deduplicated comment daily counts mean
first observed in the local sample. Velocity, acceleration and change points stay
null; they are future analyses, not invented historical measurements.

Commercial readiness uses approved identity, strong measured intent and sufficient
positive quality coverage. Visual identity is reported independently and is not a
universal requirement for a specific textual identity. Supplier and price data are
reported separately; their absence does not circularly block readiness to research
suppliers. No supplier lookup is performed.

## Operational UI

`/intelligence-core` groups Product Signal and Creative Signal, with a "Por quê"
panel, author counts, evidence references and collapsed coverage/features. Filters
are boolean views, not a ranking. Human identity review remains REVIEW-only.
Security stop, Gold labels and identity decisions are never changed by this view.
