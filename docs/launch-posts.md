# curiosity -- launch posts

## 1. Hacker News -- Show HN

**Title:** Show HN: Curiosity -- a personal knowledge base that reads your bookmarks for you

I'm a GTM strategist. I read constantly -- positioning theory, competitive intel, product marketing frameworks. Over 10 years I accumulated thousands of Chrome bookmarks. A personal internet I'd never revisit.

I tried Raindrop, Pocket, Hoarder. They organize links. That was never my problem. My problem was I had no system for actually learning from what I saved. No connections between ideas. No way to remember the good stuff before it faded into the pile.

So I built curiosity.

Save a URL. Curiosity fetches the page, reads it, and gives you back what matters: summary, key insights, topic tags, who wrote it. Then it starts connecting things. That positioning article from March shares three ideas with the design thinking piece from last week. You didn't see the connection. Curiosity did.

Every morning, it resurfaces something you saved weeks ago. Spaced repetition for ideas, not flashcards.

The technical angle, since this is HN: it's about 3,000 lines of Python. FastAPI, SQLite with FTS5 for search, Jinja2 templates. Server-rendered HTML. No React. No Electron. No build step. Runs on a Raspberry Pi if you want.

AI enrichment works three ways:
- Free via Ollama (local, no API key)
- Free via Gemini API (generous free tier)
- Anthropic API (~$0.001 per bookmark with Haiku)

Also runs as an MCP server for Claude Code, so Claude can search and enrich your library in-session at zero extra cost.

Screenshots: https://github.com/k3sava/curiosity/tree/main/docs/screenshots

```
pip install curiosity-kb && curiosity serve
```

GitHub: https://github.com/k3sava/curiosity

Built this for myself because I wanted to actually learn from the things I read. Happy to answer questions.

---

## 2. Reddit r/selfhosted

**Title:** curiosity: self-hosted knowledge base that reads your bookmarks so you don't have to

I had 10 years of Chrome bookmarks and nothing that helped me make sense of them. Every bookmark manager I tried was great at organizing. That was never my problem. My problem was I never went back.

So I built curiosity. Save a URL, it reads the page, extracts the key ideas, finds connections to your other saves, and resurfaces old insights daily.

**Self-hosting details:**

- SQLite on disk. No Postgres. No Redis. No Meilisearch. One file database.
- Docker image available, or pip install.
- AI enrichment is optional. Three free options: Ollama (fully local, no internet needed), Gemini free tier, or Claude Code MCP (zero extra API cost).
- No cloud. No account. No telemetry. Your data stays on your machine.
- Runs on a Pi.

```
docker run -p 8080:8080 -v curiosity_data:/data ghcr.io/k3sava/curiosity
```

Or:
```
pip install curiosity-kb && curiosity serve
```

**What you get:** Chrome bookmark import, RSS feeds, PDF upload, full-text search, daily review cards, topic connections, automation rules, collections, highlights, dark mode, Cmd+K command palette.

GitHub: https://github.com/k3sava/curiosity

---

## 3. Twitter/X thread

**Tweet 1:**
I built a personal knowledge system that actually works.

Not a bookmark manager. Not a read-it-later app. Something that reads what you save and helps you learn from it.

It's called curiosity. It's free and open source. Here's the story.

**Tweet 2:**
The problem: I had 10 years of Chrome bookmarks. Thousands of articles, repos, talks, threads I saved and never looked at again.

Every tool I tried organized my links better. That was never the issue. The issue was I never went back.

**Tweet 3:**
curiosity reads the page for you. Save a URL and get back: summary, key insights, topic tags, author, and whether it's worth your time.

Then it connects things. "This article shares ideas with something you saved two months ago."

[screenshot: home.png]

**Tweet 4:**
Every morning it resurfaces something you saved weeks ago. Spaced repetition for ideas, not flashcards.

[screenshot: review.png]

**Tweet 5:**
The stack: 3,000 lines of Python. FastAPI. SQLite. Server-rendered HTML. No React. No Electron. No build step.

AI enrichment is free: Ollama (local), Gemini free tier, or run it as an MCP server inside Claude Code.

[screenshot: library.png]

**Tweet 6:**
pip install curiosity-kb && curiosity serve

GitHub: https://github.com/k3sava/curiosity

Built this for myself because nothing else did what I wanted. If you're a fellow bookmark hoarder, give it a try.

---

## 4. LinkedIn

I built this because every read-it-later app treats bookmarks as a TODO list. Curiosity treats them as a knowledge base.

Over 10 years of working in GTM strategy, I accumulated thousands of saved links. Positioning frameworks, competitive analyses, product marketing deep dives. Chrome bookmarks, Pocket saves, Slack messages to myself. A personal library I never revisited.

The problem was never organization. It was learning. I needed something that would read what I saved, connect ideas across topics, and resurface the good stuff before it faded into the pile.

So I built it. It's called curiosity.

Save a link. Curiosity reads the page, extracts the insights worth keeping, finds connections to things you've already saved, and resurfaces old ideas daily. No tagging. No folders. It just reads.

It's 3,000 lines of Python. SQLite. No cloud dependency. Free AI enrichment via Ollama or Gemini. Open source under MIT.

I'm a GTM strategist, not a developer. I built this with Claude Code over a few months of evenings and weekends. It started as a personal tool and still feels like one. But a few people asked to try it, so here it is.

If you're someone who reads a lot and saves even more, give it a look: https://github.com/k3sava/curiosity
