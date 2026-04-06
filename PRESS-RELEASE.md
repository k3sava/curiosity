# curiosity — Future Press Release

*Internal working document. Amazon-style "working backwards" PR/FAQ.*

---

## Press Release

**FOR IMMEDIATE RELEASE**

### curiosity: The AI That Reads Everything You Save and Tells You What You're Missing

**Personal knowledge system turns 10 years of bookmarks into a living, searchable brain that gets smarter every day — at zero cost.**

Today, an independent developer released curiosity, a free, open-source personal knowledge system that transforms the way people learn from the web. Unlike bookmark managers that just store links, curiosity reads every page you save, extracts key insights, maps connections between ideas, tracks what you know and what you don't, and resurfaces forgotten insights exactly when they matter.

"Everyone has hundreds of saved bookmarks they'll never look at again," said the creator. "curiosity doesn't just save them. It reads them for you, tells you how they connect, shows you the gaps in your knowledge, and brings back the important stuff before you forget it. It's the difference between a filing cabinet and a research partner."

**The problem curiosity solves:** The average knowledge worker saves 50+ links per month across browser bookmarks, Pocket, Slack messages, and tweets. Within a week, 90% are never opened again. The knowledge decays. The connections between ideas are lost. Nobody knows what they don't know.

**How it works:** Install curiosity with one command. Import your Chrome bookmarks or paste a URL. Within seconds, curiosity reads the page and produces a summary, key insights, topic tags, and author identification. As your library grows, it automatically discovers connections between bookmarks, tracks your reading across 15 knowledge domains, identifies critical gaps, follows expert authors for new work, and generates weekly digests of what you've learned.

**Key capabilities:**

- **Instant enrichment.** Save a URL. Get a summary, 3 key insights, topic tags, content type, and learning value score in seconds. No manual tagging ever.
- **Knowledge gaps.** curiosity tracks 15 configurable knowledge domains and tells you where you're strong and where you're exposed. "You have 28 sources on AI but only 2 on positioning."
- **Daily review.** Spaced repetition for your knowledge base. Old insights resurface on a schedule so you remember what you read, not just that you read it.
- **Connections.** "This article about team onboarding shares 3 topics with a piece you saved about knowledge management 2 months ago." Ideas link across time and domain.
- **Expert tracking.** Follow authors. curiosity monitors for their new work and includes it in your daily sweep.
- **Ask anything.** Type a question, get answers sourced from your own knowledge base. Like having a research assistant who's read everything you've ever saved.
- **Rules engine.** "If the domain is github.com, tag it 'code' and add it to my Dev Tools collection." Automate your organization.
- **RSS feeds.** Subscribe to sources. New articles flow into the enrichment pipeline automatically. curiosity is always listening.
- **Works offline.** SQLite-native, local-first. Your data stays on your machine. No cloud account, no subscription, no API costs.

**What makes it different from Raindrop, Pocket, or Readwise:**

Raindrop organizes. Pocket saves for later. Readwise helps you remember highlights. curiosity does all three, plus it reads everything you save, maps your knowledge, finds what's missing, and discovers new sources to fill the gaps. It's not a bookmark manager — it's a knowledge system.

**What makes it different from Karakeep/Hoarder:**

Karakeep is a better filing cabinet. curiosity is a learning partner. Karakeep stores and tags your bookmarks. curiosity reads them, scores their learning value, discovers how they connect, tracks your expertise gaps, follows authors, generates digests, and runs spaced repetition on your insights. Same capture surface, fundamentally different intelligence layer.

**Pricing:** Free. Open source. Zero API costs — all AI analysis runs inside your existing Claude Code session.

**Install:**
```
pip install curiosity-kb
curiosity serve
```

**Learn more:** github.com/[repo]

---

## FAQ

**Q: How is the AI free? Don't summaries and enrichment cost money?**

A: curiosity runs as an MCP server inside Claude Code. When you enrich a bookmark, Claude reads it and produces the analysis as part of your existing Claude session. There are no separate API calls, no OpenAI key, no per-bookmark charges. If you're already using Claude Code, enrichment is included.

**Q: Can I use it without Claude Code?**

A: The web UI (browse, search, review, discover) works standalone. Enrichment requires Claude Code or any MCP-compatible AI tool. A future version may support local models via Ollama.

**Q: How does it compare to Obsidian?**

A: Obsidian is a writing tool where you build knowledge manually through notes and links. curiosity is a reading tool where knowledge builds automatically from what you save. They're complementary — curiosity exports to Obsidian format, so your enriched bookmarks can flow into your Obsidian vault.

**Q: What about mobile?**

A: The web UI is responsive and works in mobile browsers. A PWA wrapper is planned. Native apps are not on the roadmap — the web does this well enough.

**Q: I have 2,000 bookmarks. Will it handle them?**

A: Yes. SQLite with FTS5 full-text search handles millions of records. Enrichment is the bottleneck — processing 2,000 bookmarks takes time, but it happens incrementally. You don't need to enrich everything at once.

**Q: What if a page I saved goes down?**

A: curiosity archives full-page HTML (via Monolith for self-contained files), can auto-submit to the Wayback Machine, and checks for broken links. Your knowledge survives link rot.

**Q: Is my data private?**

A: Completely. SQLite on your machine. No telemetry, no cloud sync, no account. Export to markdown anytime. You own everything.

---

## Internal Tenets (not for publication)

1. **Knowledge compounds.** The more you use it, the smarter it gets, the harder it is to leave. This is the moat.
2. **Show, don't store.** Every other tool stores bookmarks. We show you what they mean, how they connect, and what you're missing.
3. **Zero friction capture, maximum friction forgetting.** Saving is one click. Forgetting is prevented by spaced repetition, weekly digests, and gap tracking.
4. **AI is invisible.** Users don't "run AI" — they save a link and insights appear. The intelligence is ambient.
5. **Local-first is a feature, not a limitation.** Privacy, speed, no subscription, no vendor lock-in. This is what users actually want.
