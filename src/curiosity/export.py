"""Export bookmarks as markdown — compatible with Artemis, Obsidian, and plain files.

Supports three formats:
- artemis: YAML frontmatter + Artemis knowledge structure (for import into Artemis project)
- obsidian: Obsidian-style with tags, backlinks, and wiki-links
- plain: Clean markdown for general use
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from .db import CuriosityDB
from .models import now_iso


def export_bookmark(
    bookmark_id: str,
    db: CuriosityDB,
    output_dir: Path,
    format: str = "plain",
) -> Optional[Path]:
    """Export a single bookmark as a markdown file.

    Returns the output file path, or None if bookmark not found.
    """
    bookmark = db.get_bookmark(bookmark_id)
    if not bookmark:
        return None

    content = db.get_content(bookmark_id)
    topics = db.get_bookmark_topics(bookmark_id)
    topic_names = [t["name"] for t in topics]

    # Get expert info
    expert_rows = db.conn.execute(
        """SELECT e.* FROM experts e
           JOIN bookmark_experts be ON e.id = be.expert_id
           WHERE be.bookmark_id = ?""",
        (bookmark_id,),
    ).fetchall()
    experts = [dict(r) for r in expert_rows]

    # Build filename from title
    slug = _slugify(bookmark.title or bookmark.domain or "untitled")
    filename = f"{slug}.md"

    if format == "artemis":
        md = _format_artemis(bookmark, content, topic_names, experts)
    elif format == "obsidian":
        md = _format_obsidian(bookmark, content, topic_names, experts)
    else:
        md = _format_plain(bookmark, content, topic_names, experts)

    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / filename
    filepath.write_text(md, encoding="utf-8")
    return filepath


def export_all(
    db: CuriosityDB,
    output_dir: Path,
    format: str = "plain",
    status: Optional[str] = None,
    limit: int = 0,
) -> list[Path]:
    """Export all bookmarks (optionally filtered by status).

    Returns list of exported file paths.
    """
    query = "SELECT id FROM bookmarks"
    params = []

    if status:
        query += " WHERE status = ?"
        params.append(status)

    query += " ORDER BY added_at DESC"

    if limit > 0:
        query += " LIMIT ?"
        params.append(limit)

    rows = db.conn.execute(query, params).fetchall()
    exported = []

    for row in rows:
        path = export_bookmark(row["id"], db, output_dir, format=format)
        if path:
            exported.append(path)

    return exported


def export_digest(
    db: CuriosityDB,
    output_dir: Path,
    digest_type: str = "daily",
) -> Optional[Path]:
    """Export the latest digest as a markdown file."""
    from .digest import get_latest_digest

    digest = get_latest_digest(db, digest_type)
    if not digest:
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    filename = f"curiosity-digest-{date_str}.md"
    filepath = output_dir / filename
    filepath.write_text(digest.get("content", ""), encoding="utf-8")
    return filepath


# ── Format Helpers ────────────────────────────────────────────


def _format_artemis(bookmark, content, topics, experts) -> str:
    """Artemis-compatible format: YAML frontmatter matching Artemis's knowledge/sources structure."""
    lines = ["---"]

    lines.append(f"title: \"{_yaml_escape(bookmark.title or '')}\"")
    lines.append(f"url: \"{bookmark.url}\"")
    lines.append(f"domain: \"{bookmark.domain or ''}\"")

    if experts:
        lines.append(f"author: \"{experts[0].get('name', '')}\"")
        lines.append(f"author_slug: \"{experts[0].get('id', '')}\"")

    if content and content.content_type:
        lines.append(f"content_type: \"{content.content_type}\"")

    if content and content.learning_value:
        lines.append(f"learning_value: \"{content.learning_value}\"")

    if topics:
        lines.append("topics:")
        for t in topics:
            lines.append(f"  - \"{t}\"")

    lines.append(f"source: \"{bookmark.source}\"")
    lines.append(f"ingested_at: \"{bookmark.added_at}\"")

    if bookmark.chrome_folder:
        lines.append(f"chrome_folder: \"{bookmark.chrome_folder}\"")

    lines.append(f"status: \"{bookmark.status}\"")
    lines.append("---")
    lines.append("")

    # Title
    lines.append(f"# {bookmark.title or bookmark.url}")
    lines.append("")

    # Summary
    if content and content.summary:
        lines.append("## Summary")
        lines.append("")
        lines.append(content.summary)
        lines.append("")

    # Key Insights
    if content and content.key_insights:
        lines.append("## Key Insights")
        lines.append("")
        for insight in content.key_insights:
            lines.append(f"- {insight}")
        lines.append("")

    # Expert info
    if experts:
        lines.append("## Author")
        lines.append("")
        for e in experts:
            expertise = json.loads(e["expertise"]) if e.get("expertise") else []
            lines.append(f"**{e['name']}**")
            if expertise:
                lines.append(f"Expertise: {', '.join(expertise)}")
            if e.get("home_url"):
                lines.append(f"Home: {e['home_url']}")
        lines.append("")

    # Source link
    lines.append("## Source")
    lines.append("")
    lines.append(f"[{bookmark.title or bookmark.url}]({bookmark.url})")
    lines.append("")

    return "\n".join(lines)


def _format_obsidian(bookmark, content, topics, experts) -> str:
    """Obsidian-compatible format with tags, wiki-links, and backlinks."""
    lines = ["---"]

    lines.append(f"title: \"{_yaml_escape(bookmark.title or '')}\"")
    lines.append(f"url: \"{bookmark.url}\"")
    lines.append(f"domain: \"{bookmark.domain or ''}\"")
    lines.append(f"created: \"{bookmark.added_at}\"")

    if content and content.content_type:
        lines.append(f"type: \"{content.content_type}\"")

    if topics:
        lines.append("tags:")
        for t in topics:
            lines.append(f"  - {t.replace(' ', '-')}")

    lines.append("---")
    lines.append("")

    # Title
    lines.append(f"# {bookmark.title or bookmark.url}")
    lines.append("")

    # Summary
    if content and content.summary:
        lines.append(content.summary)
        lines.append("")

    # Key Insights
    if content and content.key_insights:
        lines.append("## Key Insights")
        lines.append("")
        for insight in content.key_insights:
            lines.append(f"- {insight}")
        lines.append("")

    # Topics as wiki-links
    if topics:
        lines.append("## Topics")
        lines.append("")
        topic_links = [f"[[{t}]]" for t in topics]
        lines.append(" · ".join(topic_links))
        lines.append("")

    # Author as wiki-link
    if experts:
        lines.append("## Author")
        lines.append("")
        for e in experts:
            lines.append(f"[[{e['name']}]]")
        lines.append("")

    # Source
    lines.append(f"[Source]({bookmark.url})")
    lines.append("")

    return "\n".join(lines)


def _format_plain(bookmark, content, topics, experts) -> str:
    """Clean markdown — no special syntax."""
    lines = [f"# {bookmark.title or bookmark.url}"]
    lines.append("")
    lines.append(f"**URL:** {bookmark.url}")
    lines.append(f"**Domain:** {bookmark.domain or 'unknown'}")

    if experts:
        names = [e["name"] for e in experts]
        lines.append(f"**Author:** {', '.join(names)}")

    if content and content.content_type:
        lines.append(f"**Type:** {content.content_type}")

    if content and content.learning_value:
        lines.append(f"**Value:** {content.learning_value}")

    if topics:
        lines.append(f"**Topics:** {', '.join(topics)}")

    lines.append(f"**Added:** {bookmark.added_at[:10]}")
    lines.append("")

    if content and content.summary:
        lines.append("## Summary")
        lines.append("")
        lines.append(content.summary)
        lines.append("")

    if content and content.key_insights:
        lines.append("## Key Insights")
        lines.append("")
        for insight in content.key_insights:
            lines.append(f"- {insight}")
        lines.append("")

    return "\n".join(lines)


# ── Utilities ─────────────────────────────────────────────────


def _slugify(text: str) -> str:
    """Convert text to a filename-safe slug."""
    import re
    slug = text.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    slug = slug[:80].rstrip('-')
    return slug or "untitled"


def _yaml_escape(text: str) -> str:
    """Escape text for YAML string values."""
    return text.replace('"', '\\"').replace("\n", " ")
