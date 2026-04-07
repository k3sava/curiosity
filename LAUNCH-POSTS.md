# curiosity — launch posts

## 1. Hacker News — Show HN

**Title:** Show HN: curiosity – save one link, get the full picture

I wanted to learn about positioning. Found one good article. Wanted more — different angles, counterpoints, frameworks I hadn't seen. Ended up with 40 tabs open and no system for any of it.

That's the pattern. You find one thing. You want the full picture. You go down the rabbit hole. And nothing connects. Nothing sticks.

So I built curiosity.

Save a link. curiosity reads the page, pulls out the key ideas, and helps you go deeper — finding related pieces, different perspectives, deeper dives on the same topic. Then it quietly handles the rest. Summarizes. Tags. Organizes. Connects ideas across topics. Resurfaces old insights before you forget them.

One place for every rabbit hole.

It's free, open source, local-first. SQLite on your machine. AI enrichment is free via Claude Code, or ~$0.001/bookmark with the Anthropic API.

```
pip install curiosity-kb && curiosity serve
```

GitHub: https://github.com/k3sava/curiosity

Built this for myself because I kept falling into research rabbit holes with no system to catch what I found. Turns out that's a pretty common problem.

---

## 2. Product Hunt

**Tagline:** Save one link. Get the full picture. curiosity makes the cat.

**Description:**

You find one article about a topic. You want more — different angles, deeper dives, counterpoints. You open 40 tabs. You bookmark some. You close the browser. You never go back.

curiosity fixes that.

Save a link. It reads the page, pulls out the key ideas, and helps you go deeper — finding related content you wouldn't have searched for. Then it organizes everything automatically. Connects ideas across topics. And resurfaces what matters before you forget it.

Not a bookmark manager. A rabbit hole companion.

**Maker's comment:**

I'm a product marketer. I read a lot — positioning frameworks, competitive analysis, AI research. Over the years I saved thousands of links and had no way to make sense of any of it. curiosity is the tool I wished existed. Now it does.

---

## 3. Twitter/X thread

**1:**
I wanted to learn about positioning. Found one article. Wanted more.

40 tabs later, none of it was saved anywhere useful.

So I built something. It's called curiosity. And it makes the cat. 🧵

**2:**
Here's how it works.

Save a link. curiosity reads the page. Pulls out the key ideas. Summarizes it. Tags it. You didn't do anything. It just reads.

**3:**
Then you hit "go deeper."

curiosity searches for more — different perspectives, alternatives, deeper dives on the same topic. Save the ones worth keeping. One click each.

Your library grows around the things you're actually curious about.

**4:**
Over time, it starts connecting things.

"This article shares three ideas with something you saved two months ago."

You didn't see that. curiosity did.

**5:**
Every morning, it pulls out something you saved weeks ago.

*remember this?*

Not flashcards. Ideas. The ones that actually mattered.

**6:**
It's free. Open source. Runs on your machine. Python, SQLite, no cloud.

pip install curiosity-kb && curiosity serve

GitHub: https://github.com/k3sava/curiosity

curiosity makes the cat. Meow. 🐱

---

## 4. Reddit — /r/selfhosted

**Title:** curiosity: self-hosted tool for research rabbit holes — save one link, go deeper

You find one article. You want the full picture. You want alternatives, counterpoints, deeper dives. You open 40 tabs, bookmark some, close the browser, never go back.

curiosity is one place for all of that. Save a link. It reads the page, extracts the key ideas, and helps you find more related content. Then it automatically organizes, connects ideas across topics, and resurfaces old insights daily.

**Stack:** Python, FastAPI, SQLite, FTS5. No external services. Runs on a Pi.

```
docker run -p 8080:8080 -v curiosity_data:/data ghcr.io/k3sava/curiosity
```

Features: AI enrichment, "go deeper" discovery, daily review, RSS feeds, collections, highlights, automation rules, page archival, ⌘K command palette, dark mode, MCP server for Claude Code.

GitHub: https://github.com/k3sava/curiosity

---

## 5. Claude Code community

**Title:** MCP server for research rabbit holes — save a URL, Claude finds the full picture

Built an MCP server that turns Claude into a research companion. Save a URL, Claude reads and enriches it, then helps you find related content — different perspectives, deeper dives, alternatives.

17 tools. Zero extra cost — enrichment happens in your session.

```
pip install curiosity-kb
claude mcp add curiosity -- curiosity-mcp
```

"Save this URL" → "Enrich it" → "Find me more on this topic" → "What connects to my recent saves?"

Also comes with a web UI at localhost:8080.

GitHub: https://github.com/k3sava/curiosity

curiosity makes the cat. Meow.
