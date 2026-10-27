# Local visual assets and assisted identification

The image acquisition step is an explicit local upload. Nothing in this flow
opens TikTok, downloads a CDN thumbnail, clears security, captures a browser or
confirms a Product Entity. Existing VisualProductEvidence is extended by use,
not rebuilt. Existing thumbnail_url and Gold/candidate records remain unchanged.

## Operator flow

1. In Videos, expand the HIGH visual queue, or open the visual section in review.
2. Choose **Adicionar imagem**, select a JPG/JPEG/PNG/WebP, or drag one file into
   that video's drop zone. Check the displayed video ID before association.
3. The server checks decoded format/MIME, byte size, dimensions and integrity.
   It hashes the original bytes, stores the file locally and displays the image.
4. The initial assisted pilot is HIGH ∩ existing human Gold reviews. FN first:
   4, 5, 6, 11, 12, 14, followed by unclear item 2 in the current library.
   Other HIGH items can receive assets, but identification is not auto-expanded.
5. **IDENTIFICAR PRODUTO** prepares this image hash and textual context for an
   assisted review. It does not invoke any external provider. Repeating the
   preparation for the same video/image is idempotent.
6. Download the local image, open the [Google Lens page](https://lens.google/)
   manually and use its normal image-search workflow. The operator chooses the
   file; Babi never sends the image or a local URL to Google. This is an assisted
   experience, not a Lens scraping/API integration.
7. Record possible_product_name, result_url, source, listing_title, observed_at
   and notes. The result is google_lens_assisted / suggested. The initial web
   reference starts unverified, without compatibility/independence flags.
8. Record actual product references under **WEB CONFIRMATION**, including visual
   compatibility, possible_match, match_reason and reviewed independence. The
   hostname is derived server-side. Separate observed snapshots are retained.
9. Inspect **FINAL HYPOTHESIS**: name, canonical suggestion, proposed aliases and
   actual evidence sources. Accept/reject/unclear reviews only this proposal.
10. Save a separate visual/Gold comparison if evaluable. Existing Gold labels
    and benchmark snapshots are never updated by these actions.

**TEXT**, **VISUAL**, **WEB CONFIRMATION** and **FINAL HYPOTHESIS** remain separate.
Fields stay blank rather than being filled from a human Gold product name.
Different image hashes have different drafts; an earlier image's proposal or
comparison is not applied to a newly uploaded image. Earlier records remain
visible as history. Late uploads cannot replace a different selected review.

## Asset contract and limits

New files are stored as:

```
data/visual_assets/{internal_video_id}/{sha256}.{png|jpg|webp}
```

The existing visual_image_assets table stores the association. API records expose
video_id, asset_id, source_type, local_path, sha256, width, height, mime_type and
created_at. New additive columns preserve legacy source records. The current
selected asset is explicit; uploading never writes a local path to thumbnail_url.

- 10 MiB maximum, checked against headers and actual streamed bytes.
- Decoded PNG/JPEG/WebP only, validated with pinned Pillow in the existing .venv.
- Declared MIME and filename extension must agree with the decoded format.
  application/octet-stream is allowed only when actual bytes decode correctly.
- Positive dimensions, at most 8192 pixels per side and 20 million pixels total.
- Animated images and corrupt/truncated images are rejected.
- Original bytes are retained, not silently resized, converted or re-encoded.
- SHA-256 deduplicates within video_id. The same file associated with two videos
  is two explicit associations, not an inferred shared product.
- Duplicate uploads preserve the original record/time; a missing managed file
  can be restored from the same validated bytes. New user filenames never become
  filesystem paths. Resolved destinations must remain within the workspace.

An explicitly re-uploaded legacy local asset keeps its asset_id and original
created time, while its prior path/source metadata are archived in
source_metadata_json and its validated bytes move into the managed layout.
The old local file is not deleted. Regular duplicates do not rewrite valid
managed bytes or change their original metadata.

source_type is manual_upload, imported_asset or future_capture. Browser uploads
can specify only the first two. Legacy local_frame/local_thumbnail assets remain
readable; no legacy record is silently reclassified. New uploaded assets use the
organized directory and full decoder validation.

## Local API

- POST `/api/visual-identification/videos/{id}/assets?filename=frame.png`:
  raw binary body, Content-Type image/png/jpeg/webp, optional source_type query.
  No multipart dependency. JSON responses include duplicate, asset and image.
- POST `/videos/{id}/assisted-identification`: current image_sha256. Requires
  membership in the initial HIGH/Gold pilot and returns a local image/download
  URL, video ID, caption/comments/category and candidate/unresolved context.
- POST `/videos/{id}/lens-assisted`: explicit manually obtained provider result,
  bound to a prepared image. Saves suggested VPE and an initial product reference
  in the same transaction.
- Product-search and separate Gold comparison routes from v1 remain available.
- GET `/api/visual-identification`: ordered pilot and live local-asset metrics.

The `/videos/...` paths above are relative to `/api/visual-identification`.
The image endpoint supports download=true and never redirects to remote media.
Uploads are single-file, bounded and restricted to the local application origin.

## Canonical suggestions

Names are chosen only from the observed visual name, provider-supplied aliases
or short listing titles explicitly marked possible_match and visually compatible.
Literal caption support, then comment support, then the original visual name
break ties. Unicode/whitespace/case normalization is deterministic. Generic names
cannot displace a meaningful canonical name. Web titles become *suggested* aliases
with their source IDs; they are not verified synonyms or final product identity.
No fabricated hybrid name, translation or semantic model merge is introduced.
The operator can record a better supported name as a new attributed proposal.

## Future capture contract (no runtime implementation)

```python
persist_visual_asset(video_id, frame_bytes, {
    'source_type': 'future_capture',
    'capture_id': capture_id,
    'filename': 'frame.png',
    'content_type': 'image/png',
})
```

The interface is `app.visual_assets.persist_visual_asset`. It receives bytes
already legitimately visible and authorized outside this function; it has no
network or capture capability. A future runtime caller must prove readiness,
visibility, authorization and security eligibility before obtaining those bytes.
No caller is implemented now. future_capture is refused while a security stop
is active. Byte hash dedup persists the same video/frame only once. Manual
uploads remain available without clearing that stop.

## Metric meanings

- assets_uploaded: persisted unique manual_upload associations, excluding test
  fixtures and imported assets; assets_total includes all source types.
- HIGH_resolved/HIGH_remaining: local image availability, **not** identity quality.
- visual_attempted: selected Gold/HIGH videos explicitly prepared by the operator.
- Gold_FN_tested: FN videos with a current-image visual suggestion after preparation.
- visual_helpful/visual_wrong: separate human assessments, never guessed from a
  string mismatch or copied into Gold labels.
- visual_match: separate assessment or literal normalized comparison as in v1.
- still_unclear: pilot items without evaluable match/wrong judgement, including
  items awaiting upload or assisted results. Counts are not precision estimates.

The current initial pilot has no real images supplied yet. All successful upload,
identification and comparison examples in tests use temporary synthetic fixtures;
their counts are never reported as production outcomes.
