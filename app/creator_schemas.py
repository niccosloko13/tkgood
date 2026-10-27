"""Strict contracts for public profile reads; no generic navigation or action API."""
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from .extraction import video_identity

VERSION = 'tiktok-creator-profile-v1'
COUNTS = ('followers', 'following', 'total_likes', 'video_count')
TEXT_FIELDS = ('display_name', 'bio', 'avatar_url', 'external_link', 'profile_category', 'profile_type')


def profile_identity(value):
    try:
        url = urlsplit(value)
        match = re.fullmatch(r'/@([A-Za-z0-9._]{1,128})/?', url.path)
        if url.scheme != 'https' or url.netloc.lower() not in ('www.tiktok.com', 'tiktok.com') or not match:
            raise ValueError('Expected a public TikTok profile URL')
        username = '@' + match[1].lower()
        return 'https://www.tiktok.com/' + username, username
    except (TypeError, AttributeError):
        raise ValueError('Expected a public TikTok profile URL')


def normalize_count(raw):
    if raw is None:
        return None
    raw = raw.strip()
    # No separator guessing: a bare 1,234 or 1.234 is ambiguous and stays null.
    match = re.fullmatch(r'(\d+)(?:([.,])(\d+))?\s*([KMB])?', raw, re.I)
    if not match or (match[2] and not match[4]):
        return None
    from decimal import Decimal
    value = Decimal(match[1] + ('.' + match[3] if match[3] else ''))
    value *= {'K': 1000, 'M': 1000000, 'B': 1000000000}.get((match[4] or '').upper(), 1)
    return int(value) if value == int(value) and value <= 9007199254740991 else None


def public_link(value):
    url = urlsplit(value)
    if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or len(value)>2048:
        raise ValueError('Expected a public HTTP(S) URL')
    if any(re.search(r'password|access_token|refresh_token|session|authorization|jwt', key, re.I) for key,_ in parse_qsl(url.query)):
        raise ValueError('Sensitive URL parameters are forbidden')
    return urlunsplit((url.scheme, url.netloc, url.path, url.query, ''))


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class CreatorCommand(Strict):
    type: Literal['READ_CREATOR_PROFILE']
    video_url: str = Field(max_length=2048)

    @field_validator('video_url')
    @classmethod
    def canonical(cls, value):
        return video_identity(value)[0]


class ProfileEvidence(Strict):
    value: str | int | None
    raw_value: str | None = Field(default=None, max_length=4000)
    normalized_value: int | None = Field(default=None, ge=0)
    source: Literal['creator_profile'] = 'creator_profile'
    confidence: float = Field(ge=0, le=1)
    method: Literal['semantic_text', 'profile_route', 'visible_href', 'visible_image', 'visible_header_image']
    observed_at: str | None = None
    extractor_version: Literal['tiktok-creator-profile-v1'] = VERSION


class ProfileLink(Strict):
    url: str = Field(max_length=2048)
    label: str | None = Field(default=None, max_length=500)
    source: Literal['creator_profile'] = 'creator_profile'
    confidence: float = .98
    observed_at: str | None = None
    extractor_version: Literal['tiktok-creator-profile-v1'] = VERSION

    @field_validator('url')
    @classmethod
    def safe_url(cls,value):
        return public_link(value)

    @field_validator('confidence')
    @classmethod
    def fixed_confidence(cls,value):
        if value != .98:
            raise ValueError('Visible profile link confidence must be .98')
        return value


class CreatorProfile(Strict):
    username: str = Field(pattern=r'^@[A-Za-z0-9._]{1,128}$')
    profile_url: str = Field(max_length=2048)
    display_name: str | None = Field(default=None, max_length=500)
    bio: str | None = Field(default=None, max_length=4000)
    avatar_url: str | None = Field(default=None, max_length=2048)
    followers: int | None = Field(default=None, ge=0)
    following: int | None = Field(default=None, ge=0)
    total_likes: int | None = Field(default=None, ge=0)
    video_count: int | None = Field(default=None, ge=0)
    external_link: str | None = Field(default=None, max_length=2048)
    profile_category: str | None = Field(default=None, max_length=500)
    profile_type: str | None = Field(default=None, max_length=500)
    links: list[ProfileLink] = Field(default_factory=list, max_length=20)
    raw_visible_text: str = Field(min_length=1, max_length=10000)
    field_evidence: dict[str, ProfileEvidence]
    diagnostics: list[str] = Field(default_factory=list, max_length=20)
    extractor_version: Literal['tiktok-creator-profile-v1'] = VERSION

    @field_validator('profile_url')
    @classmethod
    def canonical(cls,value):
        return profile_identity(value)[0]

    @field_validator('avatar_url','external_link')
    @classmethod
    def optional_url(cls,value):
        return public_link(value) if value is not None else None

    @model_validator(mode='after')
    def provenance(self):
        if profile_identity(self.profile_url)[1] != self.username.lower():
            raise ValueError('Visible username must match the requested profile')
        allowed = ('username','profile_url') + COUNTS + TEXT_FIELDS
        if set(self.field_evidence)-set(allowed) or any(len(d)>500 for d in self.diagnostics):
            raise ValueError('Unknown field or excessive diagnostics')
        for field in allowed:
            value = getattr(self,field)
            evidence = self.field_evidence.get(field)
            if field in COUNTS:
                if evidence is None:
                    if value is not None:
                        raise ValueError('Numeric value requires provenance')
                    continue
                if evidence.method!='semantic_text' or evidence.confidence!=.98 or normalize_count(evidence.raw_value)!=value or evidence.normalized_value!=value:
                    raise ValueError('Count must match its raw semantic evidence')
            elif value is not None:
                method = 'profile_route' if field=='profile_url' else 'visible_href' if field=='external_link' else 'visible_image' if field=='avatar_url' else 'semantic_text'
                confidence = .99 if field in ('username','profile_url') else .98 if field in ('external_link','avatar_url') else .95
                if field=='avatar_url' and evidence is not None and evidence.method=='visible_header_image':
                    method,confidence='visible_header_image',.90
                if evidence is None or evidence.method!=method or evidence.confidence!=confidence:
                    raise ValueError('Field requires deterministic method provenance')
            elif evidence is not None:
                raise ValueError('Missing text fields must not claim evidence')
            if evidence is not None and evidence.value!=value:
                raise ValueError('Field and evidence differ')
        if self.external_link is not None and self.external_link not in {link.url for link in self.links}:
            raise ValueError('External link must be present in the visible links')
        return self


class CreatorSignals(Strict):
    has_external_link: bool
    has_commercial_link: bool
    has_shop_signal: bool
    follower_count: int | None
    total_likes: int | None
    video_count: int | None
    followers_to_video_ratio: float | None
    likes_per_follower_ratio: float | None
    creator_size_bucket: Literal['micro','small','medium','large','mega'] | None
    config_version: str


class CreatorVideo(Strict):
    video_id: str | None
    video_url: str
    caption: str | None
    creator_profile_url: str
    metric_evidence: dict[str, dict | None]
    followers_observed_at: str | None
    views_to_followers_ratio: float | None
    likes_to_followers_ratio: float | None
    comments_to_followers_ratio: float | None
    shares_to_followers_ratio: float | None
    creator_size_bucket: Literal['micro','small','medium','large','mega'] | None
    creator_independence_score: float | None
    score_components: dict[str,float] | None
    formula_version: str
    score_formula: dict[str,float]


class CreatorObservation(CreatorProfile):
    id: int
    command_id: int
    observed_at: str


class CreatorRecord(Strict):
    creator_id: int
    platform: Literal['tiktok']
    username: str
    profile_url: str
    display_name: str | None
    bio: str | None
    avatar_url: str | None
    followers: int | None
    following: int | None
    total_likes: int | None
    video_count: int | None
    external_link: str | None
    profile_category: str | None
    profile_type: str | None
    first_seen_at: str
    last_seen_at: str
    extractor_version: str
    field_evidence: dict[str,ProfileEvidence]
    latest_observation: CreatorObservation | None
    latest_observed_at: str | None
    observation_count: int
    links: list[ProfileLink]
    signals: CreatorSignals
    related_videos: list[CreatorVideo]


class CreatorsResponse(Strict):
    items: list[CreatorRecord]
