from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from typing import Literal
from urllib.parse import urlsplit, parse_qs
import re
from .extraction import video_identity, parse_views, completeness, STRUCTURED_FIELDS, METRIC_FIELDS, EXTRACTOR_VERSION, DETAIL_VERSION, DETAIL_VERSIONS, DETAIL_METRIC_CONFIDENCE
from .comment_schemas import CommentsSample
from .creator_schemas import CreatorProfile


class FieldEvidence(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    value: str | int | None
    raw_value: str | None = Field(default=None, max_length=100)
    confidence: float = Field(ge=0, le=1)
    source: Literal['search_card', 'heuristic_text', 'video_detail', 'comments', 'external_source']
    observed_at: str | None = None
    method: Literal['semantic_text','action_text','adjacent_text','aria_label','generated_content'] | None = None


class NodeGeometry(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    top: float
    bottom: float
    left: float
    right: float


class VisibilityEvidence(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    candidates: int = Field(ge=0)
    visible: int = Field(ge=0)
    rects: list[NodeGeometry] = Field(max_length=3)


class Viewport(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    width: float = Field(ge=0)
    height: float = Field(ge=0)


class CardDiagnostics(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    viewport: Viewport
    card_rect: NodeGeometry
    creator: VisibilityEvidence
    caption: VisibilityEvidence
    views: VisibilityEvidence


def search_page_query(url: str) -> str:
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.netloc != 'www.tiktok.com'
            or parsed.path.rstrip('/') != '/search'):
        raise ValueError('Expected a TikTok search page')
    query = parse_qs(parsed.query).get('q', [''])[0]
    if not query.strip() or len(query) > 200:
        raise ValueError('Expected a nonblank search query of at most 200 characters')
    return query


class CaptureCommand(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    type: Literal['READ_SEARCH_RESULTS']


class DiscoveryCommand(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    type: Literal['DISCOVER_MORE_RESULTS']
    query: str = Field(min_length=1,max_length=200)
    max_scrolls: int = Field(default=5,ge=1,le=5)
    max_new_videos: int = Field(default=30,ge=1,le=30)
    max_runtime: int = Field(default=90,ge=1,le=90)

    @field_validator('query')
    @classmethod
    def normalize_query(cls,value):
        value=' '.join(value.split())
        if not value:
            raise ValueError('Query cannot be blank')
        return value


class VideoDetailCommand(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    type: Literal['READ_VIDEO_DETAIL']
    video_url: str = Field(max_length=2048)

    @field_validator('video_url')
    @classmethod
    def known_video_route(cls, value):
        return video_identity(value)[0]


class VisibleVideo(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    video_url: str = Field(max_length=2048)
    video_id: str | None = Field(default=None, max_length=64)
    creator_username: str | None = Field(default=None, max_length=256)
    creator_display_name: str | None = Field(default=None, max_length=512)
    caption: str | None = Field(default=None, max_length=4000)
    views_raw: str | None = Field(default=None, max_length=100)
    views: int | str | None = None
    thumbnail_url: str | None = Field(default=None, max_length=4096)
    search_position: int | None = Field(default=None, ge=1, le=100)
    field_evidence: dict[str, FieldEvidence] = Field(default_factory=dict)
    extraction_completeness: float = Field(default=0, ge=0, le=1)
    card_snapshot: str | None = Field(default=None, max_length=12000)
    card_diagnostics: CardDiagnostics | None = None
    likes: str | None = Field(default=None, max_length=100)
    comments_count: str | None = Field(default=None, max_length=100)
    shares: str | None = Field(default=None, max_length=100)
    favorites: str | None = Field(default=None, max_length=100)
    raw_visible_text: str | None = Field(default=None, max_length=10000)
    extraction_version: Literal['search-dom-v1', 'tiktok-search-card-v1', 'tiktok-search-card-v2', 'tiktok-video-detail-v1', 'tiktok-video-detail-v2'] = 'search-dom-v1'

    @field_validator('video_url')
    @classmethod
    def canonical_video_url(cls, value):
        return video_identity(value)[0]

    @field_validator('thumbnail_url')
    @classmethod
    def public_image_url(cls, value):
        if value is not None:
            parsed = urlsplit(value)
            if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError('Expected a public HTTPS image URL')
        return value

    @model_validator(mode='after')
    def consistent_enrichment(self):
        expected_id = video_identity(self.video_url)[1]
        if self.video_id is not None and self.video_id != expected_id:
            raise ValueError('video_id does not match video URL')
        if self.extraction_version in ('tiktok-search-card-v1', EXTRACTOR_VERSION, *DETAIL_VERSIONS):
            detail = self.extraction_version in DETAIL_VERSIONS
            permitted_sources = ('video_detail',) if detail else ('search_card', 'heuristic_text')
            if self.video_id != expected_id or (not detail and self.search_position is None):
                raise ValueError('Enriched results require URL identity and position')
            if self.views is not None and (type(self.views) is not int or self.views < 0):
                raise ValueError('Enriched views must be a nonnegative integer or null')
            if self.views != parse_views(self.views_raw):
                raise ValueError('views does not match views_raw')
            if abs(self.extraction_completeness - completeness(self.model_dump())) > .000001:
                raise ValueError('Incorrect extraction completeness')
            for field in STRUCTURED_FIELDS:
                evidence = self.field_evidence.get(field)
                value = getattr(self, field)
                if value is not None and (evidence is None or evidence.value != value):
                    raise ValueError(f'Missing or inconsistent evidence for {field}')
                if value is not None and evidence.confidence < .6:
                    raise ValueError(f'Low-confidence {field} must remain null')
                if evidence is not None and (evidence.value != value or evidence.source not in permitted_sources):
                    raise ValueError(f'Invalid evidence for {field}')
            if set(self.field_evidence) - set(STRUCTURED_FIELDS) - set(METRIC_FIELDS):
                raise ValueError('Unknown evidence field')
            if self.field_evidence.get('views') and self.field_evidence['views'].raw_value != self.views_raw:
                raise ValueError('Views evidence must preserve raw_value')
            for metric in METRIC_FIELDS[1:]:
                raw = getattr(self, metric)
                evidence = self.field_evidence.get(metric)
                if evidence is not None:
                    if raw is None or evidence.raw_value != raw or evidence.value != parse_views(raw) or evidence.source != ('video_detail' if detail else 'search_card'):
                        raise ValueError(f'Inconsistent visible metric evidence: {metric}')
                elif raw is not None and self.extraction_version in (EXTRACTOR_VERSION, *DETAIL_VERSIONS):
                    raise ValueError(f'Missing visible metric evidence: {metric}')
            if self.extraction_version == DETAIL_VERSION:
                for metric in METRIC_FIELDS:
                    evidence = self.field_evidence.get(metric)
                    if evidence is not None:
                        expected_confidence = DETAIL_METRIC_CONFIDENCE.get(evidence.method)
                        if expected_confidence is None or (evidence.value is not None and
                                (type(evidence.value) is not int or abs(evidence.confidence-expected_confidence) > .000001)):
                            raise ValueError(f'Invalid metric extraction method/confidence: {metric}')
                        if evidence.value is None and evidence.confidence != 0:
                            raise ValueError(f'Unknown metric must have zero confidence: {metric}')
        else:
            if self.views is not None and not isinstance(self.views, str):
                raise ValueError('Legacy views must be visible text')
            if self.field_evidence:
                raise ValueError('Legacy results cannot assert new field provenance')
        return self


class VideoDetail(VisibleVideo):
    extraction_version: Literal['tiktok-video-detail-v1','tiktok-video-detail-v2'] = DETAIL_VERSION


class SearchResults(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    query: str = Field(min_length=1, max_length=200)
    page_url: str = Field(max_length=4096)
    results_count: int = Field(ge=0, le=100)
    links_detected: int = Field(ge=0, le=10000)
    invalid_results: int = Field(default=0,ge=0,le=10000)
    results: list[VisibleVideo] = Field(max_length=100)

    @model_validator(mode='after')
    def consistent_results(self):
        if search_page_query(self.page_url) != self.query:
            raise ValueError('Query does not match the captured page')
        if self.results_count != len(self.results) or self.links_detected < self.results_count:
            raise ValueError('Result counts do not match the payload')
        if len({r.video_url for r in self.results}) != len(self.results):
            raise ValueError('Results must be deduplicated by video_url')
        if len({video_identity(r.video_url)[1] for r in self.results}) != len(self.results):
            raise ValueError('Results must be deduplicated by video_id')
        if len({r.extraction_version for r in self.results}) > 1:
            raise ValueError('A capture must use a single extractor version')
        if any(r.extraction_version in DETAIL_VERSIONS for r in self.results):
            raise ValueError('Video detail cannot be submitted as search-card evidence')
        positions = [r.search_position for r in self.results if r.search_position is not None]
        if len(set(positions)) != len(positions):
            raise ValueError('Search positions must be unique within a capture')
        return self


class VideoObservation(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    id: int
    source: Literal['tiktok']
    video_id: str | None
    canonical_url: str
    video_url: str
    creator_username: str | None
    creator_display_name: str | None
    caption: str | None
    thumbnail_url: str | None
    views: int | None
    views_raw: str | None
    likes: str | None
    comments_count: str | None
    shares: str | None
    favorites: str | None
    search_position: int | None
    raw_visible_text: str | None
    extraction_version: str
    extractor_version: str
    extraction_completeness: float
    field_evidence: dict[str, FieldEvidence]
    observation_id: int
    capture_id: str
    card_snapshot: str | None
    card_diagnostics: CardDiagnostics | None
    search_query: str
    collected_at: str
    first_seen_at: str
    last_seen_at: str


class RecentVideos(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    total: int
    items: list[VideoObservation]


class VideoCount(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    total: int


class ExtractionQuality(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    capture_id: str | None
    query: str | None
    observed_at: str | None
    extractor_version: str | None
    total: int
    library_total: int
    current_capture: int
    new_this_capture: int | None
    updated_duplicates: int | None
    coverage: dict[str, float]
    complete: int
    partial: int
    minimal: int
    thresholds_met: bool

class SessionDOMSignals(BaseModel):
    model_config = ConfigDict(extra='forbid',strict=True)
    profile_route_present: bool = False
    messages_route_present: bool = False
    activity_or_inbox_present: bool = False
    authenticated_sidebar_present: bool = False
    account_avatar_present: bool = False
    following_authenticated_present: bool = False
    logged_out_cta_present: bool = False


class SessionSelectorDebug(BaseModel):
    model_config = ConfigDict(extra='forbid',strict=True)
    selector: str = Field(max_length=1024)
    matched_count: int = Field(ge=0,le=100000)
    visible_count: int = Field(ge=0,le=100000)
    sample_href: str | None = Field(default=None,max_length=512)
    sample_aria: str | None = Field(default=None,max_length=200)
    sample_data_e2e: str | None = Field(default=None,max_length=100)


class BridgeHeartbeat(BaseModel):
    session_auth_groups: list[Literal['account_identity','account_communication','followed_accounts']] = Field(default_factory=list,max_length=3)
    live_page_blocker: str | None = Field(default=None,max_length=500)
    session_signals: SessionDOMSignals | None = None
    session_debug: dict[str,SessionSelectorDebug] | None = None
    session_detector_version: str | None = Field(default=None,max_length=32)
    command_api_status: int | None = Field(default=None,ge=100,le=599)
    command_api_error: str | None = Field(default=None,max_length=500)
    api_version: str | None = Field(default=None,max_length=32)
    safe_collection_version: Literal['v1'] | None = None
    model_config = ConfigDict(extra="forbid")
    extension_version: str = "unknown"
    companion_version: str | None = Field(default=None, max_length=64)
    build_id: str | None = Field(default=None, pattern=r'^[a-f0-9]{16}$')
    current_url: str = ""
    page_title: str | None = None
    authenticated_hint: bool = False
    page_ready_state: str | None = None
    has_search_ui: bool = False
    playback_error_visible: bool = False
    tab_id: int | None = None
    window_id: int | None = None
    tiktok_tab_count: int = Field(default=0, ge=0)
    document_visibility: str | None = Field(default=None, max_length=32)
    window_state: str | None = Field(default=None,max_length=32)
    window_width: int | None = None
    window_height: int | None = None
    tab_active: bool | None = None
    security_stop: str | None = Field(default=None, max_length=500)
    security_stop_observed_at: str | None = Field(default=None,max_length=64)
    current_page_status: Literal['healthy','http_403','challenge','unknown'] = 'unknown'
    tiktok_session_status: Literal['confirmed','unconfirmed','login_required'] = 'unconfirmed'
    session_evidence: list[Literal['visible_own_profile_with_avatar','visible_account_inbox']] = Field(default_factory=list, max_length=2)


class SecurityStop(BaseModel):
    model_config = ConfigDict(extra='forbid')
    extension_id: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=1, max_length=500)
    observed_at: str = Field(max_length=64)

class SearchCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["SEARCH"] = "SEARCH"
    query: str = Field(min_length=1, max_length=200, strict=True)

    @field_validator("query")
    @classmethod
    def normalized_query(cls, query: str) -> str:
        query = " ".join(query.split())
        if not query:
            raise ValueError("Search query cannot be blank")
        return query

class CommandResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    extension_id: str = Field(min_length=1, max_length=128)
    status: Literal["SUCCEEDED", "FAILED"]
    detail: str = Field(default="", max_length=1000)
    capture: SearchResults | None = None
    video_detail: VideoDetail | None = None
    comments_sample: CommentsSample | None = None
    creator_profile: CreatorProfile | None = None
    search_diagnostics: dict | None = None

    @field_validator('search_diagnostics')
    @classmethod
    def bounded_search_diagnostics(cls,value):
        import json
        if value is not None and (len(json.dumps(value))>32768 or set(value)-{'query','pre_health','navigation_state','settle_samples','final_health','stop_reason'}):raise ValueError('Invalid bounded search diagnostics')
        return value

    @model_validator(mode='after')
    def capture_only_on_success(self):
        if any(value is not None for value in (self.capture,self.video_detail,self.comments_sample,self.creator_profile)) and self.status != 'SUCCEEDED':
            raise ValueError('Failed commands cannot contain observations')
        if sum(value is not None for value in (self.capture,self.video_detail,self.comments_sample,self.creator_profile))>1:
            raise ValueError('A command can return search evidence or detail evidence, not both')
        return self

class MissionCreate(BaseModel):
    market: str = Field(default="US")
    mode: str = Field(default="smart_discovery")
    max_videos: int = Field(default=300, ge=25, le=1000)
    read_comments: bool = True
    capture_evidence: bool = True
    discover_related: bool = True
