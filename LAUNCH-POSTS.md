# curiosity — launch posts

## 1. Hacker News — Show HN

**Title:** Show HN: curiosity – one place for everything you find on the web

I browse a lot. I save a lot. I save things everywhere — Chrome bookmarks, Pocket, Slack, tabs I swear I'll get back to.

Over 10 years I accumulated thousands of saved links. A personal internet I'd never revisit.

I tried Raindrop. Pocket. Hoarder. They organize links. That was never my problem. My problem was I had no system. No way to connect ideas across topics. No way to remember the good stuff before it faded into the pile.

So I built curiosity.

Save a link. curiosity reads the page, pulls out the key ideas, connects it to things you've saved before, and makes sure you don't forget the important parts. Every morning it resurfaces something you saved weeks ago and goes: *remember this?*

It's free, open source, and local-first. SQLite on your machine. No cloud. No subscription. No tracking.

AI enrichment is free via Claude Code, or ~$0.001/bookmark with the Anthropic API.

The basics: save URLs, import Chrome bookmarks, upload PDFs, subscribe to RSS feeds, search everything.

The interesting stuff: daily review cards, connections between bookmarks, a quiet tracker that notices which topics you're ignoring.

The power tools: automation rules, bulk actions, highlights, collections, page archival, command palette.

```
pip install curiosity-kb && curiosity serve
```

GitHub: https://github.com/k3sava/curiosity

Built this for myself. Turns out organizing your curiosity is a universal problem. Happy to answer questions.

---

## 2. Product Hunt

**Tagline:** One place for everything you find on the web. curiosity makes the cat.

**Description:**

I browse a lot. Articles, repos, talks, threads. I save them everywhere. I never go back.

Sound familiar?

curiosity is one place for all of it. Save a link. It reads the page, pulls out what matters, connects it to things you've already saved, and makes sure you don't forget the important parts.

Not a bookmark manager. Not a read-it-later app. A system for actually learning from the things that catch your eye.

Free. Open source. Runs on your machine. Your data stays yours.

**Maker's comment:**

I built this because I had 10 years of Chrome bookmarks and nothing that helped me make sense of them. Raindrop organizes. Pocket saves. curiosity reads. That's the difference.

---

## 3. Twitter/X thread

**1:**
I had 10 years of Chrome bookmarks.

Thousands of links I'd never look at again. Sound familiar?

So I built something. It's called curiosity. And it makes the cat.

🧵

**2:**
Here's the thing about saving links.

You're great at it. You're saving plenty. The problem is you never go back. You never connect the positioning article from March with the design thinking piece from last week.

curiosity does.

**3:**
Save a link. Any link.

curiosity reads the page and gives you back what matters. Summary. Key insights. Topic tags. Who wrote it. Whether it's worth your time.

No tagging. No folders. No organizing. It just reads.

**4:**
Then it starts connecting things.

"This article shares three ideas with something you saved two months ago."

You didn't see that. curiosity did.

**5:**
Every morning, it pulls out something you saved weeks ago.

*remember this?*

Spaced repetition for your browsing. Not flashcards. Ideas.

**6:**
It's free. Open source. Runs on your machine.

Python. SQLite. No cloud. No subscription. No tracking.

pip install curiosity-kb && curiosity serve

**7:**
GitHub: https://github.com/k3sava/curiosity

I built this for myself because nothing else did what I wanted. If you're a fellow bookmark hoarder, give it a shot.

curiosity makes the cat. Meow. 🐱

---

## 4. Reddit — /r/selfhosted

**Title:** curiosity: self-hosted tool that reads your bookmarks so you don't have to

I browse a lot. Save a lot. Never go back. Over 10 years I accumulated thousands of links across Chrome, Pocket, Slack, random tabs.

I tried every bookmark manager. They're great at organizing. That was never my problem.

My problem was that I had all this saved knowledge and no way to actually learn from it. No connections. No review. No "hey, you saved something about this 3 months ago."

So I built curiosity.

**What it does:** Save a URL (or import your Chrome bookmarks, or upload a PDF). curiosity reads the page, extracts the key ideas, finds connections to your other saves, and resurfaces old insights daily so you actually remember them.

**Stack:** Python, FastAPI, SQLite, FTS5 full-text search. No external services. One Docker image.

```
docker run -p 8080:8080 -v curiosity_data:/data ghcr.io/k3sava/curiosity
```

Or pip:
```
pip install curiosity-kb && curiosity serve
```

**Features:** AI enrichment (summary, insights, topics, author detection), daily review, RSS feeds, collections, highlights, automation rules, page archival, Cmd+K command palette, dark mode, MCP server for Claude Code.

**Self-hosted friendly:** SQLite on disk. No Postgres. No Redis. No Meilisearch. No cloud. Runs on a Pi.

GitHub: https://github.com/k3sava/curiosity

---

## 5. Claude Code community

**Title:** MCP server that turns your bookmarks into a knowledge system

Built an MCP server that gives Claude a long-term memory for web content. Save URLs, and Claude reads and enriches them. Search across everything. Follow authors. Review old insights.

17 tools. 8 resources. Zero extra API cost — enrichment happens in your existing session.

```
pip install curiosity-kb
claude mcp add curiosity -- curiosity-mcp
```

Then: "Save this URL" → "What are my knowledge gaps?" → "Find me something to read about positioning" → "Show me connections between my recent saves"

Also comes with a web UI at localhost:8080 for browsing, reviewing, and discovering.

GitHub: https://github.com/k3sava/curiosity

curiosity makes the cat. Meow.
