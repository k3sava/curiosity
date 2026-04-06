"""Pydantic data models for Curiosity."""

from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional
import uuid


def new_id() -> str:
    return str(uuid.uuid4())


def now_iso() -> str:
    return datetime.utcnow().isoformat()


class Bookmark(BaseModel):
    id: str = Field(default_factory=new_id)
    url: str
    final_url: Optional[str] = None
    title: Optional[str] = None
    domain: Optional[str] = None
    source: str = "manual"  # chrome, research_agent, manual, competitor_monitor
    chrome_folder: Optional[str] = None
    added_at: str = Field(default_factory=now_iso)
    chrome_added_at: Optional[str] = None
    status: str = "pending"  # pending, fetched, enriched, failed, dead
    updated_at: Optional[str] = None


class Content(BaseModel):
    bookmark_id: str
    raw_text: Optional[str] = None
    meta_description: Optional[str] = None
    summary: Optional[str] = None
    key_insights: Optional[list[str]] = None  # stored as JSON
    content_type: Optional[str] = None  # article, tutorial, doc, tool, video, etc.
    learning_value: Optional[str] = None  # high, medium, low
    word_count: Optional[int] = None
    fetched_at: Optional[str] = None
    enriched_at: Optional[str] = None


class Expert(BaseModel):
    id: str  # slug: 'april-dunford'
    name: str
    expertise: Optional[list[str]] = None  # JSON array of domains
    perspective: Optional[str] = None
    credentials: Optional[str] = None
    home_url: Optional[str] = None
    followed: bool = False
    created_at: str = Field(default_factory=now_iso)
    updated_at: Optional[str] = None


class Topic(BaseModel):
    id: Optional[int] = None  # auto-increment
    name: str
    category: Optional[str] = None
    bookmark_count: int = 0


class Connection(BaseModel):
    id: Optional[int] = None
    bookmark_a: str
    bookmark_b: str
    connection_type: str  # same_topic, same_author, references, contradicts, extends
    strength: float = 0.5
    explanation: Optional[str] = None
    discovered_at: str = Field(default_factory=now_iso)


class Discovery(BaseModel):
    id: Optional[int] = None
    bookmark_id: str  # the discovered content
    triggered_by: str  # which bookmark triggered discovery
    search_query: Optional[str] = None
    relevance_score: Optional[float] = None
    discovered_at: str = Field(default_factory=now_iso)


class Domain(BaseModel):
    id: str  # slug: 'positioning', 'ai_agents'
    name: str
    keywords: Optional[list[str]] = None
    target_sources: int = 20
    priority: float = 1.0
    search_queries: Optional[list[str]] = None
    updated_at: Optional[str] = None


class EnrichmentResult(BaseModel):
    """Result from Claude API summarization."""
    summary: str
    topics: list[str] = []
    content_type: str = "other"
    learning_value: str = "medium"
    key_insights: list[str] = []
    author_name: Optional[str] = None
    author_slug: Optional[str] = None


class ChromeBookmark(BaseModel):
    """Parsed from Chrome's bookmark export HTML."""
    url: str
    title: str
    folder_path: str = "Uncategorized"
    add_date: Optional[str] = None
    domain: Optional[str] = None
