"""Knowledge gap analysis — track domains, coverage, and learning priorities.

Evolved from Artemis's knowledge_gaps.py: same weighted urgency formula,
but user-configurable domains stored in SQLite instead of hardcoded.
"""

import json
from typing import Optional

from .db import CuriosityDB
from .models import Domain, now_iso


# Default domains seeded on first run (from Artemis)
DEFAULT_DOMAINS = [
    Domain(id="positioning", name="Positioning", keywords=["positioning", "category design", "competitive alternative", "differentiation"], target_sources=30, priority=2.0, search_queries=["B2B SaaS positioning framework 2025 2026", "competitive positioning methodology product marketing"]),
    Domain(id="messaging", name="Messaging", keywords=["messaging", "value proposition", "messaging matrix", "copywriting framework"], target_sources=25, priority=2.0, search_queries=["B2B messaging framework", "value proposition messaging SaaS"]),
    Domain(id="customer_research", name="Customer Research", keywords=["customer research", "voice of customer", "customer interview", "win loss", "buyer persona"], target_sources=25, priority=2.0, search_queries=["voice of customer program design", "customer interview methodology B2B"]),
    Domain(id="competitive_intel", name="Competitive Intelligence", keywords=["competitive analysis", "competitive intelligence", "competitor", "battlecard"], target_sources=20, priority=2.0, search_queries=["competitive intelligence framework B2B SaaS", "battlecard creation methodology"]),
    Domain(id="content_seo", name="Content & SEO", keywords=["content strategy", "seo", "content marketing", "editorial", "blog strategy"], target_sources=20, priority=1.0, search_queries=["B2B content strategy framework", "SEO content strategy SaaS"]),
    Domain(id="sales_enablement", name="Sales Enablement", keywords=["sales enablement", "sales collateral", "pitch deck", "objection handling", "demo script"], target_sources=20, priority=1.5, search_queries=["sales enablement strategy B2B", "sales collateral framework"]),
    Domain(id="growth_demand", name="Growth & Demand Gen", keywords=["demand gen", "growth", "pipeline", "lead gen", "acquisition"], target_sources=20, priority=1.5, search_queries=["B2B demand generation strategy", "growth marketing framework SaaS"]),
    Domain(id="pricing", name="Pricing", keywords=["pricing", "monetization", "packaging", "pricing model"], target_sources=15, priority=1.5, search_queries=["SaaS pricing strategy", "value-based pricing B2B"]),
    Domain(id="product_marketing", name="Product Marketing", keywords=["product marketing", "go-to-market", "GTM", "launch", "PMM"], target_sources=25, priority=1.0, search_queries=["product marketing career", "PMM strategy framework"]),
    Domain(id="ai_agents", name="AI & Agents", keywords=["ai agent", "claude", "llm", "automation", "mcp", "ai tools"], target_sources=30, priority=1.5, search_queries=["AI agent workflow automation 2026", "MCP server development Claude"]),
    Domain(id="ai_business", name="AI Business Models", keywords=["ai agency", "ai consulting", "ai services", "ai pricing", "ai business"], target_sources=20, priority=1.0, search_queries=["AI agency business model 2026", "AI services pricing outcome-based"]),
    Domain(id="brand", name="Brand", keywords=["brand strategy", "brand identity", "brand positioning", "brand voice"], target_sources=15, priority=0.5, search_queries=["B2B brand strategy", "brand voice guidelines"]),
    Domain(id="consulting", name="Consulting & Practice", keywords=["consulting", "freelance", "agency", "practice building", "client management"], target_sources=15, priority=1.0, search_queries=["consulting practice building", "freelance GTM consultant"]),
    Domain(id="decision_making", name="Decision Making", keywords=["decision making", "strategy", "frameworks", "mental models"], target_sources=15, priority=0.5, search_queries=["strategic decision making frameworks", "mental models business"]),
    Domain(id="conversion", name="Conversion & CRO", keywords=["conversion", "CRO", "landing page", "optimization", "funnel"], target_sources=15, priority=1.0, search_queries=["B2B conversion rate optimization", "SaaS landing page optimization"]),
]


def seed_default_domains(db: CuriosityDB):
    """Seed default knowledge domains if none exist."""
    count = db.conn.execute("SELECT COUNT(*) FROM domains").fetchone()[0]
    if count > 0:
        return

    for domain in DEFAULT_DOMAINS:
        db.conn.execute(
            """INSERT OR IGNORE INTO domains
               (id, name, keywords, target_sources, priority, search_queries, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (domain.id, domain.name, json.dumps(domain.keywords),
             domain.target_sources, domain.priority,
             json.dumps(domain.search_queries), now_iso()),
        )
    db.conn.commit()


def count_domain_sources(db: CuriosityDB, domain_id: str) -> int:
    """Count bookmarks matching a knowledge domain's keywords."""
    row = db.conn.execute(
        "SELECT keywords FROM domains WHERE id = ?", (domain_id,)
    ).fetchone()
    if not row or not row["keywords"]:
        return 0

    keywords = json.loads(row["keywords"])
    if not keywords:
        return 0

    # Count bookmarks whose title or topics match domain keywords
    count = 0
    for kw in keywords:
        # Check titles
        title_count = db.conn.execute(
            "SELECT COUNT(*) FROM bookmarks WHERE LOWER(title) LIKE ?",
            (f"%{kw.lower()}%",),
        ).fetchone()[0]

        # Check topics
        topic_count = db.conn.execute(
            """SELECT COUNT(DISTINCT bt.bookmark_id)
               FROM bookmark_topics bt
               JOIN topics t ON bt.topic_id = t.id
               WHERE LOWER(t.name) LIKE ?""",
            (f"%{kw.lower()}%",),
        ).fetchone()[0]

        count += title_count + topic_count

    # Deduplicate (rough — may overcount, but good enough)
    # Cap at actual bookmark count
    total = db.count_bookmarks()
    return min(count, total)


def get_knowledge_gaps(
    db: CuriosityDB,
    domain_id: Optional[str] = None,
    limit: int = 15,
) -> list[dict]:
    """Analyze knowledge gaps across all domains.

    Returns domains sorted by urgency (lowest coverage × highest priority first).
    Formula: weighted_urgency = coverage_pct / priority (lower = more urgent)
    """
    seed_default_domains(db)

    if domain_id:
        rows = db.conn.execute(
            "SELECT * FROM domains WHERE id = ?", (domain_id,)
        ).fetchall()
    else:
        rows = db.conn.execute("SELECT * FROM domains").fetchall()

    gaps = []
    for row in rows:
        d = dict(row)
        current = count_domain_sources(db, d["id"])
        target = d["target_sources"]
        coverage_pct = (current / target * 100) if target > 0 else 0
        priority = d["priority"] or 1.0

        # Lower score = more urgent gap
        weighted_urgency = coverage_pct / priority if priority > 0 else coverage_pct

        search_queries = json.loads(d["search_queries"]) if d.get("search_queries") else []
        keywords = json.loads(d["keywords"]) if d.get("keywords") else []

        gaps.append({
            "domain": d["id"],
            "name": d["name"],
            "current_sources": current,
            "target_sources": target,
            "coverage_pct": round(coverage_pct, 1),
            "priority": priority,
            "weighted_urgency": round(weighted_urgency, 1),
            "gap_size": max(0, target - current),
            "search_queries": search_queries,
            "keywords": keywords,
            "status": "covered" if coverage_pct >= 100 else ("critical" if coverage_pct < 30 else "partial"),
        })

    gaps.sort(key=lambda x: x["weighted_urgency"])
    return gaps[:limit]


def format_gaps_report(gaps: list[dict]) -> str:
    """Format knowledge gaps as a readable markdown report."""
    lines = ["# Knowledge Gap Analysis\n"]

    critical = [g for g in gaps if g["status"] == "critical"]
    partial = [g for g in gaps if g["status"] == "partial"]
    covered = [g for g in gaps if g["status"] == "covered"]

    if critical:
        lines.append("## Critical Gaps (< 30% coverage)\n")
        for g in critical:
            lines.append(f"**{g['name']}** — {g['current_sources']}/{g['target_sources']} ({g['coverage_pct']}%)")
            lines.append(f"  Priority: {g['priority']} | Urgency score: {g['weighted_urgency']}")
            if g["search_queries"]:
                lines.append(f"  Try: `discover_related` with \"{g['search_queries'][0]}\"")
            lines.append("")

    if partial:
        lines.append("## Partial Coverage (30-99%)\n")
        for g in partial:
            lines.append(f"**{g['name']}** — {g['current_sources']}/{g['target_sources']} ({g['coverage_pct']}%)")
            lines.append("")

    if covered:
        lines.append("## Well Covered (100%+)\n")
        for g in covered:
            lines.append(f"**{g['name']}** — {g['current_sources']}/{g['target_sources']} ({g['coverage_pct']}%)")
            lines.append("")

    return "\n".join(lines)
