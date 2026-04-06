"""Discover relationships between bookmarks — topic overlap, same author, references."""

import json
from collections import defaultdict
from typing import Optional

from .db import CuriosityDB
from .models import Connection, now_iso


def find_topic_connections(
    db: CuriosityDB,
    bookmark_id: Optional[str] = None,
    min_overlap: int = 2,
    limit: int = 20,
) -> list[dict]:
    """Find bookmarks connected by shared topics.

    If bookmark_id is given, find connections to that specific bookmark.
    Otherwise, find the strongest connections across the entire knowledge base.
    """
    if bookmark_id:
        # Find bookmarks sharing topics with the given bookmark
        rows = db.conn.execute(
            """SELECT b2.id, b2.title, b2.url, b2.domain,
                      COUNT(DISTINCT bt2.topic_id) as shared_topics,
                      GROUP_CONCAT(DISTINCT t.name) as topic_names
               FROM bookmark_topics bt1
               JOIN bookmark_topics bt2 ON bt1.topic_id = bt2.topic_id AND bt1.bookmark_id != bt2.bookmark_id
               JOIN bookmarks b2 ON bt2.bookmark_id = b2.id
               JOIN topics t ON bt1.topic_id = t.id
               WHERE bt1.bookmark_id = ?
               GROUP BY b2.id
               HAVING shared_topics >= ?
               ORDER BY shared_topics DESC
               LIMIT ?""",
            (bookmark_id, min_overlap, limit),
        ).fetchall()
    else:
        # Find strongest connections across entire KB
        rows = db.conn.execute(
            """SELECT bt1.bookmark_id as id_a, bt2.bookmark_id as id_b,
                      b1.title as title_a, b2.title as title_b,
                      COUNT(DISTINCT bt1.topic_id) as shared_topics,
                      GROUP_CONCAT(DISTINCT t.name) as topic_names
               FROM bookmark_topics bt1
               JOIN bookmark_topics bt2 ON bt1.topic_id = bt2.topic_id
                    AND bt1.bookmark_id < bt2.bookmark_id
               JOIN bookmarks b1 ON bt1.bookmark_id = b1.id
               JOIN bookmarks b2 ON bt2.bookmark_id = b2.id
               JOIN topics t ON bt1.topic_id = t.id
               GROUP BY bt1.bookmark_id, bt2.bookmark_id
               HAVING shared_topics >= ?
               ORDER BY shared_topics DESC
               LIMIT ?""",
            (min_overlap, limit),
        ).fetchall()

    return [dict(r) for r in rows]


def find_author_connections(db: CuriosityDB, bookmark_id: Optional[str] = None) -> list[dict]:
    """Find bookmarks by the same author/expert."""
    if bookmark_id:
        rows = db.conn.execute(
            """SELECT b2.id, b2.title, b2.url, b2.domain, e.name as expert_name
               FROM bookmark_experts be1
               JOIN bookmark_experts be2 ON be1.expert_id = be2.expert_id
                    AND be1.bookmark_id != be2.bookmark_id
               JOIN bookmarks b2 ON be2.bookmark_id = b2.id
               JOIN experts e ON be1.expert_id = e.id
               WHERE be1.bookmark_id = ?
               ORDER BY b2.added_at DESC""",
            (bookmark_id,),
        ).fetchall()
    else:
        rows = db.conn.execute(
            """SELECT e.name as expert_name, e.id as expert_id,
                      COUNT(be.bookmark_id) as article_count
               FROM experts e
               JOIN bookmark_experts be ON e.id = be.expert_id
               GROUP BY e.id
               HAVING article_count >= 2
               ORDER BY article_count DESC
               LIMIT 20""",
        ).fetchall()

    return [dict(r) for r in rows]


def find_domain_clusters(db: CuriosityDB, min_count: int = 3) -> list[dict]:
    """Find clusters of bookmarks from the same domain."""
    rows = db.conn.execute(
        """SELECT domain, COUNT(*) as count,
                  GROUP_CONCAT(title, ' | ') as titles
           FROM bookmarks
           WHERE domain != ''
           GROUP BY domain
           HAVING count >= ?
           ORDER BY count DESC
           LIMIT 20""",
        (min_count,),
    ).fetchall()
    return [dict(r) for r in rows]


def store_connections(
    db: CuriosityDB,
    bookmark_id: str,
    connected: list[dict],
    connection_type: str = "same_topic",
):
    """Store discovered connections in the database."""
    for c in connected:
        other_id = c.get("id", c.get("id_b"))
        if not other_id or other_id == bookmark_id:
            continue

        shared = c.get("shared_topics", 1)
        strength = min(1.0, shared / 5.0)  # Normalize: 5+ shared topics = strength 1.0
        explanation = c.get("topic_names", "")

        try:
            # Ensure consistent ordering
            a, b = sorted([bookmark_id, other_id])
            db.conn.execute(
                """INSERT OR REPLACE INTO connections
                   (bookmark_a, bookmark_b, connection_type, strength, explanation, discovered_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (a, b, connection_type, strength, explanation, now_iso()),
            )
        except Exception:
            continue

    db.conn.commit()


def get_connections(db: CuriosityDB, bookmark_id: str) -> list[dict]:
    """Get all stored connections for a bookmark."""
    rows = db.conn.execute(
        """SELECT c.*,
                  CASE WHEN c.bookmark_a = ? THEN b2.title ELSE b1.title END as connected_title,
                  CASE WHEN c.bookmark_a = ? THEN b2.url ELSE b1.url END as connected_url,
                  CASE WHEN c.bookmark_a = ? THEN c.bookmark_b ELSE c.bookmark_a END as connected_id
           FROM connections c
           JOIN bookmarks b1 ON c.bookmark_a = b1.id
           JOIN bookmarks b2 ON c.bookmark_b = b2.id
           WHERE c.bookmark_a = ? OR c.bookmark_b = ?
           ORDER BY c.strength DESC""",
        (bookmark_id, bookmark_id, bookmark_id, bookmark_id, bookmark_id),
    ).fetchall()
    return [dict(r) for r in rows]


def build_all_connections(db: CuriosityDB, min_overlap: int = 2):
    """Rebuild all topic-based connections across the knowledge base.

    Call after a bulk import or periodically to refresh connections.
    """
    pairs = find_topic_connections(db, min_overlap=min_overlap, limit=500)

    count = 0
    for pair in pairs:
        a = pair.get("id_a")
        b = pair.get("id_b")
        if not a or not b:
            continue

        shared = pair.get("shared_topics", 1)
        strength = min(1.0, shared / 5.0)
        topics = pair.get("topic_names", "")

        try:
            a_sorted, b_sorted = sorted([a, b])
            db.conn.execute(
                """INSERT OR REPLACE INTO connections
                   (bookmark_a, bookmark_b, connection_type, strength, explanation, discovered_at)
                   VALUES (?, ?, 'same_topic', ?, ?, ?)""",
                (a_sorted, b_sorted, strength, topics, now_iso()),
            )
            count += 1
        except Exception:
            continue

    db.conn.commit()
    return count
