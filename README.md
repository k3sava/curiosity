# curiosity

I had 10+ years of Chrome bookmarks. Thousands of links saved across tabs, folders, Pocket, Slack messages, tweets — the usual graveyard. I tried Raindrop, Pocket, Hoarder. They're fine for saving links. But I didn't need another place to save links. I needed something that would actually *read* them for me and tell me what I was missing.

So I built curiosity.

## What it does

You save a link. curiosity reads the page, pulls out a summary, key insights, topic tags, and the author. It scores the learning value. It finds connections to things you saved weeks ago. It tracks what you know and what you don't. And every day, it resurfaces forgotten insights before they fade.

It's not a bookmark manager. It's a knowledge system.

## Quick start

```bash
pip install curiosity-kb
curiosity serve
```

Open [localhost:8080](http://localhost:8080). Paste a URL. That's it.

Or with Docker:

```bash
docker run -p 8080:8080 -v curiosity_data:/data ghcr.io/[you]/curiosity
```

## The 30-second version

1. **Save** — paste a URL, import your Chrome bookmarks, upload a PDF, subscribe to an RSS feed
2. **Enrich** — curiosity reads everything and extracts what matters (set `ANTHROPIC_API_KEY` for auto-enrichment, or use Claude Code for free)
3. **Discover** — see what you know, what you're missing, and what to read next
4. **Review** — old insights resurface daily so you remember what you read, not just that you read it

## Features

The stuff that makes it different from yet another bookmark app:

- **AI enrichment** — every bookmark gets a summary, key insights, topic tags, content type, learning value score, and author detection. Zero manual tagging.
- **Knowledge discovery** — curiosity tracks what you've read across domains and tells you where you're thin. "You have 19 sources on AI but 2 on positioning."
- **Daily review** — spaced repetition for your bookmarks. One insight at a time. *"Take a minute. See what stuck."*
- **Connections** — "This article shares 3 topics with something you saved 2 months ago." Ideas link across time.
- **Expert tracking** — follow authors. curiosity watches for their new work.
- **RSS feeds** — subscribe to sources. New articles flow in automatically.
- **Full-text search** — search everything you've ever saved. Summaries, insights, raw content.
- **Cmd+K** — command palette for search, URL capture, and power features
- **Collections** — organize however you want. One bookmark can live in multiple collections.
- **Highlights** — select text, save it. All your highlights in one place.
- **Read status** — track what's unread, in progress, or done
- **Bulk actions** — select, tag, delete, re-enrich in batch
- **Page archival** — full HTML cache + Wayback Machine submission. Your knowledge survives link rot.
- **PDF + image upload** — not just URLs. Upload documents and images. OCR included.
- **Video archiving** — yt-dlp integration saves audio from YouTube talks
- **Import** — bring your bookmarks from Chrome, Pocket, or Omnivore
- **Automation rules** — "if domain is github.com, tag it 'code' and add to Dev Tools"
- **Dark mode** — because of course
- **Local-first** — SQLite on your machine. No cloud, no account, no subscription. Your data stays yours.
- **MCP server** — 17 tools, 8 resources. Works with Claude Code, Claude Desktop, Cursor, or any MCP-compatible client.

## How enrichment works

Two ways to enrich your bookmarks:

**With Claude Code (free):**
curiosity runs as an MCP server. When you enrich a bookmark, Claude reads it in your existing session — no extra API calls, no cost.

```bash
claude mcp add curiosity -- curiosity-mcp
```

**Standalone (API key):**
Set `ANTHROPIC_API_KEY` and click "Enrich with AI" on any bookmark. Uses Claude Haiku — fast and cheap (~$0.001/bookmark).

```bash
export ANTHROPIC_API_KEY=sk-ant-...
curiosity serve
```

## Tech

- **Python + FastAPI** — server-rendered, fast, no JS framework
- **SQLite + FTS5** — full-text search, no external services
- **MCP server** — 17 tools for AI integration
- **Zero dependencies on external services** — runs entirely on your machine

## Why I built it

I'm a product marketer. I read a lot — positioning frameworks, competitive teardowns, AI research, design thinking, growth strategy. Over the years I saved thousands of links and barely revisited any of them.

I wanted something that would:
- Actually read the things I save (I won't, let's be honest)
- Tell me how ideas connect across different domains
- Show me what I'm missing, not just what I have
- Bring back insights before I forget them completely
- Not cost me a monthly subscription to store my own data

Nothing did all of that. So I built it.

## Contributing

This started as a personal tool. If you find it useful, I'd love to hear about it. If you want to contribute, open an issue first — I'm opinionated about the design.

## License

MIT
