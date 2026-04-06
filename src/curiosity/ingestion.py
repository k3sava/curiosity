"""Content ingestion pipeline — fetch, extract, store.

NO direct Anthropic API calls. Enrichment (summarize, tag, rate) is done by
Claude Code via the enrich_bookmark MCP tool. This means zero extra API cost
on top of the user's existing Claude plan.

Flow:
  ingest_single() → fetch page → store raw content → return to Claude Code
  Claude Code analyzes → calls enrich_bookmark() → stores summary/tags/insights
"""

import json
from urllib.parse import urlparse
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
from bs4 import BeautifulSoup

from .models import Bookmark, Content, EnrichmentResult, now_iso
from .db import CuriosityDB
from .config import CuriosityConfig

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Curiosity/0.1"


def extract_domain(url: str) -> str:
    """Extract clean domain from URL."""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def fetch_url(url: str, timeout: int = 15) -> dict:
    """Fetch a URL and extract readable text content."""
    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove noise elements
        for tag in soup(["script", "style", "nav", "footer", "header",
                         "aside", "form", "noscript", "iframe", "svg"]):
            tag.decompose()

        # Try article/main content first
        content = ""
        for selector in ["article", "main", '[role="main"]', ".post-content",
                         ".article-content", ".entry-content", "#content",
                         ".post-body", ".blog-post"]:
            el = soup.select_one(selector)
            if el:
                content = el.get_text(separator="\n", strip=True)
                break

        if not content or len(content) < 200:
            content = soup.get_text(separator="\n", strip=True)

        # Clean whitespace
        lines = [line.strip() for line in content.split("\n") if line.strip()]
        content = "\n".join(lines)

        # Get meta description
        meta_desc = ""
        meta = soup.find("meta", attrs={"name": "description"})
        if meta:
            meta_desc = meta.get("content", "")

        # Get page title (might be better than bookmark title)
        page_title = soup.title.string.strip() if soup.title and soup.title.string else None

        return {
            "success": True,
            "content": content,
            "meta_description": meta_desc[:500],
            "page_title": page_title,
            "final_url": str(resp.url),
            "word_count": len(content.split()),
        }

    except httpx.TimeoutException:
        return {"success": False, "error": "timeout"}
    except httpx.HTTPStatusError as e:
        return {"success": False, "error": f"http_{e.response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


def fetch_batch(urls: list[str], max_workers: int = 8, timeout: int = 15) -> dict[str, dict]:
    """Fetch multiple URLs in parallel. Returns {url: fetch_result}."""
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(fetch_url, url, timeout): url for url in urls
        }
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                results[url] = future.result()
            except Exception as e:
                results[url] = {"success": False, "error": str(e)[:200]}
    return results


def ingest_single(
    url: str,
    db: CuriosityDB,
    config: CuriosityConfig,
    source: str = "manual",
    title: Optional[str] = None,
    chrome_folder: Optional[str] = None,
    chrome_added_at: Optional[str] = None,
) -> Bookmark:
    """Fetch and store a URL. Does NOT call any AI — returns raw content
    for Claude Code to analyze via enrich_bookmark.

    1. Create bookmark record
    2. Fetch page content
    3. Store raw text
    4. Return bookmark (status=fetched) for Claude Code to enrich
    """
    domain = extract_domain(url)

    # 1. Create bookmark
    bookmark = Bookmark(
        url=url,
        title=title or url,
        domain=domain,
        source=source,
        chrome_folder=chrome_folder,
        chrome_added_at=chrome_added_at,
    )
    bookmark = db.insert_bookmark(bookmark)

    # If already exists and enriched, skip
    if bookmark.status == "enriched":
        return bookmark

    # 2. Fetch
    fetch_result = fetch_url(url, timeout=config.fetch_timeout)

    if fetch_result["success"]:
        # Update title if we got a better one
        if fetch_result.get("page_title") and (not title or title == url):
            bookmark.title = fetch_result["page_title"]
            db.conn.execute(
                "UPDATE bookmarks SET title = ? WHERE id = ?",
                (bookmark.title, bookmark.id),
            )

        bookmark.final_url = fetch_result.get("final_url")
        db.conn.execute(
            "UPDATE bookmarks SET final_url = ?, status = 'fetched', updated_at = ? WHERE id = ?",
            (bookmark.final_url, now_iso(), bookmark.id),
        )
        db.conn.commit()

        # 3. Store raw content
        content = Content(
            bookmark_id=bookmark.id,
            raw_text=fetch_result["content"],
            meta_description=fetch_result.get("meta_description"),
            word_count=fetch_result.get("word_count"),
            fetched_at=now_iso(),
        )
        db.upsert_content(content)

        bookmark.status = "fetched"
    else:
        db.update_bookmark_status(bookmark.id, "failed")
        bookmark.status = "failed"

    return bookmark


def enrich_bookmark(
    bookmark_id: str,
    db: CuriosityDB,
    summary: str,
    topics: list[str],
    content_type: str = "other",
    learning_value: str = "medium",
    key_insights: Optional[list[str]] = None,
    author_name: Optional[str] = None,
    author_slug: Optional[str] = None,
) -> bool:
    """Store enrichment data provided by Claude Code.

    Called after Claude Code analyzes the raw content returned by ingest_url.
    This is where the AI analysis gets persisted — but the AI call itself
    happened in Claude Code's context (no extra API cost).
    """
    from .models import Expert

    content = db.get_content(bookmark_id)
    if not content:
        return False

    content.summary = summary
    content.key_insights = key_insights or []
    content.content_type = content_type
    content.learning_value = learning_value
    content.enriched_at = now_iso()
    db.upsert_content(content)

    # Create topics
    for topic_name in topics:
        topic_id = db.get_or_create_topic(topic_name)
        db.link_bookmark_topic(bookmark_id, topic_id)

    # Create expert if identified
    if author_name and author_slug:
        expert = Expert(
            id=author_slug,
            name=author_name,
        )
        db.upsert_expert(expert)
        db.link_bookmark_expert(bookmark_id, author_slug)

    db.update_bookmark_status(bookmark_id, "enriched")
    return True
