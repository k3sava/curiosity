"""Daily and weekly learning digest generation."""

import json
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from typing import Optional

from .db import CuriosityDB
from .gaps import get_knowledge_gaps
from .models import now_iso


def generate_digest(
    db: CuriosityDB,
    period: str = "daily",
    date: Optional[str] = None,
) -> dict:
    """Generate a learning digest for a given period.

    Returns structured data + formatted markdown.
    """
    if date:
        end_date = datetime.fromisoformat(date)
    else:
        end_date = datetime.utcnow()

    if period == "daily":
        start_date = end_date - timedelta(days=1)
    elif period == "weekly":
        start_date = end_date - timedelta(days=7)
    else:
        start_date = end_date - timedelta(days=1)

    start_iso = start_date.isoformat()
    end_iso = end_date.isoformat()

    # ── Gather data ──────────────────────────────────────────

    # New bookmarks in period
    new_bookmarks = db.conn.execute(
        """SELECT b.*, c.summary, c.content_type, c.learning_value, c.key_insights
           FROM bookmarks b
           LEFT JOIN content c ON b.id = c.bookmark_id
           WHERE b.added_at >= ? AND b.added_at <= ?
           ORDER BY b.added_at DESC""",
        (start_iso, end_iso),
    ).fetchall()
    new_bookmarks = [dict(r) for r in new_bookmarks]

    # Split by source
    user_bookmarks = [b for b in new_bookmarks if b["source"] in ("chrome", "manual")]
    agent_bookmarks = [b for b in new_bookmarks if b["source"] == "research_agent"]

    # Cluster by topic
    topic_clusters = defaultdict(list)
    for b in new_bookmarks:
        topics = db.get_bookmark_topics(b["id"])
        if topics:
            primary_topic = topics[0]["name"]
            topic_clusters[primary_topic].append(b)
        else:
            topic_clusters["uncategorized"].append(b)

    # Content type distribution
    type_counts = Counter(b.get("content_type", "other") for b in new_bookmarks)

    # Learning value distribution
    value_counts = Counter(b.get("learning_value", "unknown") for b in new_bookmarks)

    # Collect all key insights
    all_insights = []
    for b in new_bookmarks:
        insights = b.get("key_insights")
        if insights:
            if isinstance(insights, str):
                try:
                    insights = json.loads(insights)
                except (json.JSONDecodeError, TypeError):
                    insights = []
            for insight in insights:
                all_insights.append({
                    "insight": insight,
                    "title": b.get("title", ""),
                    "bookmark_id": b.get("id"),
                })

    # New discoveries in period
    discoveries = db.conn.execute(
        """SELECT d.*, b.title, b.url, b.domain
           FROM discoveries d
           JOIN bookmarks b ON d.bookmark_id = b.id
           WHERE d.discovered_at >= ? AND d.discovered_at <= ?""",
        (start_iso, end_iso),
    ).fetchall()
    discoveries = [dict(r) for r in discoveries]

    # Knowledge gaps
    gaps = get_knowledge_gaps(db, limit=5)
    critical_gaps = [g for g in gaps if g["status"] == "critical"]

    # Followed experts with new content
    expert_updates = db.conn.execute(
        """SELECT e.name, e.id as expert_id, COUNT(be.bookmark_id) as new_count
           FROM experts e
           JOIN bookmark_experts be ON e.id = be.expert_id
           JOIN bookmarks b ON be.bookmark_id = b.id
           WHERE e.followed = 1 AND b.added_at >= ? AND b.added_at <= ?
           GROUP BY e.id""",
        (start_iso, end_iso),
    ).fetchall()
    expert_updates = [dict(r) for r in expert_updates]

    # ── Format markdown ──────────────────────────────────────

    period_label = "Today" if period == "daily" else "This Week"
    date_label = end_date.strftime("%B %d, %Y")

    md_lines = [
        f"# Curiosity Digest — {date_label}",
        f"*{period_label}: {len(new_bookmarks)} new items in your knowledge base*",
        "",
    ]

    # Summary stats
    if new_bookmarks:
        md_lines.append(f"**{len(user_bookmarks)}** saved by you · **{len(agent_bookmarks)}** discovered by Curiosity")
        if value_counts.get("high"):
            md_lines.append(f"**{value_counts['high']}** high-value finds")
        md_lines.append("")

    # Topic clusters
    if topic_clusters:
        md_lines.append("## By Topic")
        md_lines.append("")
        for topic, bookmarks in sorted(topic_clusters.items(), key=lambda x: -len(x[1])):
            if topic == "uncategorized" and len(bookmarks) < 2:
                continue
            md_lines.append(f"### {topic.title()} ({len(bookmarks)})")
            for b in bookmarks[:5]:
                summary_short = (b.get("summary", "") or "")[:100]
                md_lines.append(f"- [{b['title'][:60]}]({b['url']}) — {summary_short}")
            if len(bookmarks) > 5:
                md_lines.append(f"  *...and {len(bookmarks) - 5} more*")
            md_lines.append("")

    # Key insights
    if all_insights:
        md_lines.append("## Key Insights")
        md_lines.append("")
        for item in all_insights[:10]:
            md_lines.append(f"- {item['insight']} *(from {item['title'][:40]})*")
        md_lines.append("")

    # Expert updates
    if expert_updates:
        md_lines.append("## Followed Experts")
        md_lines.append("")
        for eu in expert_updates:
            md_lines.append(f"- **{eu['name']}**: {eu['new_count']} new article(s)")
        md_lines.append("")

    # Knowledge gaps
    if critical_gaps:
        md_lines.append("## Knowledge Gaps")
        md_lines.append("")
        for g in critical_gaps[:3]:
            md_lines.append(f"- **{g['name']}** — {g['coverage_pct']}% coverage (target: {g['target_sources']})")
            if g.get("search_queries"):
                md_lines.append(f"  Try: \"{g['search_queries'][0]}\"")
        md_lines.append("")

    # Recommendations
    md_lines.append("## Suggested Next")
    md_lines.append("")
    if critical_gaps:
        md_lines.append(f"- Fill gap: \"{critical_gaps[0]['name']}\" — search for \"{critical_gaps[0].get('search_queries', [''])[0]}\"")
    if not new_bookmarks:
        md_lines.append("- No new content this period — bookmark something interesting!")
    md_lines.append("")

    markdown = "\n".join(md_lines)

    # ── Store digest ─────────────────────────────────────────

    topics_covered = list(topic_clusters.keys())
    gaps_identified = [g["domain"] for g in critical_gaps]

    db.conn.execute(
        """INSERT INTO digests (period_start, period_end, digest_type, content,
           topics_covered, gaps_identified, generated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (start_iso, end_iso, period, markdown,
         json.dumps(topics_covered), json.dumps(gaps_identified), now_iso()),
    )
    db.conn.commit()

    return {
        "period": period,
        "start": start_iso,
        "end": end_iso,
        "new_bookmarks": len(new_bookmarks),
        "user_bookmarks": len(user_bookmarks),
        "agent_bookmarks": len(agent_bookmarks),
        "topics": len(topic_clusters),
        "insights": len(all_insights),
        "critical_gaps": len(critical_gaps),
        "expert_updates": len(expert_updates),
        "markdown": markdown,
    }


def get_latest_digest(db: CuriosityDB, digest_type: str = "daily") -> Optional[dict]:
    """Get the most recent digest."""
    row = db.conn.execute(
        """SELECT * FROM digests WHERE digest_type = ?
           ORDER BY generated_at DESC LIMIT 1""",
        (digest_type,),
    ).fetchone()

    if not row:
        return None

    d = dict(row)
    if d.get("topics_covered"):
        d["topics_covered"] = json.loads(d["topics_covered"])
    if d.get("gaps_identified"):
        d["gaps_identified"] = json.loads(d["gaps_identified"])
    return d
