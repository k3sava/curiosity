"""Supabase cloud sync — push local SQLite state to Postgres mirror.

Push-only architecture: SQLite is the source of truth, Supabase is a read mirror
for future web UI, mobile, and multi-device access.

Uses the sync_log table to track what's been pushed, so only changes get synced.
"""

import json
import time
import threading
from datetime import datetime
from typing import Optional

from .db import CuriosityDB
from .config import CuriosityConfig
from .models import now_iso


class SupabaseSync:
    """Push changes from local SQLite to Supabase."""

    def __init__(self, db: CuriosityDB, config: CuriosityConfig):
        self.db = db
        self.config = config
        self._client = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

    @property
    def client(self):
        if self._client is None:
            if not self.config.supabase_url or not self.config.supabase_key:
                raise ValueError("Supabase credentials not configured")
            from supabase import create_client
            self._client = create_client(self.config.supabase_url, self.config.supabase_key)
        return self._client

    @property
    def is_configured(self) -> bool:
        return bool(self.config.supabase_url and self.config.supabase_key)

    def sync_all(self) -> dict:
        """Full sync: push all unsynced changes to Supabase.

        Returns counts of synced items per table.
        """
        if not self.is_configured:
            return {"error": "Supabase not configured"}

        results = {
            "bookmarks": self._sync_bookmarks(),
            "content": self._sync_content(),
            "experts": self._sync_experts(),
            "topics": self._sync_topics(),
            "timestamp": now_iso(),
        }
        return results

    def _sync_bookmarks(self) -> int:
        """Push new/updated bookmarks to Supabase."""
        # Find bookmarks not yet synced or updated since last sync
        rows = self.db.conn.execute(
            """SELECT b.* FROM bookmarks b
               LEFT JOIN sync_log sl ON sl.table_name = 'bookmarks' AND sl.row_id = b.id
               WHERE sl.synced_at IS NULL
                  OR b.updated_at > sl.synced_at
               ORDER BY b.added_at DESC
               LIMIT 500"""
        ).fetchall()

        if not rows:
            return 0

        count = 0
        for row in rows:
            d = dict(row)
            try:
                self.client.table("bookmarks").upsert(d).execute()
                self._mark_synced("bookmarks", d["id"])
                count += 1
            except Exception as e:
                continue

        return count

    def _sync_content(self) -> int:
        """Push content records to Supabase."""
        rows = self.db.conn.execute(
            """SELECT c.* FROM content c
               LEFT JOIN sync_log sl ON sl.table_name = 'content' AND sl.row_id = c.bookmark_id
               WHERE sl.synced_at IS NULL
                  OR c.enriched_at > sl.synced_at
               LIMIT 500"""
        ).fetchall()

        if not rows:
            return 0

        count = 0
        for row in rows:
            d = dict(row)
            # key_insights is already JSON string from SQLite
            try:
                self.client.table("content").upsert(d).execute()
                self._mark_synced("content", d["bookmark_id"])
                count += 1
            except Exception:
                continue

        return count

    def _sync_experts(self) -> int:
        """Push expert records to Supabase."""
        rows = self.db.conn.execute(
            """SELECT e.* FROM experts e
               LEFT JOIN sync_log sl ON sl.table_name = 'experts' AND sl.row_id = e.id
               WHERE sl.synced_at IS NULL
                  OR e.updated_at > sl.synced_at
               LIMIT 200"""
        ).fetchall()

        if not rows:
            return 0

        count = 0
        for row in rows:
            d = dict(row)
            d["followed"] = bool(d.get("followed", 0))
            try:
                self.client.table("experts").upsert(d).execute()
                self._mark_synced("experts", d["id"])
                count += 1
            except Exception:
                continue

        return count

    def _sync_topics(self) -> int:
        """Push topic records to Supabase."""
        rows = self.db.conn.execute(
            """SELECT t.* FROM topics t
               LEFT JOIN sync_log sl ON sl.table_name = 'topics'
                    AND sl.row_id = CAST(t.id AS TEXT)
               WHERE sl.synced_at IS NULL
               LIMIT 500"""
        ).fetchall()

        if not rows:
            return 0

        count = 0
        for row in rows:
            d = dict(row)
            try:
                self.client.table("topics").upsert(d).execute()
                self._mark_synced("topics", str(d["id"]))
                count += 1
            except Exception:
                continue

        return count

    def _mark_synced(self, table: str, row_id: str):
        """Record that a row has been synced."""
        self.db.conn.execute(
            """INSERT OR REPLACE INTO sync_log (table_name, row_id, action, synced_at)
               VALUES (?, ?, 'upsert', ?)""",
            (table, row_id, now_iso()),
        )
        self.db.conn.commit()

    # ── Background Sync ───────────────────────────────────────

    def start_background(self):
        """Start periodic background sync."""
        if not self.is_configured or self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._sync_loop, daemon=True)
        self._thread.start()

    def stop_background(self):
        """Stop background sync."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)

    def _sync_loop(self):
        while self._running:
            try:
                self.sync_all()
            except Exception:
                pass
            time.sleep(self.config.sync_interval)

    # ── Stats ─────────────────────────────────────────────────

    def get_sync_status(self) -> dict:
        """Get sync status: what's been synced, what's pending."""
        synced = self.db.conn.execute(
            "SELECT table_name, COUNT(*) as cnt FROM sync_log GROUP BY table_name"
        ).fetchall()
        synced_counts = {r["table_name"]: r["cnt"] for r in synced}

        total_bookmarks = self.db.count_bookmarks()
        total_content = self.db.conn.execute("SELECT COUNT(*) FROM content").fetchone()[0]
        total_experts = self.db.conn.execute("SELECT COUNT(*) FROM experts").fetchone()[0]

        last_sync = self.db.conn.execute(
            "SELECT MAX(synced_at) FROM sync_log"
        ).fetchone()[0]

        return {
            "configured": self.is_configured,
            "last_sync": last_sync,
            "bookmarks": {
                "total": total_bookmarks,
                "synced": synced_counts.get("bookmarks", 0),
                "pending": total_bookmarks - synced_counts.get("bookmarks", 0),
            },
            "content": {
                "total": total_content,
                "synced": synced_counts.get("content", 0),
                "pending": total_content - synced_counts.get("content", 0),
            },
            "experts": {
                "total": total_experts,
                "synced": synced_counts.get("experts", 0),
                "pending": total_experts - synced_counts.get("experts", 0),
            },
        }
