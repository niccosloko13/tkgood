from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from typing import Literal
from urllib.parse import urlsplit, parse_qs
import re


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


class VisibleVideo(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    video_url: str = Field(max_length=2048)
    creator_username: str | None = Field(default=None, max_length=256)
    creator_display_name: str | None = Field(default=None, max_length=512)
    caption: str | None = Field(default=None, max_length=4000)
    views: str | None = Field(default=None, max_length=100)
    likes: str | None = Field(default=None, max_length=100)
    comments_count: str | None = Field(default=None, max_length=100)
    shares: str | None = Field(default=None, max_length=100)
    raw_visible_text: str | None = Field(default=None, max_length=10000)
    extraction_version: Literal['search-dom-v1'] = 'search-dom-v1'

    @field_validator('video_url')
    @classmethod
    def canonical_video_url(cls, value):
        parsed = urlsplit(value)
        if (parsed.scheme != 'https' or parsed.netloc not in ('www.tiktok.com', 'tiktok.com')
                or not re.fullmatch(r'/@[A-Za-z0-9._]+/video/[0-9]+/?', parsed.path)):
            raise ValueError('Expected a public TikTok video URL')
        return 'https://www.tiktok.com' + parsed.path.rstrip('/')


class SearchResults(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    query: str = Field(min_length=1, max_length=200)
    page_url: str = Field(max_length=4096)
    results_count: int = Field(ge=0, le=100)
    links_detected: int = Field(ge=0, le=10000)
    results: list[VisibleVideo] = Field(max_length=100)

    @model_validator(mode='after')
    def consistent_results(self):
        if search_page_query(self.page_url) != self.query:
            raise ValueError('Query does not match the captured page')
        if self.results_count != len(self.results) or self.links_detected < self.results_count:
            raise ValueError('Result counts do not match the payload')
        if len({r.video_url for r in self.results}) != len(self.results):
            raise ValueError('Results must be deduplicated by video_url')
        return self


class VideoObservation(VisibleVideo):
    id: int
    source: Literal['tiktok']
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

class BridgeHeartbeat(BaseModel):
    model_config = ConfigDict(extra="forbid")
    extension_version: str = "unknown"
    current_url: str = ""
    page_title: str | None = None
    authenticated_hint: bool = False
    page_ready_state: str | None = None
    has_search_ui: bool = False
    playback_error_visible: bool = False

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

    @model_validator(mode='after')
    def capture_only_on_success(self):
        if self.capture is not None and self.status != 'SUCCEEDED':
            raise ValueError('Failed commands cannot contain observations')
        return self

class MissionCreate(BaseModel):
    market: str = Field(default="US")
    mode: str = Field(default="smart_discovery")
    max_videos: int = Field(default=300, ge=25, le=1000)
    read_comments: bool = True
    capture_evidence: bool = True
    discover_related: bool = True
