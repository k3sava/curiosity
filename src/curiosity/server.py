"""Curiosity MCP Server — zero extra API cost.

All AI analysis happens in Claude Code's context (already paid for).
The MCP server handles mechanical work: fetch pages, store data, search, export.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    Resource,
)

from .config import CuriosityConfig
from .db import CuriosityDB
from .ingestion import ingest_single, extract_domain, enrich_bookmark
from .models import now_iso
from .orchestrator import CuriosityOrchestrator

# ── Server Setup ──────────────────────────────────────────────

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)

app = Server("curiosity")
config: CuriosityConfig = None  # type: ignore
db: CuriosityDB = None  # type: ignore
orchestrator: CuriosityOrchestrator = None  # type: ignore


def _ensure_initialized():
    """Lazy initialization — only creates DB when first tool/resource is called."""
    global config, db, orchestrator
    if db is not None:
        return
    config = CuriosityConfig.from_env()
    config.ensure_data_dir()
    db = CuriosityDB(config.db_path)
    orchestrator = CuriosityOrchestrator(db, config)


# ── Tools ─────────────────────────────────────────────────────

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        # ── Core ──────────────────────────────────────────
        Tool(
            name="ingest_url",
            description=(
                "Fetch a URL and store its content. Returns the raw page text "
                "for you to analyze. After analyzing, call enrich_bookmark to "
                "save your summary, topics, and insights."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to fetch and store"},
                    "source": {
                        "type": "string",
                        "description": "Where this came from: manual, chrome, research_agent",
                        "default": "manual",
                    },
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="enrich_bookmark",
            description=(
                "Store your analysis of a bookmark. Call this after reading the "
                "raw content returned by ingest_url. Saves summary, topics, "
                "insights, content type, learning value, and author info."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "bookmark_id": {"type": "string"},
                    "summary": {"type": "string", "description": "2-3 sentence summary of what the page teaches"},
                    "topics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "3-7 lowercase topic tags",
                    },
                    "content_type": {
                        "type": "string",
                        "enum": ["article", "tutorial", "documentation", "tool", "video",
                                 "reference", "news", "opinion", "research", "product",
                                 "community", "course", "book", "podcast", "other"],
                        "default": "other",
                    },
                    "learning_value": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                        "default": "medium",
                    },
                    "key_insights": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "1-3 key takeaways (each under 100 chars)",
                    },
                    "author_name": {"type": "string", "description": "Author full name if identifiable"},
                    "author_slug": {"type": "string", "description": "kebab-case author slug"},
                },
                "required": ["bookmark_id", "summary", "topics"],
            },
        ),
        Tool(
            name="search",
            description=(
                "Search the knowledge base. Searches across titles, summaries, "
                "insights, and full page content. Returns matching bookmarks."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_detail",
            description="Get full details for a specific bookmark by ID or URL.",
            inputSchema={
                "type": "object",
                "properties": {
                    "bookmark_id": {"type": "string"},
                    "url": {"type": "string"},
                },
            },
        ),
        Tool(
            name="import_chrome_bookmarks",
            description=(
                "Bulk import bookmarks from a Chrome HTML export file. "
                "Stores URLs with titles and folders. Does NOT fetch content — "
                "use get_pending to process them afterward."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to Chrome bookmarks HTML file"},
                    "limit": {"type": "integer", "default": 0, "description": "Max to import (0 = all)"},
                },
                "required": ["file_path"],
            },
        ),

        # ── Intelligence ──────────────────────────────────
        Tool(
            name="web_search",
            description=(
                "Search the web and return results NOT already in the knowledge base. "
                "Uses Brave Search (if BRAVE_SEARCH_API_KEY set) or DuckDuckGo fallback. "
                "You generate the search queries, this tool executes them."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "count": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_pending",
            description=(
                "Get bookmarks that have been fetched but not yet enriched. "
                "Returns raw content for you to analyze in batch. After analyzing, "
                "call enrich_bookmark for each one."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 10},
                },
            },
        ),
        Tool(
            name="get_knowledge_gaps",
            description=(
                "Analyze knowledge gaps across domains. Returns domains sorted by "
                "urgency (lowest coverage × highest priority). Use this to decide "
                "what to search for next."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain_id": {"type": "string"},
                    "limit": {"type": "integer", "default": 15},
                },
            },
        ),
        Tool(
            name="get_digest",
            description=(
                "Generate or retrieve a learning digest. Summarizes what was added, "
                "clusters by topic, lists key insights, flags knowledge gaps."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "enum": ["daily", "weekly"],
                        "default": "daily",
                    },
                    "regenerate": {"type": "boolean", "default": False},
                },
            },
        ),

        # ── Analysis ──────────────────────────────────────
        Tool(
            name="analyze_topics",
            description="Show topic coverage with counts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "min_count": {"type": "integer", "default": 2},
                    "limit": {"type": "integer", "default": 30},
                },
            },
        ),
        Tool(
            name="find_connections",
            description="Find relationships between bookmarks — shared topics, same author, same domain.",
            inputSchema={
                "type": "object",
                "properties": {
                    "bookmark_id": {"type": "string"},
                    "connection_type": {
                        "type": "string",
                        "enum": ["topic", "author", "domain", "all"],
                        "default": "all",
                    },
                    "min_overlap": {"type": "integer", "default": 2},
                },
            },
        ),

        # ── Export ────────────────────────────────────────
        Tool(
            name="export_markdown",
            description="Export bookmarks as markdown (artemis, obsidian, or plain format).",
            inputSchema={
                "type": "object",
                "properties": {
                    "output_dir": {"type": "string"},
                    "format": {"type": "string", "enum": ["artemis", "obsidian", "plain"], "default": "plain"},
                    "bookmark_id": {"type": "string"},
                    "status": {"type": "string"},
                    "limit": {"type": "integer", "default": 0},
                },
                "required": ["output_dir"],
            },
        ),

        # ── Configuration ─────────────────────────────────
        Tool(
            name="configure_domains",
            description="View or update knowledge domains for gap analysis.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["list", "add", "update", "remove"], "default": "list"},
                    "domain_id": {"type": "string"},
                    "name": {"type": "string"},
                    "keywords": {"type": "array", "items": {"type": "string"}},
                    "target_sources": {"type": "integer"},
                    "priority": {"type": "number"},
                    "search_queries": {"type": "array", "items": {"type": "string"}},
                },
            },
        ),
        Tool(
            name="follow_expert",
            description="Follow or unfollow an expert for daily sweep monitoring.",
            inputSchema={
                "type": "object",
                "properties": {
                    "expert_id": {"type": "string"},
                    "follow": {"type": "boolean", "default": True},
                },
                "required": ["expert_id"],
            },
        ),

        # ── Orchestrator ──────────────────────────────────
        Tool(
            name="orchestrator_status",
            description="Show orchestrator status: watcher, webhook, queue, sweep schedule, stats.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="trigger_sweep",
            description="Manually trigger a daily research sweep now.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_sweep_results",
            description="Get results from the last daily sweep — candidates for you to review and ingest.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    _ensure_initialized()
    handlers = {
        "ingest_url": _tool_ingest_url,
        "enrich_bookmark": _tool_enrich_bookmark,
        "search": _tool_search,
        "get_detail": _tool_get_detail,
        "import_chrome_bookmarks": _tool_import_chrome,
        "web_search": _tool_web_search,
        "get_pending": _tool_get_pending,
        "get_knowledge_gaps": _tool_get_knowledge_gaps,
        "get_digest": _tool_get_digest,
        "analyze_topics": _tool_analyze_topics,
        "find_connections": _tool_find_connections,
        "export_markdown": _tool_export_markdown,
        "configure_domains": _tool_configure_domains,
        "follow_expert": _tool_follow_expert,
        "orchestrator_status": _tool_orchestrator_status,
        "trigger_sweep": _tool_trigger_sweep,
        "get_sweep_results": _tool_get_sweep_results,
    }
    handler = handlers.get(name)
    if handler:
        return await handler(arguments)
    return [TextContent(type="text", text=f"Unknown tool: {name}")]


# ── Tool Implementations ─────────────────────────────────────

async def _tool_ingest_url(args: dict) -> list[TextContent]:
    url = args["url"]
    source = args.get("source", "manual")

    existing = db.get_bookmark_by_url(url)
    if existing and existing.status == "enriched":
        content = db.get_content(existing.id)
        topics = db.get_bookmark_topics(existing.id)
        return [TextContent(type="text", text=json.dumps({
            "status": "already_exists",
            "bookmark_id": existing.id,
            "title": existing.title,
            "summary": content.summary if content else None,
            "topics": [t["name"] for t in topics],
        }, indent=2))]

    loop = asyncio.get_event_loop()
    bookmark = await loop.run_in_executor(
        None, lambda: ingest_single(url, db, config, source=source),
    )

    content = db.get_content(bookmark.id)

    result = {
        "status": bookmark.status,
        "bookmark_id": bookmark.id,
        "title": bookmark.title,
        "domain": bookmark.domain,
        "word_count": content.word_count if content else None,
        "meta_description": content.meta_description if content else None,
    }

    # Include truncated raw text so Claude Code can analyze it
    if content and content.raw_text:
        result["raw_text"] = content.raw_text[:8000]
        result["needs_enrichment"] = True
        result["enrich_instructions"] = (
            "Analyze the raw_text above and call enrich_bookmark with: "
            "summary, topics (3-7 lowercase tags), content_type, learning_value, "
            "key_insights (1-3 takeaways), author_name, author_slug"
        )

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def _tool_enrich_bookmark(args: dict) -> list[TextContent]:
    success = enrich_bookmark(
        bookmark_id=args["bookmark_id"],
        db=db,
        summary=args["summary"],
        topics=args["topics"],
        content_type=args.get("content_type", "other"),
        learning_value=args.get("learning_value", "medium"),
        key_insights=args.get("key_insights"),
        author_name=args.get("author_name"),
        author_slug=args.get("author_slug"),
    )

    if success:
        bookmark = db.get_bookmark(args["bookmark_id"])
        return [TextContent(type="text", text=json.dumps({
            "status": "enriched",
            "bookmark_id": args["bookmark_id"],
            "title": bookmark.title if bookmark else "",
            "topics": args["topics"],
        }, indent=2))]

    return [TextContent(type="text", text=json.dumps({
        "status": "error",
        "message": "Bookmark not found or no content to enrich",
    }))]


async def _tool_search(args: dict) -> list[TextContent]:
    query = args["query"]
    limit = args.get("limit", 10)

    results = db.search(query, limit=limit)
    if not results:
        rows = db.conn.execute(
            """SELECT b.*, c.summary, c.content_type, c.learning_value
               FROM bookmarks b LEFT JOIN content c ON b.id = c.bookmark_id
               WHERE b.title LIKE ? OR b.domain LIKE ?
               ORDER BY b.added_at DESC LIMIT ?""",
            (f"%{query}%", f"%{query}%", limit),
        ).fetchall()
        results = [dict(r) for r in rows]

    formatted = [{
        "id": r.get("id"), "title": r.get("title"), "url": r.get("url"),
        "domain": r.get("domain"), "summary": r.get("summary"),
        "content_type": r.get("content_type"), "learning_value": r.get("learning_value"),
    } for r in results]

    return [TextContent(type="text", text=json.dumps({
        "query": query, "count": len(formatted), "results": formatted,
    }, indent=2))]


async def _tool_get_detail(args: dict) -> list[TextContent]:
    bookmark = None
    if args.get("bookmark_id"):
        bookmark = db.get_bookmark(args["bookmark_id"])
    elif args.get("url"):
        bookmark = db.get_bookmark_by_url(args["url"])

    if not bookmark:
        return [TextContent(type="text", text="Bookmark not found.")]

    content = db.get_content(bookmark.id)
    topics = db.get_bookmark_topics(bookmark.id)

    from .connections import get_connections
    connections = get_connections(db, bookmark.id)

    return [TextContent(type="text", text=json.dumps({
        "bookmark": bookmark.model_dump(),
        "content": content.model_dump() if content else None,
        "topics": [t["name"] for t in topics],
        "connections": connections[:10],
    }, indent=2, default=str))]


async def _tool_import_chrome(args: dict) -> list[TextContent]:
    from .import_chrome import parse_chrome_bookmarks
    from .models import Bookmark

    file_path = args["file_path"]
    limit = args.get("limit", 0)

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            html_content = f.read()
    except FileNotFoundError:
        return [TextContent(type="text", text=f"File not found: {file_path}")]

    chrome_bookmarks = parse_chrome_bookmarks(html_content)
    if limit > 0:
        chrome_bookmarks = chrome_bookmarks[:limit]
    chrome_bookmarks = [b for b in chrome_bookmarks if b.url.startswith(("http://", "https://"))]

    imported, skipped = 0, 0
    for cb in chrome_bookmarks:
        existing = db.get_bookmark_by_url(cb.url)
        if existing:
            skipped += 1
            continue
        bookmark = Bookmark(
            url=cb.url, title=cb.title, domain=extract_domain(cb.url),
            source="chrome", chrome_folder=cb.folder_path,
            chrome_added_at=cb.add_date, status="pending",
        )
        db.insert_bookmark(bookmark)
        imported += 1

    return [TextContent(type="text", text=json.dumps({
        "imported": imported, "skipped_duplicates": skipped,
        "total_in_db": db.count_bookmarks(),
        "message": f"Imported {imported}. Use get_pending to start enriching them.",
    }, indent=2))]


async def _tool_web_search(args: dict) -> list[TextContent]:
    from .research import web_search
    query = args["query"]
    count = args.get("count", 5)
    brave_key = os.environ.get("BRAVE_SEARCH_API_KEY")

    results = web_search(query, db, count=count, brave_api_key=brave_key)

    return [TextContent(type="text", text=json.dumps({
        "query": query,
        "results": results,
        "count": len(results),
        "message": f"{len(results)} results not already in your knowledge base. "
                   "Call ingest_url on any you want to keep.",
    }, indent=2))]


async def _tool_get_pending(args: dict) -> list[TextContent]:
    from .research import get_pending_enrichment
    limit = args.get("limit", 10)
    pending = get_pending_enrichment(db, limit=limit)

    total_pending = db.conn.execute(
        "SELECT COUNT(*) FROM bookmarks WHERE status = 'fetched'"
    ).fetchone()[0]

    return [TextContent(type="text", text=json.dumps({
        "pending_total": total_pending,
        "returned": len(pending),
        "bookmarks": pending,
        "instructions": (
            "For each bookmark, analyze the raw_text and call enrich_bookmark with: "
            "bookmark_id, summary, topics, content_type, learning_value, key_insights, "
            "author_name, author_slug"
        ),
    }, indent=2))]


async def _tool_get_knowledge_gaps(args: dict) -> list[TextContent]:
    from .gaps import get_knowledge_gaps, format_gaps_report
    domain_id = args.get("domain_id")
    limit = args.get("limit", 15)
    gaps = get_knowledge_gaps(db, domain_id=domain_id, limit=limit)
    report = format_gaps_report(gaps)

    return [TextContent(type="text", text=json.dumps({
        "gaps": gaps, "markdown_report": report,
    }, indent=2))]


async def _tool_get_digest(args: dict) -> list[TextContent]:
    from .digest import generate_digest, get_latest_digest
    period = args.get("period", "daily")
    regenerate = args.get("regenerate", False)

    if not regenerate:
        existing = get_latest_digest(db, period)
        if existing:
            return [TextContent(type="text", text=json.dumps({
                "source": "cached", "digest": existing,
            }, indent=2, default=str))]

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None, lambda: generate_digest(db, period=period),
    )
    return [TextContent(type="text", text=json.dumps({
        "source": "generated", "digest": result,
    }, indent=2, default=str))]


async def _tool_analyze_topics(args: dict) -> list[TextContent]:
    topics = db.get_topics(
        min_count=args.get("min_count", 2),
        limit=args.get("limit", 30),
    )
    return [TextContent(type="text", text=json.dumps({
        "total_topics": len(topics), "topics": topics,
    }, indent=2))]


async def _tool_find_connections(args: dict) -> list[TextContent]:
    from .connections import (
        find_topic_connections, find_author_connections,
        find_domain_clusters, get_connections,
    )
    bookmark_id = args.get("bookmark_id")
    conn_type = args.get("connection_type", "all")
    min_overlap = args.get("min_overlap", 2)

    result = {}
    if conn_type in ("topic", "all"):
        result["topic_connections"] = find_topic_connections(db, bookmark_id=bookmark_id, min_overlap=min_overlap)
    if conn_type in ("author", "all"):
        result["author_connections"] = find_author_connections(db, bookmark_id=bookmark_id)
    if conn_type in ("domain", "all") and not bookmark_id:
        result["domain_clusters"] = find_domain_clusters(db)
    if bookmark_id:
        result["stored_connections"] = get_connections(db, bookmark_id)

    return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]


async def _tool_export_markdown(args: dict) -> list[TextContent]:
    from .export import export_bookmark, export_all
    output_dir = Path(args["output_dir"])
    fmt = args.get("format", "plain")
    bookmark_id = args.get("bookmark_id")

    if bookmark_id:
        path = export_bookmark(bookmark_id, db, output_dir, format=fmt)
        if path:
            return [TextContent(type="text", text=json.dumps({"exported": 1, "files": [str(path)]}))]
        return [TextContent(type="text", text="Bookmark not found.")]

    paths = export_all(db, output_dir, format=fmt,
                       status=args.get("status"), limit=args.get("limit", 0))
    return [TextContent(type="text", text=json.dumps({
        "exported": len(paths), "output_dir": str(output_dir), "format": fmt,
    }, indent=2))]


async def _tool_configure_domains(args: dict) -> list[TextContent]:
    from .gaps import seed_default_domains, get_knowledge_gaps
    action = args.get("action", "list")
    seed_default_domains(db)

    if action == "list":
        return [TextContent(type="text", text=json.dumps({"domains": get_knowledge_gaps(db)}, indent=2))]

    domain_id = args.get("domain_id")
    if not domain_id:
        return [TextContent(type="text", text="domain_id required")]

    if action == "add":
        db.conn.execute(
            "INSERT OR IGNORE INTO domains (id, name, keywords, target_sources, priority, search_queries, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (domain_id, args.get("name", domain_id.replace("_", " ").title()),
             json.dumps(args.get("keywords", [])), args.get("target_sources", 20),
             args.get("priority", 1.0), json.dumps(args.get("search_queries", [])), now_iso()),
        )
        db.conn.commit()
    elif action == "update":
        updates, params = [], []
        for field, col in [("name", "name"), ("keywords", "keywords"), ("target_sources", "target_sources"),
                           ("priority", "priority"), ("search_queries", "search_queries")]:
            if field in args:
                updates.append(f"{col} = ?")
                params.append(json.dumps(args[field]) if field in ("keywords", "search_queries") else args[field])
        if updates:
            updates.append("updated_at = ?")
            params.extend([now_iso(), domain_id])
            db.conn.execute(f"UPDATE domains SET {', '.join(updates)} WHERE id = ?", params)
            db.conn.commit()
    elif action == "remove":
        db.conn.execute("DELETE FROM domains WHERE id = ?", (domain_id,))
        db.conn.commit()

    return [TextContent(type="text", text=json.dumps({"status": action, "domain_id": domain_id}))]


async def _tool_follow_expert(args: dict) -> list[TextContent]:
    expert_id = args["expert_id"]
    follow = args.get("follow", True)
    expert = db.get_expert(expert_id)
    if not expert:
        return [TextContent(type="text", text=json.dumps({
            "error": f"Expert not found: {expert_id}",
        }))]

    db.conn.execute("UPDATE experts SET followed = ?, updated_at = ? WHERE id = ?",
                    (int(follow), now_iso(), expert_id))
    db.conn.commit()

    return [TextContent(type="text", text=json.dumps({
        "expert_id": expert_id, "name": expert.name, "followed": follow,
    }))]


async def _tool_orchestrator_status(args: dict) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(orchestrator.get_status(), indent=2, default=str))]


async def _tool_trigger_sweep(args: dict) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(orchestrator.trigger_sweep(), indent=2))]


async def _tool_get_sweep_results(args: dict) -> list[TextContent]:
    results = orchestrator.get_sweep_results()
    if not results:
        return [TextContent(type="text", text=json.dumps({
            "message": "No sweep results yet. Call trigger_sweep first.",
        }))]
    return [TextContent(type="text", text=json.dumps(results, indent=2))]


# ── Resources ─────────────────────────────────────────────────

@app.list_resources()
async def list_resources() -> list[Resource]:
    return [
        Resource(uri="curiosity://stats", name="Knowledge Base Stats",
                 description="Overview: total bookmarks, domains, topics, status breakdown",
                 mimeType="application/json"),
        Resource(uri="curiosity://recent", name="Recent Bookmarks",
                 description="Last 20 bookmarks with summaries", mimeType="application/json"),
        Resource(uri="curiosity://topics", name="Topic Map",
                 description="All topics with counts", mimeType="application/json"),
        Resource(uri="curiosity://gaps", name="Knowledge Gaps",
                 description="Domain coverage and gaps sorted by urgency", mimeType="application/json"),
        Resource(uri="curiosity://digest", name="Latest Digest",
                 description="Most recent learning digest", mimeType="application/json"),
        Resource(uri="curiosity://experts", name="Followed Experts",
                 description="Experts being tracked", mimeType="application/json"),
        Resource(uri="curiosity://pending", name="Pending Enrichment",
                 description="Bookmarks fetched but not yet analyzed — ready for Claude to enrich",
                 mimeType="application/json"),
        Resource(uri="curiosity://orchestrator", name="Orchestrator Status",
                 description="Autonomous engine status", mimeType="application/json"),
    ]


@app.read_resource()
async def read_resource(uri: str) -> str:
    _ensure_initialized()
    if uri == "curiosity://stats":
        return json.dumps(db.get_stats(), indent=2)

    elif uri == "curiosity://recent":
        return json.dumps(db.get_recent_bookmarks(limit=20), indent=2, default=str)

    elif uri == "curiosity://topics":
        return json.dumps(db.get_topics(min_count=1, limit=200), indent=2)

    elif uri == "curiosity://gaps":
        from .gaps import get_knowledge_gaps
        return json.dumps(get_knowledge_gaps(db), indent=2)

    elif uri == "curiosity://digest":
        from .digest import get_latest_digest
        digest = get_latest_digest(db, "daily")
        return json.dumps(digest or {"message": "No digest yet. Call get_digest."}, indent=2, default=str)

    elif uri == "curiosity://experts":
        rows = db.conn.execute(
            """SELECT e.*, COUNT(be.bookmark_id) as article_count
               FROM experts e LEFT JOIN bookmark_experts be ON e.id = be.expert_id
               WHERE e.followed = 1 GROUP BY e.id ORDER BY article_count DESC"""
        ).fetchall()
        experts = []
        for r in rows:
            d = dict(r)
            d["followed"] = bool(d.get("followed", 0))
            if d.get("expertise"):
                try:
                    d["expertise"] = json.loads(d["expertise"])
                except Exception:
                    pass
            experts.append(d)
        return json.dumps(experts, indent=2)

    elif uri == "curiosity://pending":
        from .research import get_pending_enrichment
        pending = get_pending_enrichment(db, limit=20)
        total = db.conn.execute("SELECT COUNT(*) FROM bookmarks WHERE status = 'fetched'").fetchone()[0]
        return json.dumps({"total_pending": total, "bookmarks": pending}, indent=2)

    elif uri == "curiosity://orchestrator":
        return json.dumps(orchestrator.get_status(), indent=2, default=str)

    return json.dumps({"error": f"Unknown resource: {uri}"})


# ── Main ──────────────────────────────────────────────────────

def main():
    import asyncio

    async def run():
        _ensure_initialized()
        orchestrator.start()
        try:
            async with stdio_server() as (read_stream, write_stream):
                await app.run(read_stream, write_stream, app.create_initialization_options())
        finally:
            orchestrator.stop()

    asyncio.run(run())


if __name__ == "__main__":
    main()
