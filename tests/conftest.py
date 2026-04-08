"""Shared fixtures for curiosity tests."""

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
# Ensure ui.py is importable
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def tmp_db_path(tmp_path):
    """Return a temporary database file path."""
    return tmp_path / "test_curiosity.db"


@pytest.fixture
def db(tmp_db_path):
    """Create a fresh CuriosityDB on a temp file. Closes after the test."""
    from curiosity.db import CuriosityDB

    database = CuriosityDB(tmp_db_path)
    yield database
    database.close()


@pytest.fixture
def populated_db(db):
    """A CuriosityDB with sample bookmarks, content, topics, and experts."""
    from curiosity.models import Bookmark, Content, Expert

    # Insert bookmarks
    b1 = Bookmark(
        id="bk-001",
        url="https://example.com/positioning",
        title="Obviously Awesome by April Dunford",
        domain="example.com",
        source="manual",
        status="enriched",
    )
    b2 = Bookmark(
        id="bk-002",
        url="https://example.com/gtm-strategy",
        title="GTM Strategy for Series A Startups",
        domain="example.com",
        source="chrome",
        status="enriched",
    )
    b3 = Bookmark(
        id="bk-003",
        url="https://example.com/pending-article",
        title="Pending Article",
        domain="example.com",
        source="manual",
        status="pending",
    )
    db.insert_bookmark(b1)
    db.insert_bookmark(b2)
    db.insert_bookmark(b3)

    # Insert content for b1 and b2
    c1 = Content(
        bookmark_id="bk-001",
        raw_text="Positioning is the act of defining how your product is the best in the world at something.",
        summary="A guide to product positioning frameworks.",
        key_insights=["Context matters more than features", "Competitive alternatives define your category"],
        content_type="article",
        learning_value="high",
        word_count=1500,
        fetched_at="2026-04-01T00:00:00",
        enriched_at="2026-04-01T01:00:00",
    )
    c2 = Content(
        bookmark_id="bk-002",
        raw_text="Go-to-market strategy requires clear ICP definition and messaging alignment.",
        summary="How to build a GTM strategy for early-stage startups.",
        key_insights=["Start with ICP", "Message-market fit before product-market fit"],
        content_type="article",
        learning_value="high",
        word_count=2000,
        fetched_at="2026-04-02T00:00:00",
        enriched_at="2026-04-02T01:00:00",
    )
    db.upsert_content(c1)
    db.upsert_content(c2)

    # Insert topics and link
    t1_id = db.get_or_create_topic("positioning", category="marketing")
    t2_id = db.get_or_create_topic("gtm-strategy", category="marketing")
    db.link_bookmark_topic("bk-001", t1_id)
    db.link_bookmark_topic("bk-002", t2_id)

    # Insert an expert
    expert = Expert(
        id="april-dunford",
        name="April Dunford",
        expertise=["positioning", "b2b-saas"],
        perspective="Category design and competitive positioning",
        home_url="https://aprildunford.com",
    )
    db.upsert_expert(expert)
    db.link_bookmark_expert("bk-001", "april-dunford")

    return db


@pytest.fixture
def test_client(tmp_path):
    """FastAPI TestClient wired to a throwaway database."""
    import ui as ui_module
    from curiosity.db import SCHEMA_SQL

    db_path = tmp_path / "ui_test.db"
    ui_module.DB_PATH = db_path

    # Bootstrap schema
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA_SQL)
    conn.close()

    from starlette.testclient import TestClient

    return TestClient(ui_module.app)
