from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from .extraction import video_identity, parse_views

VERSION = 'tiktok-comments-visible-v2'


class CommentsCommand(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    type: Literal['READ_COMMENTS_SAMPLE']
    video_url: str = Field(max_length=2048)
    target_count: int = Field(default=30, ge=1, le=100)

    @field_validator('video_url')
    @classmethod
    def canonical(cls, value):
        return video_identity(value)[0]


class VisibleComment(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    comment_id: str | None = Field(default=None, max_length=128)
    author_username: str | None = Field(default=None, max_length=128, pattern=r'^@[A-Za-z0-9._]+$')
    text: str = Field(min_length=1, max_length=4000)
    likes: int | None = Field(default=None, ge=0)
    likes_raw: str | None = Field(default=None, max_length=100)
    timestamp: str | None = Field(default=None, max_length=200)
    position: int = Field(ge=1, le=100)
    is_reply: bool | None = None
    reply_count: int | None = Field(default=None, ge=0, le=10000000)
    raw_visible_text: str = Field(max_length=6000)
    source: Literal['comments_visible'] = 'comments_visible'
    extraction_method: Literal['semantic_comment_row'] = 'semantic_comment_row'
    confidence: float = Field(default=.95, ge=0, le=1)
    extractor_version: Literal['tiktok-comments-visible-v1','tiktok-comments-visible-v2'] = VERSION

    @model_validator(mode='after')
    def consistent(self):
        if not self.text.strip() or not self.raw_visible_text.strip():
            raise ValueError('Visible comment text/evidence must be nonblank')
        if self.likes != parse_views(self.likes_raw):
            raise ValueError('Comment likes must match visible raw count')
        if self.confidence != .95:
            raise ValueError('Semantic comment row confidence is deterministic (.95)')
        return self


class CommentsSample(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    video_url: str = Field(max_length=2048)
    target_count: int = Field(ge=1, le=100)
    comments: list[VisibleComment] = Field(max_length=100)
    stop_reason: Literal['target_reached','no_more_loaded','no_scrollable_region','scroll_limit','time_limit','empty']
    scroll_steps: int = Field(ge=0, le=20)
    extractor_version: Literal['tiktok-comments-visible-v1','tiktok-comments-visible-v2'] = VERSION
    diagnostics: list[str] = Field(default_factory=list, max_length=20)

    @field_validator('video_url')
    @classmethod
    def canonical(cls,value):
        return video_identity(value)[0]

    @model_validator(mode='after')
    def bounded(self):
        if len(self.comments)>self.target_count:
            raise ValueError('Sample exceeds requested target')
        if self.stop_reason=='target_reached' and len(self.comments)!=self.target_count:
            raise ValueError('Target reached requires a full sample')
        if any(comment.extractor_version!=self.extractor_version for comment in self.comments):
            raise ValueError('Mixed comment extractor versions')
        positions=[item.position for item in self.comments]
        if positions != list(range(1,len(positions)+1)):
            raise ValueError('Sample positions must be consecutive and unique')
        identifiers=[item.comment_id for item in self.comments if item.comment_id is not None]
        if len(set(identifiers))!=len(identifiers):
            raise ValueError('Duplicate comment IDs in a sample')
        if any(len(line)>500 for line in self.diagnostics):
            raise ValueError('Diagnostic entry too long')
        return self


class CommentSignals(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    comments_sampled: int = Field(ge=0,le=100)
    unique_commenters: int = Field(ge=0,le=100)
    duplicate_ratio: float = Field(ge=0,le=1)
    comments_with_question_mark: int = Field(ge=0,le=100)
    comments_with_price_terms: int = Field(ge=0,le=100)
    comments_with_link_terms: int = Field(ge=0,le=100)
    comments_with_buy_terms: int = Field(ge=0,le=100)
    comments_with_problem_terms: int = Field(ge=0,le=100)
    by_language: dict[str,dict[str,int]]
    terms_version: str


class StoredComment(VisibleComment):
    id: int
    sample_id: int
    video_id: str
    comment_key: str
    observed_at: str


class SampleSummary(BaseModel):
    model_config = ConfigDict(extra='forbid',strict=True)
    id: int
    command_id: int
    observed_at: str
    target_count: int
    stop_reason: str
    scroll_steps: int
    extractor_version: str
    video_id: str
    signals: CommentSignals
    coverage: dict[str,float]
    diagnostics: list[str]
    comments: list[StoredComment] | None = None


class CommentsResponse(BaseModel):
    model_config = ConfigDict(extra='forbid',strict=True)
    items: list[SampleSummary]
