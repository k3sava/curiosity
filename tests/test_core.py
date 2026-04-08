"""Core tests for curiosity: database, ingestion, search, spaces, export, API routes."""

import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure imports work
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from curiosity.db import CuriosityDB, SCHEMA_SQL
from curiosity.models import Bookmark, Content, Expert


# ── 1. Database Setup ────────────────────────────────────────


class TestDatabaseSetup:
    """Test that init_db creates the expected tables and schema."""

    def test_creates_all_core_tables(self, db):
        tables = {
            row[0]
            for row in db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        expected = {
            "bookmarks",
            "content",
            "experts",
            "bookmark_experts",
            "topics",
            "bookmark_topics",
            "connections",
            "discoveries",
            "domains",
            "digests",
            "sync_log",
            "meta",
        }
        assert expected.issubset(tables), f"Missing tables: {expected - tables}"

    def test_creates_fts_virtual_table(self, db):
        tables = {
            row[0]
            for row in db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "bookmarks_fts" in tables

    def test_schema_version_set(self, db):
        row = db.conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
        assert row is not None
        assert row[0] == "1"

    def test_wal_mode_enabled(self, db):
        mode = db.conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"

    def test_foreign_keys_enabled(self, db):
        fk = db.conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1

    def test_indexes_created(self, db):
        indexes = {
            row[0]
            for row in db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
            ).fetchall()
        }
        expected_indexes = {
            "idx_bookmarks_domain",
            "idx_bookmarks_status",
            "idx_bookmarks_source",
            "idx_bookmarks_added",
            "idx_experts_followed",
            "idx_content_value",
            "idx_content_type",
            "idx_discoveries_trigger",
        }
        assert expected_indexes.issubset(indexes), f"Missing indexes: {expected_indexes - indexes}"


# ── 2. URL Ingestion ─────────────────────────────────────────


class TestIngestion:
    """Test the ingest flow with mocked HTTP calls."""

    def test_insert_bookmark(self, db):
        bm = Bookmark(url="https://example.com/test", title="Test Page", domain="example.com")
        result = db.insert_bookmark(bm)
        assert result.url == "https://example.com/test"
        assert result.title == "Test Page"
        assert result.status == "pending"

    def test_duplicate_url_returns_existing(self, db):
        bm1 = Bookmark(url="https://example.com/dup", title="First", domain="example.com")
        bm2 = Bookmark(url="https://example.com/dup", title="Second", domain="example.com")
        r1 = db.insert_bookmark(bm1)
        r2 = db.insert_bookmark(bm2)
        assert r1.id == r2.id
        assert r2.title == "First"  # returns existing, not the new one

    def test_upsert_content(self, db):
        bm = Bookmark(id="bk-ingest", url="https://example.com/content", domain="example.com")
        db.insert_bookmark(bm)

        content = Content(
            bookmark_id="bk-ingest",
            raw_text="Some article text about positioning.",
            summary="Article about positioning.",
            key_insights=["Insight one", "Insight two"],
            content_type="article",
            learning_value="high",
            word_count=500,
        )
        db.upsert_content(content)

        retrieved = db.get_content("bk-ingest")
        assert retrieved is not None
        assert retrieved.summary == "Article about positioning."
        assert retrieved.key_insights == ["Insight one", "Insight two"]
        assert retrieved.word_count == 500

    def test_update_bookmark_status(self, db):
        bm = Bookmark(id="bk-status", url="https://example.com/status", domain="example.com")
        db.insert_bookmark(bm)
        assert db.get_bookmark("bk-status").status == "pending"

        db.update_bookmark_status("bk-status", "enriched")
        assert db.get_bookmark("bk-status").status == "enriched"

    def test_get_bookmark_by_url(self, db):
        bm = Bookmark(id="bk-url", url="https://example.com/find-me", domain="example.com")
        db.insert_bookmark(bm)

        found = db.get_bookmark_by_url("https://example.com/find-me")
        assert found is not None
        assert found.id == "bk-url"

    def test_get_bookmark_by_url_not_found(self, db):
        assert db.get_bookmark_by_url("https://nonexistent.com") is None

    def test_fetch_url_extracts_content(self):
        """Test the fetch_url function with mocked HTTP."""
        from curiosity.ingestion import fetch_url

        mock_html = """
        <html>
        <head><title>Test Article</title>
        <meta name="description" content="A test article about GTM">
        </head>
        <body>
        <article>
            <p>This is a long enough article body that should pass the 200 character minimum
            threshold for content extraction. We need to make sure there is sufficient text
            here to avoid falling back to the full page text extraction. Adding more content
            to be safe and ensure proper extraction works correctly.</p>
        </article>
        </body>
        </html>
        """

        class FakeResponse:
            status_code = 200
            text = mock_html
            url = "https://example.com/article"

            def raise_for_status(self):
                pass

        fake_resp = FakeResponse()

        class FakeClient:
            def __init__(self, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def get(self, url):
                return fake_resp

        with patch("curiosity.ingestion.httpx.Client", FakeClient):
            result = fetch_url("https://example.com/article")

        assert result["success"] is True
        assert result["page_title"] == "Test Article"
        assert "GTM" in result["meta_description"]
        assert len(result["content"]) > 100


# ── 3. Search (FTS5) ─────────────────────────────────────────


class TestSearch:
    """Test FTS5 search after inserting test data."""

    def test_search_finds_matching_content(self, populated_db):
        results = populated_db.search("positioning")
        assert len(results) >= 1
        urls = [r["url"] for r in results]
        assert "https://example.com/positioning" in urls

    def test_search_finds_by_insight(self, populated_db):
        results = populated_db.search("competitive alternatives")
        assert len(results) >= 1

    def test_search_no_results(self, populated_db):
        results = populated_db.search("xyznonexistentterm123")
        assert len(results) == 0

    def test_search_respects_limit(self, populated_db):
        results = populated_db.search("article", limit=1)
        assert len(results) <= 1

    def test_search_returns_expected_fields(self, populated_db):
        results = populated_db.search("positioning")
        assert len(results) >= 1
        result = results[0]
        assert "url" in result
        assert "title" in result
        assert "summary" in result
        assert "rank" in result


# ── 4. Spaces (_get_dynamic_spaces) ──────────────────────────


class TestSpaces:
    """Test the _get_dynamic_spaces function."""

    def test_returns_list(self, populated_db):
        import ui as ui_module

        # Use the populated_db's connection directly
        spaces = ui_module._get_dynamic_spaces(populated_db.conn)
        assert isinstance(spaces, list)

    def test_space_has_required_keys(self, populated_db):
        import ui as ui_module

        spaces = ui_module._get_dynamic_spaces(populated_db.conn)
        for space in spaces:
            assert "name" in space
            assert "count" in space
            assert space["count"] > 0

    def test_spaces_sorted_by_count_desc(self, populated_db):
        import ui as ui_module

        spaces = ui_module._get_dynamic_spaces(populated_db.conn)
        if len(spaces) >= 2:
            counts = [s["count"] for s in spaces]
            assert counts == sorted(counts, reverse=True)

    def test_mapped_topics_appear_in_named_spaces(self, populated_db):
        """Topics in TOPIC_TO_SPACE should be grouped into named spaces."""
        import ui as ui_module

        # 'positioning' is in SPACES["Marketing & PMM"], so it should appear
        spaces = ui_module._get_dynamic_spaces(populated_db.conn)
        space_names = [s["name"] for s in spaces]
        # positioning maps to "Marketing & PMM"
        if "positioning" in ui_module.TOPIC_TO_SPACE:
            expected_space = ui_module.TOPIC_TO_SPACE["positioning"]
            assert expected_space in space_names


# ── 5. Export ─────────────────────────────────────────────────


class TestExport:
    """Test markdown export produces valid output."""

    def test_export_plain_format(self, populated_db, tmp_path):
        from curiosity.export import export_bookmark

        path = export_bookmark("bk-001", populated_db, tmp_path, format="plain")
        assert path is not None
        assert path.exists()

        md = path.read_text()
        assert "# Obviously Awesome by April Dunford" in md
        assert "https://example.com/positioning" in md
        assert "positioning" in md.lower()
        assert "Context matters more than features" in md

    def test_export_artemis_format(self, populated_db, tmp_path):
        from curiosity.export import export_bookmark

        path = export_bookmark("bk-001", populated_db, tmp_path, format="artemis")
        assert path is not None

        md = path.read_text()
        assert md.startswith("---")
        assert "url:" in md
        assert "title:" in md
        assert "## Summary" in md
        assert "## Key Insights" in md
        assert "## Author" in md
        assert "April Dunford" in md

    def test_export_obsidian_format(self, populated_db, tmp_path):
        from curiosity.export import export_bookmark

        path = export_bookmark("bk-001", populated_db, tmp_path, format="obsidian")
        assert path is not None

        md = path.read_text()
        assert md.startswith("---")
        assert "tags:" in md
        assert "[[" in md  # wiki-links

    def test_export_nonexistent_bookmark(self, populated_db, tmp_path):
        from curiosity.export import export_bookmark

        path = export_bookmark("nonexistent-id", populated_db, tmp_path, format="plain")
        assert path is None

    def test_export_all(self, populated_db, tmp_path):
        from curiosity.export import export_all

        paths = export_all(populated_db, tmp_path, format="plain")
        assert len(paths) >= 2  # bk-001, bk-002, bk-003

    def test_export_all_filtered_by_status(self, populated_db, tmp_path):
        from curiosity.export import export_all

        paths = export_all(populated_db, tmp_path, format="plain", status="enriched")
        assert len(paths) == 2  # only bk-001 and bk-002


# ── 6. API Routes ─────────────────────────────────────────────


class TestAPIRoutes:
    """Test key FastAPI endpoints return 200."""

    def test_home(self, test_client):
        resp = test_client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_library(self, test_client):
        resp = test_client.get("/library")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_settings(self, test_client):
        resp = test_client.get("/settings")
        assert resp.status_code == 200

    def test_health(self, test_client):
        resp = test_client.get("/health")
        assert resp.status_code == 200

    def test_search_api_empty(self, test_client):
        resp = test_client.get("/api/search?q=")
        assert resp.status_code == 200
        data = resp.json()
        assert "bookmarks" in data

    def test_search_api_with_query(self, test_client):
        resp = test_client.get("/api/search?q=test")
        assert resp.status_code == 200
        data = resp.json()
        assert "bookmarks" in data
        assert isinstance(data["bookmarks"], list)

    def test_ingest_no_url(self, test_client):
        resp = test_client.post("/api/ingest", json={"url": ""})
        assert resp.status_code == 400
        assert "error" in resp.json()

    def test_ingest_with_mock(self, test_client):
        import ui as ui_module

        mock_html = "<html><head><title>Mock Page</title></head><body><p>Content here</p></body></html>"

        class FakeResponse:
            status_code = 200
            text = mock_html

        with patch("httpx.get", return_value=FakeResponse()):
            with patch.object(ui_module, "_get_api_key", return_value=""):
                resp = test_client.post(
                    "/api/ingest", json={"url": "https://example.com/api-test"}
                )

        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["title"] == "Mock Page"

    def test_ai_status(self, test_client):
        resp = test_client.get("/api/ai-status")
        assert resp.status_code == 200
        data = resp.json()
        assert "providers" in data

    def test_spaces_page(self, test_client):
        resp = test_client.get("/spaces")
        assert resp.status_code == 200

    def test_topics_page(self, test_client):
        resp = test_client.get("/topics")
        assert resp.status_code == 200

    def test_queue_page(self, test_client):
        resp = test_client.get("/queue")
        assert resp.status_code == 200

    def test_experts_page(self, test_client):
        resp = test_client.get("/experts")
        assert resp.status_code == 200
