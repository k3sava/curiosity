"""Tests for the curiosity web UI (FastAPI app)."""

import os
import tempfile

# Point at a throwaway DB before importing anything that touches sqlite
os.environ["CURIOSITY_DB"] = tempfile.mktemp(suffix=".db")

import sys
from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest

# Make ui.py importable
sys.path.insert(0, str(Path(__file__).parent.parent))

# Patch DB_PATH at module level before the app wires up
import ui as _ui_module

_ui_module.DB_PATH = Path(os.environ["CURIOSITY_DB"])

# Now we can safely import the schema bootstrap from curiosity.db
from src.curiosity.db import SCHEMA_SQL

# Bootstrap the temp database with the core schema + UI tables
import sqlite3

_db = sqlite3.connect(str(_ui_module.DB_PATH))
_db.executescript(SCHEMA_SQL)
_db.close()

from starlette.testclient import TestClient

client = TestClient(_ui_module.app)


# ---- Page render tests ----


def test_home_returns_200():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_library_returns_200():
    resp = client.get("/library")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_settings_returns_200():
    resp = client.get("/settings")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


# ---- Search API tests ----


def test_search_empty_query():
    resp = client.get("/api/search?q=")
    assert resp.status_code == 200
    data = resp.json()
    assert "bookmarks" in data
    assert "notes" in data


def test_search_with_query():
    resp = client.get("/api/search?q=test")
    assert resp.status_code == 200
    data = resp.json()
    assert "bookmarks" in data
    assert isinstance(data["bookmarks"], list)


def test_search_recent():
    resp = client.get("/api/search?q=&recent=3")
    assert resp.status_code == 200
    data = resp.json()
    assert "bookmarks" in data
    assert isinstance(data["bookmarks"], list)


# ---- Ingest API test ----


def test_ingest_url():
    """POST /api/ingest with a URL returns id, status, title."""
    # Mock httpx.get so we don't make real HTTP calls
    mock_html = "<html><head><title>Test Page</title></head><body><p>Hello world</p></body></html>"

    class FakeResponse:
        status_code = 200
        text = mock_html

    with patch("httpx.get", return_value=FakeResponse()):
        with patch.object(_ui_module, "_get_api_key", return_value=""):
            resp = client.post("/api/ingest", json={"url": "https://example.com/test-article"})

    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert "status" in data
    assert "title" in data
    assert data["status"] in ("saved", "exists")
    assert data["title"] == "Test Page"


def test_ingest_no_url():
    resp = client.post("/api/ingest", json={"url": ""})
    assert resp.status_code == 400
    assert resp.json()["error"] == "No URL"


# ---- Settings API tests ----


def test_api_key_save_and_delete():
    # Save a key
    resp = client.post("/api/settings/api-key", json={
        "key": "GEMINI_API_KEY",
        "value": "test-key-12345",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "saved"
    assert data["key"] == "GEMINI_API_KEY"

    # Delete the key (empty value)
    resp = client.post("/api/settings/api-key", json={
        "key": "GEMINI_API_KEY",
        "value": "",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "deleted"


def test_api_key_invalid_name():
    resp = client.post("/api/settings/api-key", json={
        "key": "OPENAI_API_KEY",
        "value": "nope",
    })
    assert resp.status_code == 400


# ---- AI status test ----


def test_ai_status():
    resp = client.get("/api/ai-status")
    assert resp.status_code == 200
    data = resp.json()
    assert "providers" in data
    assert isinstance(data["providers"], list)
