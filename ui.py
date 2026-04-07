#!/usr/bin/env python3
"""
curiosity — AI-Native Personal Knowledge System
Web UI for browsing an AI-maintained knowledge graph.

Usage: python3 mcp/curiosity/ui.py
Opens at http://localhost:8080
"""

import asyncio
import io
import json
import re
import shutil
import sqlite3
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import feedparser
import httpx
from fastapi import FastAPI, Query, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import uvicorn

VIDEOS_DIR = Path(__file__).parent.parent.parent / "data" / "videos"

BASE_DIR = Path(__file__).parent
DB_PATH = Path(__file__).parent.parent.parent / "data" / "curiosity.db"
ARTEMIS_DB = Path(__file__).parent.parent.parent / "data" / "artemis.db"

app = FastAPI(title="curiosity")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# --- Spaces: curated knowledge areas ---

SPACES = {
    "AI & LLMs": {
        "icon": "◈", "color": "#8b5cf6",
        "topics": [
            "llm-limitations", "multi-agent", "hallucination", "calibration",
            "confidence", "ai-safety", "reasoning", "retrieval-vs-synthesis",
            "formal-verification", "multi-model", "ensemble", "synthesis",
            "self-correction", "overconfidence", "reflexion", "error-correction",
            "self-verification", "planning", "machine-learning", "ai-music",
            "ai-search", "verification", "debate",
        ],
    },
    "Knowledge & PKM": {
        "icon": "◇", "color": "#3b82f6",
        "topics": [
            "knowledge-management", "pkm", "note-taking", "obsidian",
            "knowledge-ui-research", "graph-view", "anytype", "heptabase",
            "trilium", "are-na", "readwise", "knowledge-base",
            "knowledge-graph", "information-architecture", "local-first",
            "reading-apps", "highlighting", "visual-thinking", "whiteboards",
            "markdown", "privacy",
        ],
    },
    "Marketing & PMM": {
        "icon": "▣", "color": "#10b981",
        "topics": [
            "product-marketing", "pmm-career", "marketing-strategy",
            "brand-strategy", "content-marketing", "seo", "keyword-research",
            "targeting", "certification", "professional-development", "frameworks",
            "small-business", "mark-ritson", "positioning", "gtm-strategy",
            "b2b-marketing", "guerrilla-marketing", "customer-marketing",
            "social-proof", "customer-testimonials", "email-templates",
            "content-analytics", "brand-building", "scarcity",
        ],
    },
    "Design & UX": {
        "icon": "△", "color": "#f59e0b",
        "topics": [
            "ui-design", "ux-design", "web-design", "typography",
            "reading-experience", "ui-architecture", "frontend",
            "scrolling-patterns", "page-design", "wireframing",
            "design-tools", "design-agency", "landing-pages", "portfolio",
            "inspiration", "low-code", "browser-extension",
            "helpscout", "documentation",
        ],
    },
    "Dev & Scraping": {
        "icon": "◆", "color": "#ef4444",
        "topics": [
            "selenium", "beautifulsoup", "linkedin-scraping", "linkedin-api",
            "software-engineering", "design-patterns", "typescript",
            "api-architecture", "open-source", "github", "self-hosted",
            "linkedin-data-export", "python-automation", "python-tutorial",
            "web-scraping", "profile-extraction", "ethical-scraping",
            "apify", "scraping-api", "mcp-server", "claude-code", "composio",
            "oauth-automation", "social-media-automation", "social-media-tools",
            "open-source-tools",
        ],
    },
    "Music & Art": {
        "icon": "♫", "color": "#ec4899",
        "topics": [
            "classical-music", "composition", "music-production",
            "stem-separation", "ai-music", "music", "interactive-art",
            "google-experiments", "american-culture", "obituary",
        ],
    },
    "Startups & Strategy": {
        "icon": "◰", "color": "#06b6d4",
        "topics": [
            "startup-strategy", "product-strategy", "compound-startups",
            "founder-advice", "saas-metrics", "fincent", "rippling",
            "product-architecture", "community-platform", "saas-tools",
            "dating-apps",
        ],
    },
    "Work & Career": {
        "icon": "▢", "color": "#84cc16",
        "topics": [
            "remote-work", "distributed-teams", "company-culture",
            "job-board", "automattic", "careers", "async-work", "buffer",
            "collaboration", "productivity-tools", "linkedin",
            "professional-networking", "job-listing", "sales", "marketing",
        ],
    },
    "Reading & Ideas": {
        "icon": "¶", "color": "#f97316",
        "topics": [
            "reading-lists", "blogs", "intellectual-curiosity",
            "matt-mullenweg", "podcast", "smashing-magazine", "semrush",
            "tools",
        ],
    },
    "Home & Life": {
        "icon": "⌂", "color": "#14b8a6",
        "topics": [
            "interior-design", "home-renovation", "vintage-decor", "diy",
        ],
    },
}

# Reverse lookup: topic → space name
TOPIC_TO_SPACE = {}
for space_name, space_data in SPACES.items():
    for topic in space_data["topics"]:
        TOPIC_TO_SPACE[topic] = space_name

BLOCKED_DOMAINS = {"meet.google.com", "app.slack.com", "fincentcom.sharepoint.com"}
BLOCKED_TITLE_PATTERNS = ["applytojob.com", "Career Page"]



# --- Helpers ---

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    # Ensure UI-specific tables exist
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS collections (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            color TEXT DEFAULT '#6E6E73',
            created_at TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS bookmark_collections (
            bookmark_id TEXT REFERENCES bookmarks(id),
            collection_id TEXT REFERENCES collections(id),
            added_at TEXT,
            PRIMARY KEY (bookmark_id, collection_id)
        );
        CREATE TABLE IF NOT EXISTS item_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bookmark_id TEXT REFERENCES bookmarks(id),
            viewed_at TEXT,
            source TEXT DEFAULT 'web_ui'
        );
        CREATE TABLE IF NOT EXISTS notes (
            id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            source TEXT DEFAULT 'web_ui',
            created_at TEXT,
            status TEXT DEFAULT 'raw'
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
            note_id, content, tokenize='porter unicode61'
        );
        CREATE TABLE IF NOT EXISTS rss_feeds (
            id TEXT PRIMARY KEY,
            url TEXT NOT NULL UNIQUE,
            title TEXT,
            last_fetched TEXT,
            fetch_interval_hours INTEGER DEFAULT 6,
            active INTEGER DEFAULT 1,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS automation_rules (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            active INTEGER DEFAULT 1,
            conditions TEXT,
            actions TEXT,
            created_at TEXT,
            run_count INTEGER DEFAULT 0
        );
    """)
    # Schema migrations: add columns if missing
    _add_column_if_missing(conn, "bookmarks", "link_status", "TEXT")
    _add_column_if_missing(conn, "bookmarks", "last_checked", "TEXT")
    _add_column_if_missing(conn, "bookmarks", "video_path", "TEXT")
    _add_column_if_missing(conn, "content", "page_cache", "TEXT")
    _add_column_if_missing(conn, "bookmarks", "read_status", "TEXT DEFAULT 'unread'")
    # P3 columns: screenshot, pdf, js-rendered, cookies
    _add_column_if_missing(conn, "bookmarks", "screenshot_path", "TEXT")
    _add_column_if_missing(conn, "bookmarks", "pdf_path", "TEXT")
    _add_column_if_missing(conn, "bookmarks", "js_rendered", "INTEGER DEFAULT 0")
    _add_column_if_missing(conn, "bookmarks", "cookies", "TEXT")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS cookie_jar (
            id TEXT PRIMARY KEY,
            domain TEXT NOT NULL,
            cookies_json TEXT NOT NULL,
            created_at TEXT
        );
    """)
    # Highlights table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS highlights (
            id TEXT PRIMARY KEY,
            bookmark_id TEXT REFERENCES bookmarks(id),
            text TEXT NOT NULL,
            note TEXT,
            color TEXT DEFAULT 'signal',
            position INTEGER,
            created_at TEXT
        )
    """)
    return conn


def _add_column_if_missing(conn, table, column, col_type):
    """Safely add a column to an existing table."""
    cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        conn.commit()


def get_artemis_db():
    conn = sqlite3.connect(str(ARTEMIS_DB))
    conn.row_factory = sqlite3.Row
    return conn


def parse_json_field(value):
    if not value:
        return []
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return [value] if value else []


def timeago(dt_str):
    if not dt_str:
        return ""
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return str(dt_str)[:10] if dt_str else ""
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now - dt
    if delta.days == 0:
        return "today"
    if delta.days == 1:
        return "yesterday"
    if delta.days < 7:
        return f"{delta.days}d ago"
    if delta.days < 30:
        return f"{delta.days // 7}w ago"
    if delta.days < 365:
        return f"{delta.days // 30}mo ago"
    return f"{delta.days // 365}y ago"


def is_blocked(domain, title):
    if domain in BLOCKED_DOMAINS:
        return True
    if not title:
        return False
    return any(p in title for p in BLOCKED_TITLE_PATTERNS)


def get_bookmark_space(db, bookmark_id):
    """Get the primary space for a bookmark based on its topics."""
    topics = db.execute("""
        SELECT t.name FROM bookmark_topics bt
        JOIN topics t ON bt.topic_id = t.id
        WHERE bt.bookmark_id = ?
    """, (bookmark_id,)).fetchall()
    for t in topics:
        if t["name"] in TOPIC_TO_SPACE:
            return TOPIC_TO_SPACE[t["name"]]
    return None


def get_bookmark_spaces(db, bookmark_id):
    """Get all spaces for a bookmark."""
    topics = db.execute("""
        SELECT t.name FROM bookmark_topics bt
        JOIN topics t ON bt.topic_id = t.id
        WHERE bt.bookmark_id = ?
    """, (bookmark_id,)).fetchall()
    spaces = set()
    for t in topics:
        if t["name"] in TOPIC_TO_SPACE:
            spaces.add(TOPIC_TO_SPACE[t["name"]])
    return list(spaces)


def blocked_filter_sql():
    """SQL conditions to exclude blocked content."""
    domain_placeholders = ",".join(f"'{d}'" for d in BLOCKED_DOMAINS)
    conditions = [f"b.domain NOT IN ({domain_placeholders})"]
    for pat in BLOCKED_TITLE_PATTERNS:
        conditions.append(f"b.title NOT LIKE '%{pat}%'")
    conditions.append("b.title IS NOT NULL")
    conditions.append("b.title != ''")
    conditions.append("b.title != b.url")
    return " AND ".join(conditions)


def space_topic_ids(db, space_name):
    """Get topic IDs belonging to a space."""
    if space_name not in SPACES:
        return []
    topic_names = SPACES[space_name]["topics"]
    if not topic_names:
        return []
    placeholders = ",".join("?" * len(topic_names))
    rows = db.execute(
        f"SELECT id FROM topics WHERE name IN ({placeholders})", topic_names
    ).fetchall()
    return [r["id"] for r in rows]


# Register template helpers
templates.env.filters["parse_json"] = parse_json_field
templates.env.filters["timeago"] = timeago
templates.env.globals["SPACES"] = SPACES
templates.env.globals["quote"] = quote


# --- Pages ---

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    db = get_db()
    block_sql = blocked_filter_sql()

    # Compute space counts + previews
    spaces_data = []
    for name, sdata in SPACES.items():
        topic_ids = space_topic_ids(db, name)
        if not topic_ids:
            spaces_data.append({"name": name, **sdata, "count": 0, "previews": []})
            continue
        placeholders = ",".join("?" * len(topic_ids))
        count = db.execute(f"""
            SELECT COUNT(DISTINCT bt.bookmark_id) FROM bookmark_topics bt
            JOIN bookmarks b ON bt.bookmark_id = b.id
            WHERE bt.topic_id IN ({placeholders}) AND b.status = 'enriched'
            AND {block_sql}
        """, topic_ids).fetchone()[0]
        previews = db.execute(f"""
            SELECT DISTINCT b.title FROM bookmark_topics bt
            JOIN bookmarks b ON bt.bookmark_id = b.id
            WHERE bt.topic_id IN ({placeholders}) AND b.status = 'enriched'
            AND {block_sql}
            ORDER BY b.added_at DESC LIMIT 2
        """, topic_ids).fetchall()
        spaces_data.append({
            "name": name, **sdata, "count": count,
            "previews": [p["title"] for p in previews],
        })
    # Sort by count desc, filter out empties
    spaces_data = [s for s in spaces_data if s["count"] > 0]
    spaces_data.sort(key=lambda s: s["count"], reverse=True)

    # Picked for you: high-value items not yet viewed
    picked = db.execute(f"""
        SELECT b.id, b.title, b.domain, b.added_at, c.summary, c.learning_value
        FROM bookmarks b
        JOIN content c ON b.id = c.bookmark_id
        WHERE b.status = 'enriched' AND c.learning_value = 'high'
        AND {block_sql}
        AND b.id NOT IN (SELECT DISTINCT bookmark_id FROM item_views)
        ORDER BY b.added_at DESC LIMIT 3
    """).fetchall()
    # Fallback to medium if no high-value unviewed
    if not picked:
        picked = db.execute(f"""
            SELECT b.id, b.title, b.domain, b.added_at, c.summary, c.learning_value
            FROM bookmarks b
            JOIN content c ON b.id = c.bookmark_id
            WHERE b.status = 'enriched' AND c.learning_value = 'medium'
            AND {block_sql}
            AND b.id NOT IN (SELECT DISTINCT bookmark_id FROM item_views)
            ORDER BY RANDOM() LIMIT 3
        """).fetchall()

    # Recently visited (from item_views)
    visited = db.execute(f"""
        SELECT DISTINCT b.id, b.title, b.domain, MAX(iv.viewed_at) as last_viewed
        FROM item_views iv
        JOIN bookmarks b ON iv.bookmark_id = b.id
        WHERE iv.viewed_at > datetime('now', '-7 days')
        AND {block_sql}
        GROUP BY b.id
        ORDER BY last_viewed DESC LIMIT 8
    """).fetchall()

    # Fresh: last 5 enriched
    fresh = db.execute(f"""
        SELECT b.id, b.title, b.domain, b.added_at
        FROM bookmarks b
        WHERE b.status = 'enriched' AND {block_sql}
        ORDER BY b.added_at DESC LIMIT 5
    """).fetchall()

    # Dashboard stats
    total_all = db.execute("SELECT COUNT(*) FROM bookmarks").fetchone()[0]
    total_enriched = db.execute(f"""
        SELECT COUNT(*) FROM bookmarks b WHERE b.status = 'enriched' AND {block_sql}
    """).fetchone()[0]
    enriched_pct = round(total_enriched / total_all * 100) if total_all else 0
    high_value_count = db.execute(f"""
        SELECT COUNT(*) FROM bookmarks b
        JOIN content c ON b.id = c.bookmark_id
        WHERE c.learning_value = 'high' AND {block_sql}
    """).fetchone()[0]
    this_week_count = db.execute(f"""
        SELECT COUNT(*) FROM bookmarks b
        WHERE b.status = 'enriched' AND b.added_at > datetime('now', '-7 days')
        AND {block_sql}
    """).fetchone()[0]

    # Reading streak
    view_dates = db.execute("""
        SELECT DISTINCT DATE(viewed_at) as d FROM item_views ORDER BY d DESC
    """).fetchall()
    streak = 0
    if view_dates:
        from datetime import date, timedelta
        today = date.today()
        for i in range(len(view_dates)):
            check = today - timedelta(days=i)
            if str(check) == view_dates[i]["d"] if i < len(view_dates) else False:
                streak += 1
            else:
                break

    # Trending topics (most viewed this week)
    trending = db.execute("""
        SELECT t.name, COUNT(DISTINCT iv.bookmark_id) as views
        FROM item_views iv
        JOIN bookmark_topics bt ON iv.bookmark_id = bt.bookmark_id
        JOIN topics t ON bt.topic_id = t.id
        WHERE iv.viewed_at > datetime('now', '-7 days')
        GROUP BY t.id ORDER BY views DESC LIMIT 5
    """).fetchall()

    # Top domains
    top_domains = db.execute(f"""
        SELECT domain, COUNT(*) as cnt FROM bookmarks b
        WHERE b.status = 'enriched' AND {block_sql}
        GROUP BY domain ORDER BY cnt DESC LIMIT 5
    """).fetchall()

    stats = {
        "total": total_enriched,
        "total_all": total_all,
        "enriched_pct": enriched_pct,
        "high_value": high_value_count,
        "this_week": this_week_count,
        "streak": streak,
    }

    db.close()
    return templates.TemplateResponse("home.html", {
        "request": request,
        "spaces": spaces_data,
        "picked": picked,
        "visited": visited,
        "fresh": fresh,
        "stats": stats,
        "trending": trending,
        "top_domains": top_domains,
    })


@app.get("/library", response_class=HTMLResponse)
async def library(
    request: Request,
    space: str = Query(None),
    domain: str = Query(None),
    sort: str = Query("date"),
    read_status: str = Query(None),
):
    db = get_db()
    block_sql = blocked_filter_sql()
    conditions = [f"b.status = 'enriched'", block_sql]
    params = []

    if space and space in SPACES:
        topic_ids = space_topic_ids(db, space)
        if topic_ids:
            placeholders = ",".join("?" * len(topic_ids))
            conditions.append(f"b.id IN (SELECT bookmark_id FROM bookmark_topics WHERE topic_id IN ({placeholders}))")
            params.extend(topic_ids)

    if domain:
        conditions.append("b.domain = ?")
        params.append(domain)

    if read_status and read_status in ('unread', 'reading', 'read'):
        conditions.append("COALESCE(b.read_status, 'unread') = ?")
        params.append(read_status)

    order = {
        "date": "b.added_at DESC",
        "value": "CASE c.learning_value WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, b.added_at DESC",
        "title": "b.title ASC",
    }.get(sort, "b.added_at DESC")

    where = " AND ".join(conditions)
    bookmarks = db.execute(f"""
        SELECT b.id, b.title, b.domain, b.url, b.added_at, b.link_status,
               c.summary, c.learning_value, c.content_type,
               COALESCE(b.read_status, 'unread') as read_status
        FROM bookmarks b
        LEFT JOIN content c ON b.id = c.bookmark_id
        WHERE {where}
        ORDER BY {order}
        LIMIT 200
    """, params).fetchall()

    # Domains for filter
    domains = db.execute(f"""
        SELECT domain, COUNT(*) as cnt FROM bookmarks b
        WHERE b.status = 'enriched' AND {block_sql}
        GROUP BY domain HAVING cnt >= 3 ORDER BY cnt DESC LIMIT 20
    """).fetchall()

    db.close()
    return templates.TemplateResponse("library.html", {
        "request": request,
        "bookmarks": bookmarks,
        "domains": domains,
        "current_space": space,
        "current_domain": domain,
        "current_sort": sort,
        "current_read_status": read_status,
    })


@app.get("/space/{name}", response_class=HTMLResponse)
async def space_view(request: Request, name: str):
    db = get_db()
    block_sql = blocked_filter_sql()

    # Find the space
    space_data = None
    for sname, sdata in SPACES.items():
        if sname == name:
            space_data = {"name": sname, **sdata}
            break
    if not space_data:
        db.close()
        return HTMLResponse("<h1>Space not found</h1>", status_code=404)

    topic_ids = space_topic_ids(db, name)
    items = []
    if topic_ids:
        placeholders = ",".join("?" * len(topic_ids))
        items = db.execute(f"""
            SELECT DISTINCT b.id, b.title, b.domain, b.url, b.added_at,
                   c.summary, c.learning_value
            FROM bookmark_topics bt
            JOIN bookmarks b ON bt.bookmark_id = b.id
            LEFT JOIN content c ON b.id = c.bookmark_id
            WHERE bt.topic_id IN ({placeholders}) AND b.status = 'enriched'
            AND {block_sql}
            ORDER BY b.added_at DESC
        """, topic_ids).fetchall()

    # Viewed item IDs for marking
    viewed_ids = set()
    if items:
        item_ids = [i["id"] for i in items]
        id_placeholders = ",".join("?" * len(item_ids))
        viewed_rows = db.execute(
            f"SELECT DISTINCT bookmark_id FROM item_views WHERE bookmark_id IN ({id_placeholders})",
            item_ids
        ).fetchall()
        viewed_ids = {r["bookmark_id"] for r in viewed_rows}

    # Related spaces: other spaces sharing bookmarks with this space
    related = []
    if topic_ids:
        bookmark_ids = [i["id"] for i in items]
        if bookmark_ids:
            bk_placeholders = ",".join("?" * len(bookmark_ids))
            related_topics = db.execute(f"""
                SELECT t.name, COUNT(DISTINCT bt.bookmark_id) as shared
                FROM bookmark_topics bt
                JOIN topics t ON bt.topic_id = t.id
                WHERE bt.bookmark_id IN ({bk_placeholders})
                AND t.name NOT IN ({",".join("?" * len(space_data["topics"]))})
                GROUP BY t.name ORDER BY shared DESC LIMIT 20
            """, bookmark_ids + space_data["topics"]).fetchall()
            # Map topics to spaces
            related_spaces = {}
            for rt in related_topics:
                rs = TOPIC_TO_SPACE.get(rt["name"])
                if rs and rs != name:
                    related_spaces[rs] = related_spaces.get(rs, 0) + rt["shared"]
            related = sorted(related_spaces.items(), key=lambda x: x[1], reverse=True)[:5]

    # Experts in this space
    experts = []
    if topic_ids:
        placeholders = ",".join("?" * len(topic_ids))
        experts = db.execute(f"""
            SELECT DISTINCT e.id, e.name, e.expertise
            FROM bookmark_topics bt
            JOIN bookmark_experts be ON bt.bookmark_id = be.bookmark_id
            JOIN experts e ON be.expert_id = e.id
            WHERE bt.topic_id IN ({placeholders})
            LIMIT 10
        """, topic_ids).fetchall()

    db.close()
    return templates.TemplateResponse("space.html", {
        "request": request,
        "space": space_data,
        "items": items,
        "viewed_ids": viewed_ids,
        "related": related,
        "experts": experts,
    })


# Keep /topic/ as redirect to space
@app.get("/topic/{name}", response_class=HTMLResponse)
async def topic_redirect(request: Request, name: str):
    space = TOPIC_TO_SPACE.get(name)
    if space:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(f"/space/{quote(space)}", status_code=302)
    # Fallback: show as a mini-space
    db = get_db()
    topic = db.execute("SELECT * FROM topics WHERE name = ?", (name,)).fetchone()
    if not topic:
        db.close()
        return HTMLResponse("<h1>Topic not found</h1>", status_code=404)
    block_sql = blocked_filter_sql()
    items = db.execute(f"""
        SELECT b.id, b.title, b.domain, b.added_at, c.summary, c.learning_value
        FROM bookmark_topics bt
        JOIN bookmarks b ON bt.bookmark_id = b.id
        LEFT JOIN content c ON b.id = c.bookmark_id
        WHERE bt.topic_id = ? AND b.status = 'enriched' AND {block_sql}
        ORDER BY b.added_at DESC
    """, (topic["id"],)).fetchall()
    db.close()
    return templates.TemplateResponse("space.html", {
        "request": request,
        "space": {"name": name, "icon": "·", "color": "#6b7280", "topics": [name]},
        "items": items,
        "viewed_ids": set(),
        "related": [],
        "experts": [],
    })


@app.get("/item/{item_id}", response_class=HTMLResponse)
async def item_view(request: Request, item_id: str):
    db = get_db()
    block_sql = blocked_filter_sql()

    # Check if it's a note
    if item_id.startswith("note:"):
        note = db.execute("SELECT * FROM notes WHERE id = ?", (item_id[5:],)).fetchone()
        if not note:
            db.close()
            return HTMLResponse("<h1>Not found</h1>", status_code=404)
        db.close()
        return templates.TemplateResponse("item.html", {
            "request": request,
            "item_type": "note",
            "item": note,
            "summary": note["content"],
            "insights": [],
            "spaces": [],
            "expert": None,
            "more_items": [],
        })

    # Bookmark
    bookmark = db.execute("""
        SELECT b.*, c.summary, c.key_insights, c.content_type,
               c.learning_value, c.word_count, b.video_path
        FROM bookmarks b
        LEFT JOIN content c ON b.id = c.bookmark_id
        WHERE b.id = ?
    """, (item_id,)).fetchone()

    if not bookmark:
        db.close()
        return HTMLResponse("<h1>Not found</h1>", status_code=404)

    # Record view
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        "INSERT INTO item_views (bookmark_id, viewed_at, source) VALUES (?, ?, 'web_ui')",
        (item_id, now),
    )
    db.commit()

    # Get spaces for this bookmark
    topics = db.execute("""
        SELECT t.name FROM bookmark_topics bt
        JOIN topics t ON bt.topic_id = t.id
        WHERE bt.bookmark_id = ?
    """, (item_id,)).fetchall()
    topic_names = [t["name"] for t in topics]
    item_spaces = []
    seen = set()
    for t in topic_names:
        s = TOPIC_TO_SPACE.get(t)
        if s and s not in seen:
            item_spaces.append({"name": s, **SPACES[s]})
            seen.add(s)

    insights = parse_json_field(bookmark["key_insights"]) if bookmark["key_insights"] else []

    expert = db.execute("""
        SELECT e.* FROM bookmark_experts be
        JOIN experts e ON be.expert_id = e.id
        WHERE be.bookmark_id = ?
    """, (item_id,)).fetchone()

    # Check if cached copy exists
    has_cache = bool(db.execute(
        "SELECT 1 FROM content WHERE bookmark_id = ? AND page_cache IS NOT NULL",
        (item_id,),
    ).fetchone())

    # "More in [primary space]" — 3 items from the same space
    more_items = []
    if item_spaces:
        primary = item_spaces[0]["name"]
        t_ids = space_topic_ids(db, primary)
        if t_ids:
            placeholders = ",".join("?" * len(t_ids))
            more_items = db.execute(f"""
                SELECT DISTINCT b.id, b.title, b.domain
                FROM bookmark_topics bt
                JOIN bookmarks b ON bt.bookmark_id = b.id
                WHERE bt.topic_id IN ({placeholders})
                AND b.id != ? AND b.status = 'enriched' AND {block_sql}
                ORDER BY b.added_at DESC LIMIT 3
            """, t_ids + [item_id]).fetchall()

    # Highlights for this bookmark
    highlights = db.execute(
        "SELECT * FROM highlights WHERE bookmark_id = ? ORDER BY created_at DESC",
        (item_id,),
    ).fetchall()

    # YouTube video info
    is_youtube = _is_youtube(bookmark["url"])
    video_path = bookmark["video_path"] if bookmark["video_path"] else None
    video_ready = video_path and Path(video_path).exists() if video_path else False
    has_ytdlp = bool(shutil.which("yt-dlp"))

    db.close()
    return templates.TemplateResponse("item.html", {
        "request": request,
        "item_type": "bookmark",
        "item": bookmark,
        "summary": bookmark["summary"] or "",
        "insights": insights,
        "spaces": item_spaces,
        "expert": expert,
        "more_items": more_items,
        "has_cache": has_cache,
        "highlights": highlights,
        "read_status": bookmark["read_status"] or "unread",
        "is_youtube": is_youtube,
        "video_ready": video_ready,
        "video_path": video_path,
        "has_ytdlp": has_ytdlp,
    })


@app.get("/spaces", response_class=HTMLResponse)
async def spaces_overview(request: Request):
    db = get_db()
    block_sql = blocked_filter_sql()
    spaces_data = []
    for name, sdata in SPACES.items():
        topic_ids = space_topic_ids(db, name)
        if not topic_ids:
            continue
        placeholders = ",".join("?" * len(topic_ids))
        count = db.execute(f"""
            SELECT COUNT(DISTINCT bt.bookmark_id) FROM bookmark_topics bt
            JOIN bookmarks b ON bt.bookmark_id = b.id
            WHERE bt.topic_id IN ({placeholders}) AND b.status = 'enriched'
            AND {block_sql}
        """, topic_ids).fetchone()[0]
        if count == 0:
            continue
        previews = db.execute(f"""
            SELECT DISTINCT b.title FROM bookmark_topics bt
            JOIN bookmarks b ON bt.bookmark_id = b.id
            WHERE bt.topic_id IN ({placeholders}) AND b.status = 'enriched'
            AND {block_sql}
            ORDER BY b.added_at DESC LIMIT 3
        """, topic_ids).fetchall()
        spaces_data.append({
            "name": name, **sdata, "count": count,
            "previews": [p["title"] for p in previews],
        })
    spaces_data.sort(key=lambda s: s["count"], reverse=True)
    db.close()
    return templates.TemplateResponse("spaces.html", {
        "request": request,
        "spaces": spaces_data,
    })


# Keep /topics as redirect
@app.get("/topics", response_class=HTMLResponse)
async def topics_redirect(request: Request):
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/spaces", status_code=302)


@app.get("/queue", response_class=HTMLResponse)
async def queue(request: Request, show_all: str = Query(None)):
    db = get_db()
    block_sql = blocked_filter_sql()
    read_filter = "" if show_all else "AND COALESCE(b.read_status, 'unread') = 'unread'"
    items = db.execute(f"""
        SELECT b.id, b.title, b.domain, b.url, b.added_at, c.summary,
               c.learning_value, c.word_count,
               COALESCE(b.read_status, 'unread') as read_status
        FROM bookmarks b
        JOIN content c ON b.id = c.bookmark_id
        WHERE b.status = 'enriched' AND c.learning_value = 'high'
        AND {block_sql} {read_filter}
        ORDER BY b.added_at DESC
        LIMIT 100
    """).fetchall()
    db.close()
    return templates.TemplateResponse("queue.html", {
        "request": request,
        "items": items,
        "show_all": bool(show_all),
    })


@app.get("/experts", response_class=HTMLResponse)
async def experts_list(request: Request):
    db = get_db()
    experts = db.execute("""
        SELECT e.*, COUNT(be.bookmark_id) as item_count
        FROM experts e
        LEFT JOIN bookmark_experts be ON e.id = be.expert_id
        GROUP BY e.id
        ORDER BY item_count DESC, e.name
    """).fetchall()
    db.close()
    return templates.TemplateResponse("experts.html", {
        "request": request,
        "experts": experts,
    })


@app.get("/expert/{expert_id}", response_class=HTMLResponse)
async def expert_detail(request: Request, expert_id: str):
    db = get_db()
    expert = db.execute("SELECT * FROM experts WHERE id = ?", (expert_id,)).fetchone()
    if not expert:
        db.close()
        return HTMLResponse("<h1>Expert not found</h1>", status_code=404)
    block_sql = blocked_filter_sql()
    items = db.execute(f"""
        SELECT b.id, b.title, b.domain, b.added_at, c.summary, c.learning_value
        FROM bookmark_experts be
        JOIN bookmarks b ON be.bookmark_id = b.id
        LEFT JOIN content c ON b.id = c.bookmark_id
        WHERE be.expert_id = ? AND {block_sql}
        ORDER BY b.added_at DESC
    """, (expert_id,)).fetchall()
    db.close()
    return templates.TemplateResponse("expert.html", {
        "request": request,
        "expert": expert,
        "items": items,
    })


@app.get("/digest", response_class=HTMLResponse)
async def digest(request: Request):
    db = get_db()
    block_sql = blocked_filter_sql()
    weeks = db.execute(f"""
        SELECT strftime('%Y-W%W', added_at) as week,
               COUNT(*) as count,
               MIN(added_at) as week_start
        FROM bookmarks b WHERE b.status = 'enriched' AND {block_sql}
        GROUP BY week ORDER BY week DESC LIMIT 12
    """).fetchall()

    week_items = {}
    for w in weeks:
        items = db.execute(f"""
            SELECT b.id, b.title, b.domain, b.added_at, c.learning_value, c.summary
            FROM bookmarks b
            LEFT JOIN content c ON b.id = c.bookmark_id
            WHERE strftime('%Y-W%W', b.added_at) = ? AND b.status = 'enriched'
            AND {block_sql}
            ORDER BY CASE c.learning_value WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END
            LIMIT 10
        """, (w["week"],)).fetchall()
        week_items[w["week"]] = items

    db.close()
    return templates.TemplateResponse("digest.html", {
        "request": request,
        "weeks": weeks,
        "week_items": week_items,
    })


@app.get("/graph", response_class=HTMLResponse)
async def graph_view(request: Request):
    return templates.TemplateResponse("graph.html", {"request": request})


@app.get("/connections", response_class=HTMLResponse)
async def connections_view(request: Request):
    db = get_db()
    conns = db.execute("""
        SELECT c.*, b1.title as title_a, b1.domain as domain_a,
               b2.title as title_b, b2.domain as domain_b
        FROM connections c
        JOIN bookmarks b1 ON c.bookmark_a = b1.id
        JOIN bookmarks b2 ON c.bookmark_b = b2.id
        ORDER BY c.strength DESC, c.discovered_at DESC
        LIMIT 100
    """).fetchall()
    db.close()
    return templates.TemplateResponse("connections.html", {
        "request": request,
        "connections": conns,
    })


@app.get("/projects", response_class=HTMLResponse)
async def projects_view(request: Request):
    adb = get_artemis_db()
    projects = adb.execute("""
        SELECT * FROM projects ORDER BY
        CASE status WHEN 'active' THEN 0 WHEN 'pending' THEN 1 ELSE 2 END,
        updated DESC
    """).fetchall()

    project_tasks = {}
    for p in projects:
        tasks = adb.execute("""
            SELECT * FROM tasks WHERE project_id = ?
            ORDER BY CASE status WHEN 'in_progress' THEN 0 WHEN 'queued' THEN 1 ELSE 2 END
        """, (p["id"],)).fetchall()
        project_tasks[p["id"]] = tasks

    adb.close()
    return templates.TemplateResponse("projects.html", {
        "request": request,
        "projects": projects,
        "project_tasks": project_tasks,
    })


@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})


# --- API endpoints ---

@app.get("/api/search")
async def api_search(q: str = Query(..., min_length=1)):
    db = get_db()
    block_sql = blocked_filter_sql()
    results = {"bookmarks": [], "notes": []}

    try:
        rows = db.execute(f"""
            SELECT b.id, b.title, b.domain, b.url, c.summary, c.learning_value,
                   snippet(bookmarks_fts, 2, '<mark>', '</mark>', '...', 40) as snippet
            FROM bookmarks_fts fts
            JOIN bookmarks b ON fts.bookmark_id = b.id
            LEFT JOIN content c ON b.id = c.bookmark_id
            WHERE bookmarks_fts MATCH ? AND {block_sql}
            ORDER BY rank LIMIT 20
        """, (q,)).fetchall()
        results["bookmarks"] = [dict(r) for r in rows]
    except Exception:
        rows = db.execute(f"""
            SELECT b.id, b.title, b.domain, b.url, c.summary, c.learning_value
            FROM bookmarks b
            LEFT JOIN content c ON b.id = c.bookmark_id
            WHERE (b.title LIKE ? OR c.summary LIKE ?) AND {block_sql}
            ORDER BY b.added_at DESC LIMIT 20
        """, (f"%{q}%", f"%{q}%")).fetchall()
        results["bookmarks"] = [dict(r) for r in rows]

    try:
        note_rows = db.execute("""
            SELECT n.id, n.content, n.source, n.created_at,
                   snippet(notes_fts, 1, '<mark>', '</mark>', '...', 40) as snippet
            FROM notes_fts nfts
            JOIN notes n ON nfts.note_id = n.id
            WHERE notes_fts MATCH ?
            ORDER BY rank LIMIT 10
        """, (q,)).fetchall()
        results["notes"] = [dict(r) for r in note_rows]
    except Exception:
        note_rows = db.execute("""
            SELECT id, content, source, created_at FROM notes
            WHERE content LIKE ? LIMIT 10
        """, (f"%{q}%",)).fetchall()
        results["notes"] = [dict(r) for r in note_rows]

    try:
        adb = get_artemis_db()
        lesson_rows = adb.execute("""
            SELECT id, date, lesson, source FROM lessons
            WHERE lesson LIKE ? ORDER BY date DESC LIMIT 10
        """, (f"%{q}%",)).fetchall()
        results["lessons"] = [dict(r) for r in lesson_rows]
        adb.close()
    except Exception:
        results["lessons"] = []

    db.close()
    return JSONResponse(results)


@app.post("/api/note")
async def api_create_note(request: Request):
    body = await request.json()
    content = body.get("content", "").strip()
    source = body.get("source", "search_bar")
    if not content:
        return JSONResponse({"error": "Empty note"}, status_code=400)

    note_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    db = get_db()
    db.execute(
        "INSERT INTO notes (id, content, source, created_at, status) VALUES (?, ?, ?, ?, 'raw')",
        (note_id, content, source, now),
    )
    db.execute("INSERT INTO notes_fts (note_id, content) VALUES (?, ?)", (note_id, content))
    db.commit()
    db.close()

    return JSONResponse({"id": note_id, "status": "saved"})


@app.post("/api/ingest")
async def api_ingest_url(request: Request):
    body = await request.json()
    url = body.get("url", "").strip()
    if not url:
        return JSONResponse({"error": "No URL"}, status_code=400)

    bookmark_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    domain = url.replace("https://", "").replace("http://", "").split("/")[0]

    db = get_db()
    existing = db.execute("SELECT id FROM bookmarks WHERE url = ?", (url,)).fetchone()
    if existing:
        db.close()
        return JSONResponse({"id": existing["id"], "status": "exists"})

    db.execute(
        "INSERT INTO bookmarks (id, url, title, domain, source, added_at, status) VALUES (?, ?, ?, ?, 'web_ui', ?, 'pending')",
        (bookmark_id, url, url, domain, now),
    )
    db.commit()
    run_rules_on_bookmark(db, bookmark_id)
    is_yt = _is_youtube(url)
    db.close()
    return JSONResponse({"id": bookmark_id, "status": "pending", "is_youtube": is_yt})


@app.post("/api/chat")
async def api_chat(request: Request):
    """Search knowledge base and format results as a conversational answer."""
    body = await request.json()
    question = body.get("question", "").strip()
    if not question:
        return JSONResponse({"error": "No question provided"}, status_code=400)

    db = get_db()
    block_sql = blocked_filter_sql()
    results = []

    # Try FTS5 first, fall back to LIKE
    try:
        rows = db.execute(f"""
            SELECT b.id, b.title, b.domain, b.url, b.added_at,
                   c.summary, c.key_insights, c.learning_value
            FROM bookmarks_fts fts
            JOIN bookmarks b ON fts.bookmark_id = b.id
            LEFT JOIN content c ON b.id = c.bookmark_id
            WHERE bookmarks_fts MATCH ? AND {block_sql}
            ORDER BY rank LIMIT 5
        """, (question,)).fetchall()
        results = [dict(r) for r in rows]
    except Exception:
        rows = db.execute(f"""
            SELECT b.id, b.title, b.domain, b.url, b.added_at,
                   c.summary, c.key_insights, c.learning_value
            FROM bookmarks b
            LEFT JOIN content c ON b.id = c.bookmark_id
            WHERE (b.title LIKE ? OR c.summary LIKE ?) AND {block_sql}
            ORDER BY b.added_at DESC LIMIT 5
        """, (f"%{question}%", f"%{question}%")).fetchall()
        results = [dict(r) for r in rows]

    db.close()

    if not results:
        return JSONResponse({
            "answer": "Nothing in your knowledge base matches this yet. Try /read <url> to add relevant content.",
            "sources": [],
            "count": 0,
        })

    # Build sources with first key insight
    sources = []
    for r in results:
        insights = parse_json_field(r.get("key_insights"))
        first_insight = insights[0] if insights else None
        sources.append({
            "id": r["id"],
            "title": r.get("title") or "Untitled",
            "domain": r.get("domain") or "",
            "summary": (r.get("summary") or "")[:200],
            "insight": first_insight,
            "learning_value": r.get("learning_value"),
        })

    topic = question.rstrip("?").strip()
    answer = f"Found {len(sources)} relevant item{'s' if len(sources) != 1 else ''} about \"{topic}\":"

    return JSONResponse({
        "answer": answer,
        "sources": sources,
        "count": len(sources),
    })


@app.post("/api/upload")
async def api_upload_pdf(file: UploadFile = File(...)):
    """Upload a PDF and create a bookmark from its text content."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return JSONResponse(
            {"error": "Only PDF files are supported"},
            status_code=400,
        )

    try:
        from PyPDF2 import PdfReader

        contents = await file.read()
        reader = PdfReader(io.BytesIO(contents))
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

        if not text_parts:
            return JSONResponse(
                {"error": "Could not extract text from PDF. It may be image-based."},
                status_code=422,
            )

        raw_text = "\n\n".join(text_parts)
        word_count = len(raw_text.split())
    except ImportError:
        return JSONResponse(
            {"error": "PyPDF2 is not installed. Run: pip install PyPDF2"},
            status_code=500,
        )
    except Exception as e:
        return JSONResponse(
            {"error": f"Failed to read PDF: {str(e)}"},
            status_code=422,
        )

    bookmark_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    filename = file.filename
    title = filename.replace(".pdf", "").replace(".PDF", "").replace("-", " ").replace("_", " ")

    db = get_db()
    db.execute(
        "INSERT INTO bookmarks (id, url, title, domain, source, added_at, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (bookmark_id, f"file://{filename}", title, "local", "upload", now, "fetched"),
    )
    db.execute(
        "INSERT OR REPLACE INTO content (bookmark_id, raw_text, word_count) VALUES (?, ?, ?)",
        (bookmark_id, raw_text, word_count),
    )
    db.commit()
    db.close()

    return JSONResponse({
        "id": bookmark_id,
        "title": title,
        "word_count": word_count,
        "status": "uploaded",
    })


@app.get("/api/graph")
async def api_graph():
    """Space-cluster graph: nodes are spaces, edges are shared bookmarks."""
    db = get_db()
    block_sql = blocked_filter_sql()

    nodes = []
    space_bookmarks = {}

    for name, sdata in SPACES.items():
        topic_ids = space_topic_ids(db, name)
        if not topic_ids:
            continue
        placeholders = ",".join("?" * len(topic_ids))
        rows = db.execute(f"""
            SELECT DISTINCT bt.bookmark_id
            FROM bookmark_topics bt
            JOIN bookmarks b ON bt.bookmark_id = b.id
            WHERE bt.topic_id IN ({placeholders}) AND b.status = 'enriched'
            AND {block_sql}
        """, topic_ids).fetchall()
        bk_ids = {r["bookmark_id"] for r in rows}
        if not bk_ids:
            continue
        space_bookmarks[name] = bk_ids

        # Top 3 titles for tooltip
        top = db.execute(f"""
            SELECT DISTINCT b.title FROM bookmark_topics bt
            JOIN bookmarks b ON bt.bookmark_id = b.id
            WHERE bt.topic_id IN ({placeholders}) AND b.status = 'enriched'
            AND {block_sql}
            ORDER BY b.added_at DESC LIMIT 3
        """, topic_ids).fetchall()

        nodes.append({
            "id": name,
            "icon": sdata["icon"],
            "color": sdata["color"],
            "count": len(bk_ids),
            "top_items": [t["title"] for t in top],
        })

    # Edges: shared bookmarks between spaces
    edges = []
    space_names = list(space_bookmarks.keys())
    for i, s1 in enumerate(space_names):
        for s2 in space_names[i + 1:]:
            shared = len(space_bookmarks[s1] & space_bookmarks[s2])
            if shared > 0:
                edges.append({
                    "source": s1,
                    "target": s2,
                    "shared": shared,
                    "strength": min(shared / 10.0, 1.0),
                })

    db.close()
    return JSONResponse({"nodes": nodes, "edges": edges})


@app.get("/gaps", response_class=HTMLResponse)
async def knowledge_gaps(request: Request):
    """Knowledge gaps dashboard — what you DON'T know yet."""
    db = get_db()
    block_sql = blocked_filter_sql()

    # Load domains from the gaps system
    domains = db.execute("SELECT * FROM domains ORDER BY priority DESC").fetchall()
    gap_data = []
    for d in domains:
        keywords = parse_json_field(d["keywords"])
        search_queries = parse_json_field(d["search_queries"]) if d["search_queries"] else []

        # Count bookmarks matching this domain's keywords
        if keywords:
            like_conditions = " OR ".join(
                [f"t.name LIKE '%{kw}%'" for kw in keywords[:10]]
            )
            count = db.execute(f"""
                SELECT COUNT(DISTINCT bt.bookmark_id)
                FROM bookmark_topics bt
                JOIN topics t ON bt.topic_id = t.id
                JOIN bookmarks b ON bt.bookmark_id = b.id
                WHERE ({like_conditions}) AND b.status = 'enriched' AND {block_sql}
            """).fetchone()[0]
        else:
            count = 0

        target = d["target_sources"] or 30
        pct = min(round(count / target * 100), 100) if target else 0
        status = "covered" if pct >= 100 else "partial" if pct >= 30 else "critical"
        urgency = round(pct / (d["priority"] or 1), 1)

        gap_data.append({
            "name": d["name"],
            "count": count,
            "target": target,
            "pct": pct,
            "priority": d["priority"] or 1.0,
            "status": status,
            "urgency": urgency,
            "search_queries": search_queries[:3],
        })

    gap_data.sort(key=lambda g: g["urgency"])
    db.close()
    return templates.TemplateResponse("gaps.html", {
        "request": request,
        "gaps": gap_data,
        "critical_count": sum(1 for g in gap_data if g["status"] == "critical"),
        "partial_count": sum(1 for g in gap_data if g["status"] == "partial"),
        "covered_count": sum(1 for g in gap_data if g["status"] == "covered"),
    })


@app.get("/review", response_class=HTMLResponse)
async def daily_review(request: Request):
    """Spaced repetition lite — resurface old high-value insights."""
    db = get_db()
    block_sql = blocked_filter_sql()

    # Get 5 random high-value insights from bookmarks older than 7 days
    items = db.execute(f"""
        SELECT b.id, b.title, b.domain, b.added_at, c.summary, c.key_insights,
               c.learning_value
        FROM bookmarks b
        JOIN content c ON b.id = c.bookmark_id
        WHERE b.status = 'enriched' AND c.key_insights IS NOT NULL
        AND c.key_insights != '[]' AND c.learning_value IN ('high', 'medium')
        AND b.added_at < datetime('now', '-7 days')
        AND {block_sql}
        ORDER BY RANDOM() LIMIT 5
    """).fetchall()

    review_items = []
    for item in items:
        insights = parse_json_field(item["key_insights"])
        spaces = get_bookmark_spaces(db, item["id"])
        review_items.append({
            "id": item["id"],
            "title": item["title"],
            "domain": item["domain"],
            "added_at": item["added_at"],
            "summary": item["summary"],
            "insights": insights,
            "learning_value": item["learning_value"],
            "spaces": spaces,
        })

    db.close()
    return templates.TemplateResponse("review.html", {
        "request": request,
        "items": review_items,
    })


@app.get("/collections", response_class=HTMLResponse)
async def collections_list(request: Request):
    db = get_db()
    collections = db.execute("""
        SELECT c.*, COUNT(bc.bookmark_id) as item_count
        FROM collections c
        LEFT JOIN bookmark_collections bc ON c.id = bc.collection_id
        GROUP BY c.id
        ORDER BY c.updated_at DESC
    """).fetchall()
    db.close()
    return templates.TemplateResponse("collections.html", {
        "request": request,
        "collections": collections,
    })


@app.get("/collection/{coll_id}", response_class=HTMLResponse)
async def collection_detail(request: Request, coll_id: str):
    db = get_db()
    block_sql = blocked_filter_sql()
    coll = db.execute("SELECT * FROM collections WHERE id = ?", (coll_id,)).fetchone()
    if not coll:
        db.close()
        return HTMLResponse("<h1>Collection not found</h1>", status_code=404)
    items = db.execute(f"""
        SELECT b.id, b.title, b.domain, b.added_at, c.summary, c.learning_value
        FROM bookmark_collections bc
        JOIN bookmarks b ON bc.bookmark_id = b.id
        LEFT JOIN content c ON b.id = c.bookmark_id
        WHERE bc.collection_id = ? AND {block_sql}
        ORDER BY bc.added_at DESC
    """, (coll_id,)).fetchall()
    db.close()
    return templates.TemplateResponse("collection.html", {
        "request": request,
        "collection": coll,
        "items": items,
    })


@app.post("/api/collections")
async def api_create_collection(request: Request):
    body = await request.json()
    name = body.get("name", "").strip()
    if not name:
        return JSONResponse({"error": "Name required"}, status_code=400)
    coll_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    db = get_db()
    db.execute(
        "INSERT INTO collections (id, name, description, color, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (coll_id, name, body.get("description", ""), body.get("color", "#6E6E73"), now, now),
    )
    db.commit()
    db.close()
    return JSONResponse({"id": coll_id, "name": name})


@app.post("/api/collections/{coll_id}/add")
async def api_add_to_collection(request: Request, coll_id: str):
    body = await request.json()
    bookmark_id = body.get("bookmark_id")
    if not bookmark_id:
        return JSONResponse({"error": "bookmark_id required"}, status_code=400)
    now = datetime.now(timezone.utc).isoformat()
    db = get_db()
    try:
        db.execute(
            "INSERT INTO bookmark_collections (bookmark_id, collection_id, added_at) VALUES (?, ?, ?)",
            (bookmark_id, coll_id, now),
        )
        db.execute("UPDATE collections SET updated_at = ? WHERE id = ?", (now, coll_id))
        db.commit()
    except sqlite3.IntegrityError:
        pass
    db.close()
    return JSONResponse({"status": "added"})


@app.post("/api/collections/{coll_id}/remove")
async def api_remove_from_collection(request: Request, coll_id: str):
    body = await request.json()
    bookmark_id = body.get("bookmark_id")
    db = get_db()
    db.execute(
        "DELETE FROM bookmark_collections WHERE bookmark_id = ? AND collection_id = ?",
        (bookmark_id, coll_id),
    )
    db.commit()
    db.close()
    return JSONResponse({"status": "removed"})


@app.post("/api/follow-expert/{expert_id}")
async def api_follow_expert(expert_id: str):
    db = get_db()
    expert = db.execute("SELECT followed FROM experts WHERE id = ?", (expert_id,)).fetchone()
    if not expert:
        db.close()
        return JSONResponse({"error": "Not found"}, status_code=404)
    new_state = 0 if expert["followed"] else 1
    db.execute("UPDATE experts SET followed = ? WHERE id = ?", (new_state, expert_id))
    db.commit()
    db.close()
    return JSONResponse({"followed": bool(new_state)})


# --- Feature: RSS Feeds ---

@app.get("/feeds", response_class=HTMLResponse)
async def feeds_page(request: Request):
    db = get_db()
    feeds = db.execute("""
        SELECT f.*,
               (SELECT COUNT(*) FROM bookmarks WHERE source = 'rss:' || f.id) as item_count
        FROM rss_feeds f
        ORDER BY f.created_at DESC
    """).fetchall()
    db.close()
    return templates.TemplateResponse("feeds.html", {
        "request": request,
        "feeds": feeds,
    })


@app.post("/api/feeds")
async def api_add_feed(request: Request):
    body = await request.json()
    url = body.get("url", "").strip()
    if not url:
        return JSONResponse({"error": "URL required"}, status_code=400)

    db = get_db()
    existing = db.execute("SELECT id FROM rss_feeds WHERE url = ?", (url,)).fetchone()
    if existing:
        db.close()
        return JSONResponse({"error": "Feed already exists", "id": existing["id"]}, status_code=409)

    # Parse feed to get title
    feed = feedparser.parse(url)
    title = feed.feed.get("title", url) if feed.feed else url
    feed_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    db.execute(
        "INSERT INTO rss_feeds (id, url, title, created_at) VALUES (?, ?, ?, ?)",
        (feed_id, url, title, now),
    )
    db.commit()
    db.close()
    return JSONResponse({"id": feed_id, "title": title, "status": "added"})


@app.post("/api/feeds/{feed_id}/fetch")
async def api_fetch_feed(feed_id: str):
    db = get_db()
    feed_row = db.execute("SELECT * FROM rss_feeds WHERE id = ?", (feed_id,)).fetchone()
    if not feed_row:
        db.close()
        return JSONResponse({"error": "Feed not found"}, status_code=404)

    feed = feedparser.parse(feed_row["url"])
    now = datetime.now(timezone.utc).isoformat()
    new_count = 0

    for entry in feed.entries:
        link = entry.get("link", "").strip()
        if not link:
            continue
        existing = db.execute("SELECT id FROM bookmarks WHERE url = ?", (link,)).fetchone()
        if existing:
            continue

        bookmark_id = str(uuid.uuid4())
        title = entry.get("title", link)
        domain = link.replace("https://", "").replace("http://", "").split("/")[0]

        db.execute(
            "INSERT INTO bookmarks (id, url, title, domain, source, added_at, status) VALUES (?, ?, ?, ?, ?, ?, 'pending')",
            (bookmark_id, link, title, domain, f"rss:{feed_id}", now),
        )
        run_rules_on_bookmark(db, bookmark_id)
        new_count += 1

    db.execute("UPDATE rss_feeds SET last_fetched = ? WHERE id = ?", (now, feed_id))
    db.commit()
    db.close()
    return JSONResponse({"feed_id": feed_id, "new_items": new_count})


@app.delete("/api/feeds/{feed_id}")
async def api_delete_feed(feed_id: str):
    db = get_db()
    db.execute("DELETE FROM rss_feeds WHERE id = ?", (feed_id,))
    db.commit()
    db.close()
    return JSONResponse({"status": "deleted"})


# --- Feature: Broken Link Checker ---

@app.get("/api/check-links")
async def api_check_links():
    db = get_db()
    block_sql = blocked_filter_sql()
    rows = db.execute(f"""
        SELECT b.id, b.url FROM bookmarks b
        WHERE b.status = 'enriched' AND {block_sql}
        ORDER BY b.last_checked ASC NULLS FIRST
        LIMIT 50
    """).fetchall()

    results = []
    now = datetime.now(timezone.utc).isoformat()
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        for row in rows:
            status = "ok"
            code = 0
            try:
                resp = await client.head(row["url"])
                code = resp.status_code
                if code in (404, 410):
                    status = "broken"
                elif code >= 500:
                    status = "error"
            except httpx.TimeoutException:
                status = "timeout"
                code = 0
            except Exception:
                status = "error"
                code = 0

            db.execute(
                "UPDATE bookmarks SET link_status = ?, last_checked = ? WHERE id = ?",
                (status, now, row["id"]),
            )
            results.append({"id": row["id"], "url": row["url"], "status": status, "code": code})

    db.commit()
    db.close()
    return JSONResponse({"checked": len(results), "results": results})


@app.get("/health", response_class=HTMLResponse)
async def health_page(request: Request):
    db = get_db()
    block_sql = blocked_filter_sql()
    broken = db.execute(f"""
        SELECT b.id, b.title, b.url, b.domain, b.link_status, b.last_checked
        FROM bookmarks b
        WHERE b.link_status IN ('broken', 'error', 'timeout')
        AND {block_sql}
        ORDER BY b.last_checked DESC
    """).fetchall()
    total_checked = db.execute(
        "SELECT COUNT(*) FROM bookmarks WHERE last_checked IS NOT NULL"
    ).fetchone()[0]
    total_broken = len(broken)
    db.close()
    return templates.TemplateResponse("health.html", {
        "request": request,
        "broken": broken,
        "total_checked": total_checked,
        "total_broken": total_broken,
    })


# --- Feature: Full-page Archival + Wayback Machine ---

@app.post("/api/archive/{bookmark_id}")
async def api_archive(bookmark_id: str):
    db = get_db()
    bookmark = db.execute("SELECT url FROM bookmarks WHERE id = ?", (bookmark_id,)).fetchone()
    if not bookmark:
        db.close()
        return JSONResponse({"error": "Not found"}, status_code=404)

    url = bookmark["url"]
    html = ""
    method = "httpx"
    try:
        # Prefer monolith for self-contained archival
        if shutil.which("monolith"):
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
                tmp_path = tmp.name
            result = subprocess.run(
                ["monolith", url, "-o", tmp_path],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode == 0 and Path(tmp_path).exists():
                html = Path(tmp_path).read_text(errors="ignore")
                method = "monolith"
                Path(tmp_path).unlink(missing_ok=True)
            else:
                Path(tmp_path).unlink(missing_ok=True)
                raise RuntimeError("monolith failed, falling back to httpx")

        if not html:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(url)
                html = resp.text

        db.execute(
            "UPDATE content SET page_cache = ? WHERE bookmark_id = ?",
            (html, bookmark_id),
        )
        db.commit()

        # Fire-and-forget Wayback Machine submission
        asyncio.create_task(_submit_wayback(url))
    except Exception as e:
        db.close()
        return JSONResponse({"error": f"Fetch failed: {str(e)}"}, status_code=502)

    db.close()
    return JSONResponse({"status": "archived", "size": len(html), "method": method})


async def _submit_wayback(url: str):
    """Submit URL to Wayback Machine (fire-and-forget)."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            await client.get(f"https://web.archive.org/save/{url}")
    except Exception:
        pass  # Best-effort, don't fail on this


@app.get("/archive/{bookmark_id}", response_class=HTMLResponse)
async def serve_archive(bookmark_id: str):
    db = get_db()
    row = db.execute(
        "SELECT page_cache FROM content WHERE bookmark_id = ? AND page_cache IS NOT NULL",
        (bookmark_id,),
    ).fetchone()
    db.close()
    if not row:
        return HTMLResponse("<h1>No cached copy available</h1>", status_code=404)
    return HTMLResponse(row["page_cache"])


# --- Feature: Bulk Actions ---

@app.post("/api/bulk/add-to-collection")
async def api_bulk_add_to_collection(request: Request):
    body = await request.json()
    bookmark_ids = body.get("bookmark_ids", [])
    collection_name = body.get("collection_name", "").strip()
    if not bookmark_ids or not collection_name:
        return JSONResponse({"error": "bookmark_ids and collection_name required"}, status_code=400)
    now = datetime.now(timezone.utc).isoformat()
    db = get_db()
    coll = db.execute("SELECT id FROM collections WHERE name = ?", (collection_name,)).fetchone()
    if coll:
        coll_id = coll["id"]
    else:
        coll_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO collections (id, name, description, color, created_at, updated_at) VALUES (?, ?, '', '#6E6E73', ?, ?)",
            (coll_id, collection_name, now, now),
        )
    for bid in bookmark_ids:
        try:
            db.execute(
                "INSERT INTO bookmark_collections (bookmark_id, collection_id, added_at) VALUES (?, ?, ?)",
                (bid, coll_id, now),
            )
        except sqlite3.IntegrityError:
            pass
    db.execute("UPDATE collections SET updated_at = ? WHERE id = ?", (now, coll_id))
    db.commit()
    db.close()
    return JSONResponse({"status": "added", "collection_id": coll_id, "count": len(bookmark_ids)})


@app.post("/api/bulk/delete")
async def api_bulk_delete(request: Request):
    body = await request.json()
    bookmark_ids = body.get("bookmark_ids", [])
    if not bookmark_ids:
        return JSONResponse({"error": "bookmark_ids required"}, status_code=400)
    db = get_db()
    placeholders = ",".join("?" * len(bookmark_ids))
    db.execute(f"DELETE FROM bookmark_collections WHERE bookmark_id IN ({placeholders})", bookmark_ids)
    db.execute(f"DELETE FROM bookmark_topics WHERE bookmark_id IN ({placeholders})", bookmark_ids)
    db.execute(f"DELETE FROM bookmark_experts WHERE bookmark_id IN ({placeholders})", bookmark_ids)
    db.execute(f"DELETE FROM item_views WHERE bookmark_id IN ({placeholders})", bookmark_ids)
    db.execute(f"DELETE FROM highlights WHERE bookmark_id IN ({placeholders})", bookmark_ids)
    db.execute(f"DELETE FROM content WHERE bookmark_id IN ({placeholders})", bookmark_ids)
    db.execute(f"DELETE FROM bookmarks WHERE id IN ({placeholders})", bookmark_ids)
    db.commit()
    db.close()
    return JSONResponse({"status": "deleted", "count": len(bookmark_ids)})


@app.post("/api/bulk/re-enrich")
async def api_bulk_re_enrich(request: Request):
    body = await request.json()
    bookmark_ids = body.get("bookmark_ids", [])
    if not bookmark_ids:
        return JSONResponse({"error": "bookmark_ids required"}, status_code=400)
    db = get_db()
    placeholders = ",".join("?" * len(bookmark_ids))
    db.execute(f"UPDATE bookmarks SET status = 'pending' WHERE id IN ({placeholders})", bookmark_ids)
    db.commit()
    db.close()
    return JSONResponse({"status": "queued", "count": len(bookmark_ids)})


# --- Feature: Read Status ---

@app.post("/api/read-status/{bookmark_id}")
async def api_set_read_status(request: Request, bookmark_id: str):
    body = await request.json()
    status = body.get("status", "unread")
    if status not in ("unread", "reading", "read"):
        return JSONResponse({"error": "Invalid status"}, status_code=400)
    db = get_db()
    db.execute("UPDATE bookmarks SET read_status = ? WHERE id = ?", (status, bookmark_id))
    db.commit()
    db.close()
    return JSONResponse({"status": status})


# --- Feature: Highlights ---

@app.post("/api/highlights")
async def api_create_highlight(request: Request):
    body = await request.json()
    bookmark_id = body.get("bookmark_id")
    text = body.get("text", "").strip()
    if not bookmark_id or not text:
        return JSONResponse({"error": "bookmark_id and text required"}, status_code=400)
    highlight_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    db = get_db()
    row = db.execute(
        "SELECT MAX(position) as mx FROM highlights WHERE bookmark_id = ?", (bookmark_id,)
    ).fetchone()
    pos = (row["mx"] or 0) + 1
    db.execute(
        "INSERT INTO highlights (id, bookmark_id, text, note, color, position, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (highlight_id, bookmark_id, text, body.get("note", ""), body.get("color", "signal"), pos, now),
    )
    db.commit()
    db.close()
    return JSONResponse({"id": highlight_id, "status": "saved"})


@app.delete("/api/highlights/{highlight_id}")
async def api_delete_highlight(highlight_id: str):
    db = get_db()
    db.execute("DELETE FROM highlights WHERE id = ?", (highlight_id,))
    db.commit()
    db.close()
    return JSONResponse({"status": "deleted"})


@app.get("/highlights", response_class=HTMLResponse)
async def highlights_list(request: Request):
    db = get_db()
    rows = db.execute("""
        SELECT h.*, b.title as bookmark_title, b.domain
        FROM highlights h
        JOIN bookmarks b ON h.bookmark_id = b.id
        ORDER BY h.created_at DESC
    """).fetchall()
    grouped = {}
    for r in rows:
        bid = r["bookmark_id"]
        if bid not in grouped:
            grouped[bid] = {
                "bookmark_id": bid,
                "title": r["bookmark_title"],
                "domain": r["domain"],
                "highlights": [],
            }
        grouped[bid]["highlights"].append(r)
    db.close()
    return templates.TemplateResponse("highlights.html", {
        "request": request,
        "groups": list(grouped.values()),
        "total": len(rows),
    })


# --- Feature: Notes Page ---

@app.get("/notes", response_class=HTMLResponse)
async def notes_page(request: Request):
    db = get_db()
    notes = db.execute("SELECT * FROM notes ORDER BY created_at DESC").fetchall()
    db.close()
    return templates.TemplateResponse("notes.html", {
        "request": request,
        "notes": notes,
    })


@app.delete("/api/notes/{note_id}")
async def api_delete_note(note_id: str):
    db = get_db()
    db.execute("DELETE FROM notes_fts WHERE note_id = ?", (note_id,))
    db.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    db.commit()
    db.close()
    return JSONResponse({"status": "deleted"})


# --- Feature: Video Archiving via yt-dlp ---

_YT_PATTERN = re.compile(r"(youtube\.com/watch|youtu\.be/|youtube\.com/shorts/)")


def _is_youtube(url: str) -> bool:
    return bool(_YT_PATTERN.search(url or ""))


@app.post("/api/download-video/{bookmark_id}")
async def api_download_video(bookmark_id: str):
    db = get_db()
    bookmark = db.execute("SELECT url FROM bookmarks WHERE id = ?", (bookmark_id,)).fetchone()
    if not bookmark:
        db.close()
        return JSONResponse({"error": "Not found"}, status_code=404)

    if not shutil.which("yt-dlp"):
        db.close()
        return JSONResponse({"error": "yt-dlp is not installed. Run: brew install yt-dlp"}, status_code=500)

    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    url = bookmark["url"]
    out_template = str(VIDEOS_DIR / "%(id)s.%(ext)s")

    # Run in background — don't block
    subprocess.Popen(
        ["yt-dlp", "-x", "--audio-format", "mp3", "-o", out_template, url],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    # Try to extract video ID for the expected path
    vid_id = None
    if "v=" in url:
        vid_id = url.split("v=")[1].split("&")[0]
    elif "youtu.be/" in url:
        vid_id = url.split("youtu.be/")[1].split("?")[0]
    elif "shorts/" in url:
        vid_id = url.split("shorts/")[1].split("?")[0]

    if vid_id:
        expected_path = str(VIDEOS_DIR / f"{vid_id}.mp3")
        db.execute("UPDATE bookmarks SET video_path = ? WHERE id = ?", (expected_path, bookmark_id))
        db.commit()

    db.close()
    return JSONResponse({"status": "downloading", "video_id": vid_id})


@app.get("/api/video/{bookmark_id}")
async def api_serve_video(bookmark_id: str):
    """Serve a downloaded audio file."""
    db = get_db()
    bookmark = db.execute("SELECT video_path FROM bookmarks WHERE id = ?", (bookmark_id,)).fetchone()
    db.close()
    if not bookmark or not bookmark["video_path"]:
        return JSONResponse({"error": "No video"}, status_code=404)
    vpath = Path(bookmark["video_path"])
    if not vpath.exists():
        return JSONResponse({"error": "File not found (still downloading?)"}, status_code=404)
    from fastapi.responses import FileResponse
    return FileResponse(str(vpath), media_type="audio/mpeg")


# --- Feature: Rule-based Automation Engine ---

def run_rules_on_bookmark(db, bookmark_id):
    """Execute all active rules against a single bookmark."""
    bookmark = db.execute("""
        SELECT b.*, c.learning_value, c.content_type
        FROM bookmarks b
        LEFT JOIN content c ON b.id = c.bookmark_id
        WHERE b.id = ?
    """, (bookmark_id,)).fetchone()
    if not bookmark:
        return

    rules = db.execute(
        "SELECT * FROM automation_rules WHERE active = 1"
    ).fetchall()

    for rule in rules:
        conditions = json.loads(rule["conditions"] or "[]")
        actions = json.loads(rule["actions"] or "[]")

        if not conditions or not actions:
            continue

        # Check ALL conditions
        match = True
        for cond in conditions:
            field = cond.get("field", "")
            op = cond.get("op", "")
            value = cond.get("value", "")
            actual = ""
            if field == "domain":
                actual = bookmark["domain"] or ""
            elif field == "title":
                actual = bookmark["title"] or ""
            elif field == "learning_value":
                actual = bookmark["learning_value"] if bookmark["learning_value"] else ""
            elif field == "content_type":
                actual = bookmark["content_type"] if bookmark["content_type"] else ""
            elif field == "source":
                actual = bookmark["source"] or ""

            if op == "contains" and value.lower() not in actual.lower():
                match = False
                break
            elif op == "equals" and actual.lower() != value.lower():
                match = False
                break
            elif op == "starts_with" and not actual.lower().startswith(value.lower()):
                match = False
                break

        if not match:
            continue

        # Execute ALL actions
        now = datetime.now(timezone.utc).isoformat()
        for action in actions:
            atype = action.get("type", "")
            avalue = action.get("value", "")

            if atype == "add_to_collection":
                coll = db.execute("SELECT id FROM collections WHERE name = ?", (avalue,)).fetchone()
                if coll:
                    coll_id = coll["id"]
                else:
                    coll_id = str(uuid.uuid4())
                    db.execute(
                        "INSERT INTO collections (id, name, description, color, created_at, updated_at) VALUES (?, ?, '', '#6E6E73', ?, ?)",
                        (coll_id, avalue, now, now),
                    )
                try:
                    db.execute(
                        "INSERT INTO bookmark_collections (bookmark_id, collection_id, added_at) VALUES (?, ?, ?)",
                        (bookmark_id, coll_id, now),
                    )
                except sqlite3.IntegrityError:
                    pass

            elif atype == "set_read_status" and avalue in ("unread", "reading", "read"):
                db.execute("UPDATE bookmarks SET read_status = ? WHERE id = ?", (avalue, bookmark_id))

        db.execute(
            "UPDATE automation_rules SET run_count = run_count + 1 WHERE id = ?",
            (rule["id"],),
        )

    db.commit()


@app.get("/rules", response_class=HTMLResponse)
async def rules_page(request: Request):
    db = get_db()
    rules = db.execute("SELECT * FROM automation_rules ORDER BY created_at DESC").fetchall()
    collections = db.execute("SELECT name FROM collections ORDER BY name").fetchall()
    db.close()
    return templates.TemplateResponse("rules.html", {
        "request": request,
        "rules": rules,
        "collections": [c["name"] for c in collections],
    })


@app.post("/api/rules")
async def api_create_rule(request: Request):
    body = await request.json()
    name = body.get("name", "").strip()
    conditions = body.get("conditions", [])
    actions = body.get("actions", [])
    if not name or not conditions or not actions:
        return JSONResponse({"error": "name, conditions, and actions required"}, status_code=400)

    rule_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    db = get_db()
    db.execute(
        "INSERT INTO automation_rules (id, name, active, conditions, actions, created_at, run_count) VALUES (?, ?, 1, ?, ?, ?, 0)",
        (rule_id, name, json.dumps(conditions), json.dumps(actions), now),
    )
    db.commit()
    db.close()
    return JSONResponse({"id": rule_id, "status": "created"})


@app.delete("/api/rules/{rule_id}")
async def api_delete_rule(rule_id: str):
    db = get_db()
    db.execute("DELETE FROM automation_rules WHERE id = ?", (rule_id,))
    db.commit()
    db.close()
    return JSONResponse({"status": "deleted"})


@app.post("/api/rules/{rule_id}/toggle")
async def api_toggle_rule(rule_id: str):
    db = get_db()
    rule = db.execute("SELECT active FROM automation_rules WHERE id = ?", (rule_id,)).fetchone()
    if not rule:
        db.close()
        return JSONResponse({"error": "Not found"}, status_code=404)
    new_state = 0 if rule["active"] else 1
    db.execute("UPDATE automation_rules SET active = ? WHERE id = ?", (new_state, rule_id))
    db.commit()
    db.close()
    return JSONResponse({"active": bool(new_state)})


@app.post("/api/rules/run-all")
async def api_run_all_rules():
    db = get_db()
    bookmarks = db.execute("SELECT id FROM bookmarks WHERE status = 'enriched'").fetchall()
    count = 0
    for b in bookmarks:
        run_rules_on_bookmark(db, b["id"])
        count += 1
    db.close()
    return JSONResponse({"status": "complete", "bookmarks_checked": count})


# --- Feature: Multi-source Import ---

@app.get("/import", response_class=HTMLResponse)
async def import_page(request: Request):
    return templates.TemplateResponse("import.html", {"request": request})


@app.post("/api/import/pocket")
async def api_import_pocket(file: UploadFile = File(...)):
    """Import from Pocket HTML export."""
    contents = await file.read()
    html_text = contents.decode("utf-8", errors="ignore")

    # Parse <a> tags from Pocket export
    link_pattern = re.compile(
        r'<a\s+[^>]*href="([^"]+)"[^>]*time_added="(\d+)"[^>]*tags="([^"]*)"[^>]*>([^<]*)</a>',
        re.IGNORECASE,
    )
    # Fallback: simpler pattern
    simple_pattern = re.compile(
        r'<a\s+[^>]*href="([^"]+)"[^>]*>([^<]*)</a>',
        re.IGNORECASE,
    )

    items = []
    for m in link_pattern.finditer(html_text):
        items.append({
            "url": m.group(1),
            "time_added": m.group(2),
            "tags": m.group(3),
            "title": m.group(4),
        })

    if not items:
        for m in simple_pattern.finditer(html_text):
            url = m.group(1)
            if url.startswith("http"):
                items.append({"url": url, "title": m.group(2), "tags": "", "time_added": ""})

    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    imported = 0
    skipped = 0

    for item in items:
        url = item["url"]
        existing = db.execute("SELECT id FROM bookmarks WHERE url = ?", (url,)).fetchone()
        if existing:
            skipped += 1
            continue
        bookmark_id = str(uuid.uuid4())
        domain = url.replace("https://", "").replace("http://", "").split("/")[0]
        title = item.get("title") or url
        db.execute(
            "INSERT INTO bookmarks (id, url, title, domain, source, added_at, status) VALUES (?, ?, ?, ?, 'pocket', ?, 'pending')",
            (bookmark_id, url, title, domain, now),
        )
        imported += 1

    db.commit()
    db.close()
    return JSONResponse({"imported": imported, "skipped": skipped})


@app.post("/api/import/omnivore")
async def api_import_omnivore(file: UploadFile = File(...)):
    """Import from Omnivore JSON export."""
    contents = await file.read()
    try:
        data = json.loads(contents.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JSONResponse({"error": "Invalid JSON file"}, status_code=400)

    # Omnivore exports as an array of items or {items: [...]}
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict) and "items" in data:
        items = data["items"]
    else:
        items = [data] if isinstance(data, dict) else []

    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    imported = 0
    skipped = 0

    for item in items:
        url = item.get("url") or item.get("originalArticleUrl", "")
        if not url:
            continue
        existing = db.execute("SELECT id FROM bookmarks WHERE url = ?", (url,)).fetchone()
        if existing:
            skipped += 1
            continue
        bookmark_id = str(uuid.uuid4())
        domain = url.replace("https://", "").replace("http://", "").split("/")[0]
        title = item.get("title") or url
        db.execute(
            "INSERT INTO bookmarks (id, url, title, domain, source, added_at, status) VALUES (?, ?, ?, ?, 'omnivore', ?, 'pending')",
            (bookmark_id, url, title, domain, now),
        )
        imported += 1

    db.commit()
    db.close()
    return JSONResponse({"imported": imported, "skipped": skipped})


# --- Feature: OCR for Images ---

@app.post("/api/upload-image")
async def api_upload_image(file: UploadFile = File(...)):
    """Upload an image and extract text via OCR."""
    if not file.filename:
        return JSONResponse({"error": "No file provided"}, status_code=400)

    ext = file.filename.lower().rsplit(".", 1)[-1] if "." in file.filename else ""
    if ext not in ("png", "jpg", "jpeg", "webp", "tiff", "bmp"):
        return JSONResponse({"error": "Unsupported image format. Use PNG, JPG, or WEBP."}, status_code=400)

    contents = await file.read()

    # Try OCR
    ocr_text = ""
    ocr_available = True
    try:
        import pytesseract
        from PIL import Image
        img = Image.open(io.BytesIO(contents))
        ocr_text = pytesseract.image_to_string(img).strip()
    except ImportError:
        ocr_available = False
    except Exception as e:
        ocr_text = f"[OCR failed: {str(e)}]"

    bookmark_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    title = file.filename.rsplit(".", 1)[0].replace("-", " ").replace("_", " ")

    # Save image file to disk
    images_dir = Path(__file__).parent.parent.parent / "data" / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    safe_filename = f"{bookmark_id}.{ext}"
    (images_dir / safe_filename).write_bytes(contents)

    db = get_db()
    db.execute(
        "INSERT INTO bookmarks (id, url, title, domain, source, added_at, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (bookmark_id, f"file://images/{safe_filename}", title, "local", "upload-image", now, "fetched"),
    )
    word_count = len(ocr_text.split()) if ocr_text else 0
    db.execute(
        "INSERT OR REPLACE INTO content (bookmark_id, raw_text, word_count) VALUES (?, ?, ?)",
        (bookmark_id, ocr_text or "[No text extracted]", word_count),
    )
    db.commit()
    db.close()

    return JSONResponse({
        "id": bookmark_id,
        "title": title,
        "word_count": word_count,
        "ocr_available": ocr_available,
        "status": "uploaded",
    })


# =============================================================
# P3 Features: Screenshot, PDF, Dark Mode, Cookies, JS Render, Images
# =============================================================

SCREENSHOTS_DIR = Path(__file__).parent.parent.parent / "data" / "screenshots"
PDFS_DIR = Path(__file__).parent.parent.parent / "data" / "pdfs"
IMAGES_DIR = Path(__file__).parent.parent.parent / "data" / "images"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
PDFS_DIR.mkdir(parents=True, exist_ok=True)
IMAGES_DIR.mkdir(parents=True, exist_ok=True)


# --- Feature 1: Screenshot Capture ---

def _capture_screenshot(url: str, save_path: Path):
    """Synchronous Playwright screenshot capture."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.screenshot(path=str(save_path), full_page=False)
        browser.close()


@app.post("/api/screenshot/{bookmark_id}")
async def api_screenshot(bookmark_id: str):
    db = get_db()
    bookmark = db.execute("SELECT url FROM bookmarks WHERE id = ?", (bookmark_id,)).fetchone()
    if not bookmark:
        db.close()
        return JSONResponse({"error": "Not found"}, status_code=404)
    save_path = SCREENSHOTS_DIR / f"{bookmark_id}.png"
    try:
        await asyncio.to_thread(_capture_screenshot, bookmark["url"], save_path)
    except Exception as e:
        db.close()
        return JSONResponse({"error": str(e)}, status_code=500)
    rel_path = f"data/screenshots/{bookmark_id}.png"
    db.execute("UPDATE bookmarks SET screenshot_path = ? WHERE id = ?", (rel_path, bookmark_id))
    db.commit()
    db.close()
    return JSONResponse({"path": rel_path, "status": "captured"})


@app.get("/screenshot/{bookmark_id}")
async def serve_screenshot(bookmark_id: str):
    from fastapi.responses import FileResponse
    path = SCREENSHOTS_DIR / f"{bookmark_id}.png"
    if not path.exists():
        return JSONResponse({"error": "No screenshot"}, status_code=404)
    return FileResponse(str(path), media_type="image/png")


# --- Feature 2: PDF Capture ---

def _capture_pdf(url: str, save_path: Path):
    """Synchronous Playwright PDF capture."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.pdf(path=str(save_path), format="A4", print_background=True)
        browser.close()


@app.post("/api/pdf-capture/{bookmark_id}")
async def api_pdf_capture(bookmark_id: str):
    db = get_db()
    bookmark = db.execute("SELECT url FROM bookmarks WHERE id = ?", (bookmark_id,)).fetchone()
    if not bookmark:
        db.close()
        return JSONResponse({"error": "Not found"}, status_code=404)
    save_path = PDFS_DIR / f"{bookmark_id}.pdf"
    try:
        await asyncio.to_thread(_capture_pdf, bookmark["url"], save_path)
    except Exception as e:
        db.close()
        return JSONResponse({"error": str(e)}, status_code=500)
    rel_path = f"data/pdfs/{bookmark_id}.pdf"
    db.execute("UPDATE bookmarks SET pdf_path = ? WHERE id = ?", (rel_path, bookmark_id))
    db.commit()
    db.close()
    return JSONResponse({"path": rel_path, "status": "captured"})


@app.get("/pdf/{bookmark_id}")
async def serve_pdf(bookmark_id: str):
    from fastapi.responses import FileResponse
    path = PDFS_DIR / f"{bookmark_id}.pdf"
    if not path.exists():
        return JSONResponse({"error": "No PDF"}, status_code=404)
    return FileResponse(str(path), media_type="application/pdf")


# --- Feature 4: Cookie-injected Crawling ---

@app.post("/api/set-cookies")
async def api_set_cookies(request: Request):
    body = await request.json()
    domain = body.get("domain", "").strip()
    cookies = body.get("cookies", [])
    if not domain or not cookies:
        return JSONResponse({"error": "domain and cookies required"}, status_code=400)
    db = get_db()
    cid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        "INSERT OR REPLACE INTO cookie_jar (id, domain, cookies_json, created_at) VALUES (?, ?, ?, ?)",
        (cid, domain, json.dumps(cookies), now),
    )
    db.commit()
    db.close()
    return JSONResponse({"id": cid, "domain": domain, "status": "saved"})


@app.delete("/api/cookies/{cookie_id}")
async def api_delete_cookie(cookie_id: str):
    db = get_db()
    db.execute("DELETE FROM cookie_jar WHERE id = ?", (cookie_id,))
    db.commit()
    db.close()
    return JSONResponse({"status": "deleted"})


def get_cookies_for_domain(db, url: str) -> dict:
    """Get stored cookies for a URL's domain as a header-ready cookie string."""
    from urllib.parse import urlparse
    domain = urlparse(url).netloc
    rows = db.execute(
        "SELECT cookies_json FROM cookie_jar WHERE domain = ? OR ? LIKE '%' || domain",
        (domain, domain),
    ).fetchall()
    cookies = {}
    for row in rows:
        try:
            for c in json.loads(row["cookies_json"]):
                cookies[c["name"]] = c["value"]
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
    return cookies


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    db = get_db()
    cookie_domains = db.execute(
        "SELECT id, domain, created_at FROM cookie_jar ORDER BY created_at DESC"
    ).fetchall()
    total = db.execute("SELECT COUNT(*) FROM bookmarks").fetchone()[0]
    enriched = db.execute("SELECT COUNT(*) FROM bookmarks WHERE status = 'enriched'").fetchone()[0]
    stats = {"total": total, "enriched_pct": round(enriched / total * 100) if total else 0}
    db.close()
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "active": "settings",
        "cookie_domains": cookie_domains,
        "stats": stats,
    })


# --- Feature 5: Headless Browser for JS-rendered Pages ---

def _render_page_js(url: str, cookies: dict = None) -> str:
    """Use Playwright to render a JS-heavy page and return its text content."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        if cookies:
            cookie_list = [
                {"name": k, "value": v, "url": url} for k, v in cookies.items()
            ]
            context.add_cookies(cookie_list)
        page = context.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)
        text = page.evaluate("() => document.body.innerText")
        browser.close()
        return text or ""


@app.post("/api/render/{bookmark_id}")
async def api_render_js(bookmark_id: str):
    db = get_db()
    bookmark = db.execute("SELECT url FROM bookmarks WHERE id = ?", (bookmark_id,)).fetchone()
    if not bookmark:
        db.close()
        return JSONResponse({"error": "Not found"}, status_code=404)
    cookies = get_cookies_for_domain(db, bookmark["url"])
    try:
        text = await asyncio.to_thread(_render_page_js, bookmark["url"], cookies)
    except Exception as e:
        db.close()
        return JSONResponse({"error": str(e)}, status_code=500)
    word_count = len(text.split())
    db.execute(
        "INSERT OR REPLACE INTO content (bookmark_id, raw_text, word_count) VALUES (?, ?, ?)",
        (bookmark_id, text, word_count),
    )
    db.execute("UPDATE bookmarks SET js_rendered = 1 WHERE id = ?", (bookmark_id,))
    db.commit()
    db.close()
    return JSONResponse({"word_count": word_count, "status": "rendered"})


# --- Feature 6: Image Upload as Bookmarks (enhanced) ---
# Note: basic /api/upload-image already exists above. This adds the image serving route.

@app.get("/image/{filename}")
async def serve_image(filename: str):
    from fastapi.responses import FileResponse
    # Sanitize filename
    safe = Path(filename).name
    path = IMAGES_DIR / safe
    if not path.exists():
        return JSONResponse({"error": "Image not found"}, status_code=404)
    ext = safe.rsplit(".", 1)[-1].lower()
    media_types = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                   "webp": "image/webp", "gif": "image/gif"}
    return FileResponse(str(path), media_type=media_types.get(ext, "application/octet-stream"))


@app.post("/api/enrich/{bookmark_id}")
async def api_enrich_bookmark(bookmark_id: str):
    """Enrich a bookmark using the Anthropic API directly. Requires ANTHROPIC_API_KEY env var."""
    import os
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return JSONResponse({"error": "Set ANTHROPIC_API_KEY environment variable to enable enrichment."}, status_code=400)

    db = get_db()
    bookmark = db.execute("""
        SELECT b.id, b.url, b.title, b.domain, c.raw_text
        FROM bookmarks b LEFT JOIN content c ON b.id = c.bookmark_id
        WHERE b.id = ?
    """, (bookmark_id,)).fetchone()
    if not bookmark:
        db.close()
        return JSONResponse({"error": "Bookmark not found"}, status_code=404)

    raw_text = bookmark["raw_text"] or ""
    if not raw_text:
        # Fetch the page first
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(bookmark["url"])
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, "html.parser")
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                raw_text = (soup.find("article") or soup.find("main") or soup.find("body") or soup).get_text(separator="\n", strip=True)[:8000]
                db.execute(
                    "INSERT OR REPLACE INTO content (bookmark_id, raw_text, fetched_at) VALUES (?, ?, ?)",
                    (bookmark_id, raw_text, datetime.now(timezone.utc).isoformat()),
                )
                db.commit()
        except Exception as e:
            db.close()
            return JSONResponse({"error": f"Failed to fetch page: {e}"}, status_code=500)

    # Call Anthropic API
    prompt = f"""Analyze this web page and return a JSON object with these fields:
- "summary": 2-3 sentence summary
- "topics": array of 3-7 lowercase topic tags
- "content_type": one of article/tutorial/documentation/tool/video/reference/news/opinion/research/product
- "learning_value": "high", "medium", or "low"
- "key_insights": array of 1-3 key takeaways
- "author_name": author name if identifiable, null otherwise

Title: {bookmark['title'] or 'Unknown'}
Domain: {bookmark['domain'] or 'Unknown'}
URL: {bookmark['url']}

Content (truncated to 6000 chars):
{raw_text[:6000]}

Return ONLY valid JSON, no markdown fences."""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            data = resp.json()
            text = data["content"][0]["text"]

            # Parse the JSON response
            enrichment = json.loads(text)

            now = datetime.now(timezone.utc).isoformat()
            db.execute("""
                INSERT OR REPLACE INTO content
                (bookmark_id, raw_text, summary, key_insights, content_type, learning_value, enriched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                bookmark_id,
                raw_text,
                enrichment.get("summary", ""),
                json.dumps(enrichment.get("key_insights", [])),
                enrichment.get("content_type", "article"),
                enrichment.get("learning_value", "medium"),
                now,
            ))

            # Update bookmark status
            db.execute("UPDATE bookmarks SET status = 'enriched', title = COALESCE(NULLIF(title, url), ?) WHERE id = ?",
                        (bookmark["title"] or enrichment.get("summary", "")[:80], bookmark_id))

            # Create/link topics
            for topic_name in enrichment.get("topics", []):
                topic_name = topic_name.lower().strip()
                if not topic_name:
                    continue
                existing = db.execute("SELECT id FROM topics WHERE name = ?", (topic_name,)).fetchone()
                if existing:
                    topic_id = existing["id"]
                else:
                    db.execute("INSERT INTO topics (name) VALUES (?)", (topic_name,))
                    topic_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
                try:
                    db.execute("INSERT INTO bookmark_topics (bookmark_id, topic_id) VALUES (?, ?)", (bookmark_id, topic_id))
                except sqlite3.IntegrityError:
                    pass

            # Create/link author
            author_name = enrichment.get("author_name")
            if author_name:
                slug = author_name.lower().replace(" ", "-")
                existing = db.execute("SELECT id FROM experts WHERE id = ?", (slug,)).fetchone()
                if not existing:
                    db.execute("INSERT INTO experts (id, name, created_at) VALUES (?, ?, ?)", (slug, author_name, now))
                try:
                    db.execute("INSERT INTO bookmark_experts (bookmark_id, expert_id) VALUES (?, ?)", (bookmark_id, slug))
                except sqlite3.IntegrityError:
                    pass

            # Update FTS
            try:
                db.execute("DELETE FROM bookmarks_fts WHERE bookmark_id = ?", (bookmark_id,))
                db.execute(
                    "INSERT INTO bookmarks_fts (bookmark_id, title, summary, key_insights) VALUES (?, ?, ?, ?)",
                    (bookmark_id, bookmark["title"] or "", enrichment.get("summary", ""), text),
                )
            except Exception:
                pass

            db.commit()

            # Run automation rules
            try:
                run_rules_on_bookmark(db, bookmark_id)
            except Exception:
                pass

            db.close()
            return JSONResponse({
                "status": "enriched",
                "summary": enrichment.get("summary", ""),
                "topics": enrichment.get("topics", []),
                "learning_value": enrichment.get("learning_value"),
            })

    except Exception as e:
        db.close()
        return JSONResponse({"error": f"Enrichment failed: {e}"}, status_code=500)


@app.post("/api/discover/{bookmark_id}")
async def api_discover_related(bookmark_id: str):
    """Find 3-5 related URLs for a bookmark using web search. No API key needed."""
    db = get_db()
    bookmark = db.execute("""
        SELECT b.title, b.domain, c.summary
        FROM bookmarks b LEFT JOIN content c ON b.id = c.bookmark_id
        WHERE b.id = ?
    """, (bookmark_id,)).fetchone()
    if not bookmark:
        db.close()
        return JSONResponse({"error": "Not found"}, status_code=404)

    # Build a search query from title + summary keywords
    title = bookmark["title"] or ""
    summary = bookmark["summary"] or ""
    # Use title as primary query, trim to key phrase
    query = title[:80]
    if not query:
        query = summary[:80]

    if not query:
        db.close()
        return JSONResponse({"results": [], "query": ""})

    # Search using DuckDuckGo (no API key needed)
    try:
        resp = httpx.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": "Mozilla/5.0 curiosity/0.1"},
            timeout=10,
            follow_redirects=True,
        )
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        raw_results = []
        for link in soup.select(".result__a")[:8]:
            href = link.get("href", "")
            link_title = link.get_text(strip=True)
            if href and link_title:
                if "uddg=" in href:
                    from urllib.parse import parse_qs, urlparse as up
                    parsed = up(href)
                    qs = parse_qs(parsed.query)
                    href = qs.get("uddg", [href])[0]
                raw_results.append({"url": href, "title": link_title})
    except Exception:
        raw_results = []

    # Dedup against existing bookmarks
    existing = set()
    for row in db.execute("SELECT url FROM bookmarks").fetchall():
        existing.add(row["url"].rstrip("/").lower())

    results = []
    for r in raw_results:
        normalized = r["url"].rstrip("/").lower()
        if normalized not in existing and bookmark["domain"] not in normalized:
            results.append(r)
        if len(results) >= 5:
            break

    db.close()
    return JSONResponse({"results": results, "query": query})


@app.post("/api/save-discovered")
async def api_save_discovered(request: Request):
    """One-click save a discovered URL."""
    body = await request.json()
    url = body.get("url", "").strip()
    title = body.get("title", "").strip()
    triggered_by = body.get("triggered_by", "")
    if not url:
        return JSONResponse({"error": "No URL"}, status_code=400)

    bookmark_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    domain = url.replace("https://", "").replace("http://", "").split("/")[0]

    db = get_db()
    existing = db.execute("SELECT id FROM bookmarks WHERE url = ?", (url,)).fetchone()
    if existing:
        db.close()
        return JSONResponse({"id": existing["id"], "status": "exists"})

    db.execute(
        "INSERT INTO bookmarks (id, url, title, domain, source, added_at, status) VALUES (?, ?, ?, ?, 'discovery', ?, 'pending')",
        (bookmark_id, url, title or url, domain, now),
    )
    db.commit()

    # Record the discovery link
    if triggered_by:
        try:
            db.execute(
                "INSERT INTO discoveries (bookmark_id, triggered_by, search_query, relevance_score, discovered_at) VALUES (?, ?, ?, ?, ?)",
                (bookmark_id, triggered_by, "", 0.7, now),
            )
            db.commit()
        except Exception:
            pass

    db.close()
    return JSONResponse({"id": bookmark_id, "status": "saved"})


if __name__ == "__main__":
    import sys as _sys
    _host = "127.0.0.1"
    _port = 8080
    if "--host" in _sys.argv:
        _host = _sys.argv[_sys.argv.index("--host") + 1]
    if "--port" in _sys.argv:
        _port = int(_sys.argv[_sys.argv.index("--port") + 1])
    print(f"curiosity — http://{_host}:{_port}")
    uvicorn.run(app, host=_host, port=_port)
