"""Deterministic identity, evidence precedence and capture quality. No network/AI."""
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

EXTRACTOR_VERSION = 'tiktok-search-card-v2'
DETAIL_VERSION = 'tiktok-video-detail-v2'
DETAIL_VERSIONS = ('tiktok-video-detail-v1', DETAIL_VERSION)
DETAIL_METRIC_CONFIDENCE = {'semantic_text': .98, 'action_text': .94,
                           'adjacent_text': .90, 'aria_label': .95, 'generated_content': .95}
METRIC_FIELDS = ('views', 'likes', 'comments_count', 'shares', 'favorites')
FIELD_PRECEDENCE = {'heuristic_text': 10, 'search_card': 20, 'video_detail': 30}
COVERAGE_FIELDS = {'video_url': 'video_url', 'video_id': 'video_id', 'creator': 'creator_username',
                   'caption': 'caption', 'views': 'views', 'thumbnail': 'thumbnail_url'}
STRUCTURED_FIELDS = ('video_url', 'video_id', 'creator_username', 'creator_display_name',
                     'caption', 'views', 'thumbnail_url')


def video_identity(url):
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.netloc not in ('www.tiktok.com', 'tiktok.com')
            or not re.fullmatch(r'/@[A-Za-z0-9._]+/video/[0-9]+/?', parsed.path)):
        raise ValueError('Expected a public TikTok video URL')
    return 'https://www.tiktok.com' + parsed.path.rstrip('/'), parsed.path.rstrip('/').rsplit('/', 1)[1]


def legacy_url_fallback(url):
    """Normalize a legacy TikTok URL without fabricating a numeric video ID."""
    try:
        parsed = urlsplit(url)
        if parsed.scheme == 'https' and parsed.netloc in ('www.tiktok.com', 'tiktok.com'):
            return 'https://www.tiktok.com' + (parsed.path.rstrip('/') or '/')
    except ValueError:
        pass
    return url


def parse_views(raw):
    if raw is None:
        return None
    text = raw.strip().replace('\u00a0', ' ')
    text = re.sub(r'^(?:views|visualiza[çc][õo]es)\s*:?\s*', '', text, flags=re.I)
    text = re.sub(r'\s+(?:views|visualiza[çc][õo]es)$', '', text, flags=re.I)
    # Grouped integers have exactly three digits per group; decimal commas are
    # accepted with a suffix. Ambiguous unsuffixed decimals remain unknown.
    if re.fullmatch(r'\d+', text):
        value = int(text)
    elif re.fullmatch(r'\d{1,3}([., ])\d{3}(?:\1\d{3})*', text):
        value = int(re.sub(r'[., ]', '', text))
    else:
        match = re.fullmatch(r'(\d+(?:[.,]\d+)?)\s*([KMB])', text, re.I)
        if not match:
            return None
        try:
            value = Decimal(match[1].replace(',', '.')) * {'K': 1000, 'M': 1000000, 'B': 1000000000}[match[2].upper()]
        except InvalidOperation:
            return None
        if value != value.to_integral_value():
            return None
        value = int(value)
    return value if 0 <= value <= 9007199254740991 else None


def completeness(values):
    return sum(values.get(field) is not None for field in COVERAGE_FIELDS.values()) / 6


def merge_evidence(current, incoming):
    """Missing evidence never erases known data; rank wins, then recency."""
    merged = dict(current)
    for field, candidate in incoming.items():
        if candidate.get('value') is None or candidate.get('source') not in FIELD_PRECEDENCE:
            continue
        old = merged.get(field)
        new_rank = FIELD_PRECEDENCE[candidate['source']]
        old_rank = FIELD_PRECEDENCE.get(old.get('source'), 0) if old else -1
        if (new_rank > old_rank or (new_rank == old_rank and
                datetime.fromisoformat(candidate['observed_at']) >= datetime.fromisoformat(old['observed_at']))):
            merged[field] = candidate
    return merged


def capture_quality(rows):
    total = len(rows)
    coverage = {key: round(sum(row.get(field) is not None for row in rows) * 100 / total, 2) if total else 0.0
                for key, field in COVERAGE_FIELDS.items()}
    complete = sum(completeness(row) >= .8 for row in rows)
    partial = sum(.4 <= completeness(row) < .8 for row in rows)
    return {'total': total, 'coverage': coverage, 'complete': complete, 'partial': partial,
            'minimal': total - complete - partial,
            'thresholds_met': total >= 8 and coverage['video_url'] == 100 and coverage['video_id'] == 100
            and coverage['creator'] >= 75 and coverage['caption'] >= 70 and coverage['views'] >= 75}
