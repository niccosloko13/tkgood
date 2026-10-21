from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Literal

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

class MissionCreate(BaseModel):
    market: str = Field(default="US")
    mode: str = Field(default="smart_discovery")
    max_videos: int = Field(default=300, ge=25, le=1000)
    read_comments: bool = True
    capture_evidence: bool = True
    discover_related: bool = True
