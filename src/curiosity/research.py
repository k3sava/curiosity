"""Research agent — web search and discovery.

NO direct Anthropic API calls. Search query generation is done by Claude Code
(it calls web_search with queries it generates itself). Zero extra API cost.

Flow:
  Claude Code decides what to search for → calls web_search tool
  Claude Code reviews results → calls ingest_url for the good ones
"""

import time
from typing import Optional
from urllib.parse import urlparse, quote_plus

import httpx

from .models import Bookmark, Discovery, now_iso, new_id
from .db import CuriosityDB
from .config import CuriosityConfig
from .ingestion import extract_domain


def web_search_brave(query: str, api_key: str, count: int = 5) -> list[dict]:
    """Search the web using Brave Search API.

    Returns list of {url, title, description}.
    """
    try:
        resp = httpx.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": count},
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": api_key,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get("web", {}).get("results", []):
            results.append({
                "url": item.get("url", ""),
                "title": item.get("title", ""),
                "description": item.get("description", ""),
            })
        return results
    except Exception:
        return []


def web_search_fallback(query: str, count: int = 5) -> list[dict]:
    """Fallback web search using DuckDuckGo HTML (no API key needed)."""
    try:
        resp = httpx.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": "Mozilla/5.0 Curiosity/0.1"},
            timeout=10,
        )
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for link in soup.select(".result__a")[:count]:
            href = link.get("href", "")
            title = link.get_text(strip=True)
            if href and title:
                if "uddg=" in href:
                    from urllib.parse import parse_qs, urlparse as up
                    parsed = up(href)
                    qs = parse_qs(parsed.query)
                    href = qs.get("uddg", [href])[0]
                results.append({
                    "url": href,
                    "title": title,
                    "description": "",
                })
        return results
    except Exception:
        return []


def web_search(
    query: str,
    db: CuriosityDB,
    count: int = 5,
    brave_api_key: Optional[str] = None,
) -> list[dict]:
    """Search the web, dedup against existing bookmarks, return candidates.

    Called by Claude Code with queries it generates itself.
    Returns results NOT already in the knowledge base.
    """
    if brave_api_key:
        results = web_search_brave(query, brave_api_key, count=count)
    else:
        results = web_search_fallback(query, count=count)

    # Dedup against existing URLs
    existing_urls = set()
    for row in db.conn.execute("SELECT url FROM bookmarks").fetchall():
        existing_urls.add(_normalize_url(row["url"]))

    filtered = []
    for r in results:
        if _normalize_url(r["url"]) not in existing_urls:
            r["search_query"] = query
            filtered.append(r)

    return filtered


def record_discovery(
    db: CuriosityDB,
    bookmark_id: str,
    triggered_by: str,
    search_query: str = "",
    relevance_score: float = 0.5,
):
    """Record a discovery link (which bookmark triggered the find)."""
    try:
        db.conn.execute(
            """INSERT OR IGNORE INTO discoveries
               (bookmark_id, triggered_by, search_query, relevance_score, discovered_at)
               VALUES (?, ?, ?, ?, ?)""",
            (bookmark_id, triggered_by, search_query, relevance_score, now_iso()),
        )
        db.conn.commit()
    except Exception:
        pass


def get_pending_enrichment(db: CuriosityDB, limit: int = 10) -> list[dict]:
    """Get bookmarks that have been fetched but not yet enriched.

    Returns raw content for Claude Code to analyze in batch.
    """
    rows = db.conn.execute(
        """SELECT b.id, b.url, b.title, b.domain,
                  c.raw_text, c.meta_description, c.word_count
           FROM bookmarks b
           JOIN content c ON b.id = c.bookmark_id
           WHERE b.status = 'fetched' AND c.raw_text IS NOT NULL
           ORDER BY b.added_at DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()

    results = []
    for r in rows:
        d = dict(r)
        # Truncate raw_text for Claude Code's context
        if d.get("raw_text"):
            d["raw_text"] = d["raw_text"][:8000]
        results.append(d)

    return results


def daily_sweep(
    db: CuriosityDB,
    brave_api_key: Optional[str] = None,
    max_total: int = 50,
) -> dict:
    """Daily research sweep — searches for followed experts and knowledge gaps.

    Returns candidates for Claude Code to review and ingest.
    Does NOT auto-ingest (Claude Code decides what's worth keeping).
    """
    total_found = 0
    all_candidates = []

    # 1. Check followed experts
    followed = db.conn.execute(
        "SELECT * FROM experts WHERE followed = 1"
    ).fetchall()

    for expert_row in followed:
        if total_found >= max_total:
            break

        expert = dict(expert_row)
        query = f"{expert['name']} latest articles {_current_year()}"

        results = web_search(query, db, count=3, brave_api_key=brave_api_key)

        for r in results:
            r["source"] = "followed_expert"
            r["triggered_by"] = f"expert:{expert['id']}"
            all_candidates.append(r)
            total_found += 1

        time.sleep(1)

    # 2. Fill knowledge gaps (top 3 most urgent)
    from .gaps import get_knowledge_gaps

    gaps = get_knowledge_gaps(db, limit=3)
    for gap in gaps:
        if total_found >= max_total:
            break

        queries = gap.get("search_queries", [])
        for query in queries[:1]:
            results = web_search(query, db, count=3, brave_api_key=brave_api_key)

            for r in results:
                r["source"] = "knowledge_gap"
                r["triggered_by"] = f"gap:{gap['domain']}"
                all_candidates.append(r)
                total_found += 1

            time.sleep(1)

    return {
        "candidates": all_candidates,
        "expert_checks": len(followed),
        "gaps_targeted": len(gaps),
        "total_found": total_found,
    }


def _normalize_url(url: str) -> str:
    """Normalize URL for deduplication."""
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = parsed.path.rstrip("/")
    return f"{host}{path}"


def _current_year() -> int:
    from datetime import datetime
    return datetime.now().year
