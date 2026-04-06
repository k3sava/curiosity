"""SQLite database layer for Curiosity — schema, CRUD, FTS5, migrations."""

import json
import sqlite3
from pathlib import Path
from typing import Optional

from .models import Bookmark, Content, Expert, Topic, Connection, Discovery, Domain, now_iso

SCHEMA_VERSION = 1

SCHEMA_SQL = """
-- Every URL the system knows about
CREATE TABLE IF NOT EXISTS bookmarks (
    id              TEXT PRIMARY KEY,
    url             TEXT NOT NULL UNIQUE,
    final_url       TEXT,
    title           TEXT,
    domain          TEXT,
    source          TEXT NOT NULL DEFAULT 'manual',
    chrome_folder   TEXT,
    added_at        TEXT NOT NULL,
    chrome_added_at TEXT,
    status          TEXT DEFAULT 'pending',
    updated_at      TEXT
);

-- Fetched and AI-processed content
CREATE TABLE IF NOT EXISTS content (
    bookmark_id     TEXT PRIMARY KEY REFERENCES bookmarks(id),
    raw_text        TEXT,
    meta_description TEXT,
    summary         TEXT,
    key_insights    TEXT,  -- JSON array
    content_type    TEXT,
    learning_value  TEXT,
    word_count      INTEGER,
    fetched_at      TEXT,
    enriched_at     TEXT
);

-- Authors / experts
CREATE TABLE IF NOT EXISTS experts (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    expertise   TEXT,  -- JSON array
    perspective TEXT,
    credentials TEXT,
    home_url    TEXT,
    followed    INTEGER DEFAULT 0,
    created_at  TEXT,
    updated_at  TEXT
);

-- Bookmark ↔ Expert join
CREATE TABLE IF NOT EXISTS bookmark_experts (
    bookmark_id TEXT REFERENCES bookmarks(id),
    expert_id   TEXT REFERENCES experts(id),
    PRIMARY KEY (bookmark_id, expert_id)
);

-- Topic tags
CREATE TABLE IF NOT EXISTS topics (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT UNIQUE NOT NULL,
    category        TEXT,
    bookmark_count  INTEGER DEFAULT 0
);

-- Bookmark ↔ Topic join
CREATE TABLE IF NOT EXISTS bookmark_topics (
    bookmark_id TEXT REFERENCES bookmarks(id),
    topic_id    INTEGER REFERENCES topics(id),
    relevance   REAL DEFAULT 0.5,
    PRIMARY KEY (bookmark_id, topic_id)
);

-- Relationships between bookmarks
CREATE TABLE IF NOT EXISTS connections (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    bookmark_a      TEXT REFERENCES bookmarks(id),
    bookmark_b      TEXT REFERENCES bookmarks(id),
    connection_type TEXT,
    strength        REAL,
    explanation     TEXT,
    discovered_at   TEXT,
    UNIQUE(bookmark_a, bookmark_b, connection_type)
);

-- Research agent discoveries
CREATE TABLE IF NOT EXISTS discoveries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    bookmark_id     TEXT REFERENCES bookmarks(id),
    triggered_by    TEXT REFERENCES bookmarks(id),
    search_query    TEXT,
    relevance_score REAL,
    discovered_at   TEXT
);

-- Knowledge domains with gap tracking
CREATE TABLE IF NOT EXISTS domains (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    keywords        TEXT,  -- JSON array
    target_sources  INTEGER DEFAULT 20,
    priority        REAL DEFAULT 1.0,
    search_queries  TEXT,  -- JSON array
    updated_at      TEXT
);

-- Generated digests
CREATE TABLE IF NOT EXISTS digests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    period_start    TEXT,
    period_end      TEXT,
    digest_type     TEXT,
    content         TEXT,
    topics_covered  TEXT,  -- JSON
    gaps_identified TEXT,  -- JSON
    generated_at    TEXT
);

-- Full-text search
CREATE VIRTUAL TABLE IF NOT EXISTS bookmarks_fts USING fts5(
    bookmark_id,
    title,
    summary,
    key_insights,
    raw_text,
    tokenize='porter unicode61'
);

-- Sync tracking
CREATE TABLE IF NOT EXISTS sync_log (
    table_name  TEXT,
    row_id      TEXT,
    action      TEXT,
    synced_at   TEXT,
    PRIMARY KEY (table_name, row_id)
);

-- Schema version
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_bookmarks_domain ON bookmarks(domain);
CREATE INDEX IF NOT EXISTS idx_bookmarks_status ON bookmarks(status);
CREATE INDEX IF NOT EXISTS idx_bookmarks_source ON bookmarks(source);
CREATE INDEX IF NOT EXISTS idx_bookmarks_added ON bookmarks(added_at DESC);
CREATE INDEX IF NOT EXISTS idx_experts_followed ON experts(followed);
CREATE INDEX IF NOT EXISTS idx_content_value ON content(learning_value);
CREATE INDEX IF NOT EXISTS idx_content_type ON content(content_type);
CREATE INDEX IF NOT EXISTS idx_discoveries_trigger ON discoveries(triggered_by);
"""


class CuriosityDB:
    """SQLite database for Curiosity with FTS5 full-text search."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript(SCHEMA_SQL)
        # Set schema version
        self.conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            ("schema_version", str(SCHEMA_VERSION)),
        )
        self.conn.commit()

    def close(self):
        self.conn.close()

    # ── Bookmarks ─────────────────────────────────────────────

    def insert_bookmark(self, bookmark: Bookmark) -> Bookmark:
        """Insert a bookmark. Returns the bookmark (unchanged if URL already exists)."""
        try:
            self.conn.execute(
                """INSERT INTO bookmarks (id, url, final_url, title, domain, source,
                   chrome_folder, added_at, chrome_added_at, status, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (bookmark.id, bookmark.url, bookmark.final_url, bookmark.title,
                 bookmark.domain, bookmark.source, bookmark.chrome_folder,
                 bookmark.added_at, bookmark.chrome_added_at, bookmark.status,
                 bookmark.updated_at),
            )
            self.conn.commit()
            return bookmark
        except sqlite3.IntegrityError:
            # URL already exists — return existing
            row = self.conn.execute(
                "SELECT * FROM bookmarks WHERE url = ?", (bookmark.url,)
            ).fetchone()
            return Bookmark(**dict(row)) if row else bookmark

    def get_bookmark(self, bookmark_id: str) -> Optional[Bookmark]:
        row = self.conn.execute(
            "SELECT * FROM bookmarks WHERE id = ?", (bookmark_id,)
        ).fetchone()
        return Bookmark(**dict(row)) if row else None

    def get_bookmark_by_url(self, url: str) -> Optional[Bookmark]:
        row = self.conn.execute(
            "SELECT * FROM bookmarks WHERE url = ?", (url,)
        ).fetchone()
        return Bookmark(**dict(row)) if row else None

    def update_bookmark_status(self, bookmark_id: str, status: str):
        self.conn.execute(
            "UPDATE bookmarks SET status = ?, updated_at = ? WHERE id = ?",
            (status, now_iso(), bookmark_id),
        )
        self.conn.commit()

    def get_bookmarks_by_status(self, status: str, limit: int = 100) -> list[Bookmark]:
        rows = self.conn.execute(
            "SELECT * FROM bookmarks WHERE status = ? ORDER BY added_at DESC LIMIT ?",
            (status, limit),
        ).fetchall()
        return [Bookmark(**dict(r)) for r in rows]

    def get_recent_bookmarks(self, limit: int = 20) -> list[dict]:
        """Get recent bookmarks with their content summaries."""
        rows = self.conn.execute(
            """SELECT b.*, c.summary, c.content_type, c.learning_value, c.key_insights
               FROM bookmarks b
               LEFT JOIN content c ON b.id = c.bookmark_id
               ORDER BY b.added_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def count_bookmarks(self, source: Optional[str] = None) -> int:
        if source:
            row = self.conn.execute(
                "SELECT COUNT(*) FROM bookmarks WHERE source = ?", (source,)
            ).fetchone()
        else:
            row = self.conn.execute("SELECT COUNT(*) FROM bookmarks").fetchone()
        return row[0]

    # ── Content ───────────────────────────────────────────────

    def upsert_content(self, content: Content):
        """Insert or update content for a bookmark."""
        insights_json = json.dumps(content.key_insights) if content.key_insights else None
        self.conn.execute(
            """INSERT OR REPLACE INTO content
               (bookmark_id, raw_text, meta_description, summary, key_insights,
                content_type, learning_value, word_count, fetched_at, enriched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (content.bookmark_id, content.raw_text, content.meta_description,
             content.summary, insights_json, content.content_type,
             content.learning_value, content.word_count,
             content.fetched_at, content.enriched_at),
        )
        self.conn.commit()

        # Update FTS index
        self._update_fts(content)

    def get_content(self, bookmark_id: str) -> Optional[Content]:
        row = self.conn.execute(
            "SELECT * FROM content WHERE bookmark_id = ?", (bookmark_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        if d.get("key_insights"):
            d["key_insights"] = json.loads(d["key_insights"])
        return Content(**d)

    # ── FTS ────────────────────────────────────────────────────

    def _update_fts(self, content: Content):
        """Update full-text search index for a bookmark."""
        bookmark = self.get_bookmark(content.bookmark_id)
        if not bookmark:
            return

        # Delete existing FTS entry
        self.conn.execute(
            "DELETE FROM bookmarks_fts WHERE bookmark_id = ?", (content.bookmark_id,)
        )

        insights_text = " | ".join(content.key_insights) if content.key_insights else ""

        self.conn.execute(
            """INSERT INTO bookmarks_fts (bookmark_id, title, summary, key_insights, raw_text)
               VALUES (?, ?, ?, ?, ?)""",
            (content.bookmark_id, bookmark.title or "", content.summary or "",
             insights_text, (content.raw_text or "")[:5000]),  # limit raw text in FTS
        )
        self.conn.commit()

    def search(self, query: str, limit: int = 20) -> list[dict]:
        """Full-text search across bookmarks."""
        rows = self.conn.execute(
            """SELECT b.*, c.summary, c.content_type, c.learning_value, c.key_insights,
                      bm25(bookmarks_fts) as rank
               FROM bookmarks_fts fts
               JOIN bookmarks b ON fts.bookmark_id = b.id
               LEFT JOIN content c ON b.id = c.bookmark_id
               WHERE bookmarks_fts MATCH ?
               ORDER BY rank
               LIMIT ?""",
            (query, limit),
        ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            if d.get("key_insights"):
                try:
                    d["key_insights"] = json.loads(d["key_insights"])
                except (json.JSONDecodeError, TypeError):
                    pass
            results.append(d)
        return results

    # ── Topics ─────────────────────────────────────────────────

    def get_or_create_topic(self, name: str, category: Optional[str] = None) -> int:
        """Get topic ID by name, creating if needed."""
        name = name.lower().strip()
        row = self.conn.execute(
            "SELECT id FROM topics WHERE name = ?", (name,)
        ).fetchone()
        if row:
            return row[0]

        cursor = self.conn.execute(
            "INSERT INTO topics (name, category, bookmark_count) VALUES (?, ?, 0)",
            (name, category),
        )
        self.conn.commit()
        return cursor.lastrowid

    def link_bookmark_topic(self, bookmark_id: str, topic_id: int, relevance: float = 0.5):
        try:
            self.conn.execute(
                "INSERT INTO bookmark_topics (bookmark_id, topic_id, relevance) VALUES (?, ?, ?)",
                (bookmark_id, topic_id, relevance),
            )
            self.conn.execute(
                "UPDATE topics SET bookmark_count = bookmark_count + 1 WHERE id = ?",
                (topic_id,),
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass  # already linked

    def get_topics(self, min_count: int = 1, limit: int = 100) -> list[dict]:
        rows = self.conn.execute(
            """SELECT * FROM topics WHERE bookmark_count >= ?
               ORDER BY bookmark_count DESC LIMIT ?""",
            (min_count, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_bookmark_topics(self, bookmark_id: str) -> list[dict]:
        rows = self.conn.execute(
            """SELECT t.* FROM topics t
               JOIN bookmark_topics bt ON t.id = bt.topic_id
               WHERE bt.bookmark_id = ?
               ORDER BY bt.relevance DESC""",
            (bookmark_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Experts ────────────────────────────────────────────────

    def upsert_expert(self, expert: Expert) -> Expert:
        expertise_json = json.dumps(expert.expertise) if expert.expertise else None
        self.conn.execute(
            """INSERT OR REPLACE INTO experts
               (id, name, expertise, perspective, credentials, home_url,
                followed, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (expert.id, expert.name, expertise_json, expert.perspective,
             expert.credentials, expert.home_url, int(expert.followed),
             expert.created_at, expert.updated_at),
        )
        self.conn.commit()
        return expert

    def link_bookmark_expert(self, bookmark_id: str, expert_id: str):
        try:
            self.conn.execute(
                "INSERT INTO bookmark_experts (bookmark_id, expert_id) VALUES (?, ?)",
                (bookmark_id, expert_id),
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass

    def get_expert(self, expert_id: str) -> Optional[Expert]:
        row = self.conn.execute(
            "SELECT * FROM experts WHERE id = ?", (expert_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["followed"] = bool(d.get("followed", 0))
        if d.get("expertise"):
            d["expertise"] = json.loads(d["expertise"])
        return Expert(**d)

    # ── Stats ──────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Overview statistics for the knowledge base."""
        total = self.count_bookmarks()
        by_source = {}
        for row in self.conn.execute(
            "SELECT source, COUNT(*) as cnt FROM bookmarks GROUP BY source"
        ).fetchall():
            by_source[row["source"]] = row["cnt"]

        by_status = {}
        for row in self.conn.execute(
            "SELECT status, COUNT(*) as cnt FROM bookmarks GROUP BY status"
        ).fetchall():
            by_status[row["status"]] = row["cnt"]

        enriched = self.conn.execute(
            "SELECT COUNT(*) FROM content WHERE summary IS NOT NULL"
        ).fetchone()[0]

        experts_count = self.conn.execute("SELECT COUNT(*) FROM experts").fetchone()[0]
        topics_count = self.conn.execute("SELECT COUNT(*) FROM topics").fetchone()[0]
        domains_count = self.conn.execute(
            "SELECT COUNT(DISTINCT domain) FROM bookmarks"
        ).fetchone()[0]

        top_domains = self.conn.execute(
            """SELECT domain, COUNT(*) as cnt FROM bookmarks
               GROUP BY domain ORDER BY cnt DESC LIMIT 10"""
        ).fetchall()

        top_topics = self.get_topics(min_count=2, limit=10)

        return {
            "total_bookmarks": total,
            "by_source": by_source,
            "by_status": by_status,
            "enriched": enriched,
            "experts": experts_count,
            "topics": topics_count,
            "unique_domains": domains_count,
            "top_domains": [{"domain": r["domain"], "count": r["cnt"]} for r in top_domains],
            "top_topics": top_topics,
        }
