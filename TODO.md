# curiosity — fixes, enhancements, improvements

## Critical (before any launch)

- [ ] **Setup wizard on first run** — walk user through: install Ollama OR get free Gemini key. Show instructions in the UI, not just error messages. Test the connection before proceeding.
- [ ] **Home nav link** — add "Home" to topbar or make logo click obvious (visual affordance)
- [ ] **Prominent save action on home** — the Cmd+K trigger is too subtle. Add a visible "Save a link" input on the home page, not just in the command palette.
- [ ] **Performance: reduce home queries** — 11+ DB queries on every home load. Cache stats, batch queries, or compute on a timer.
- [ ] **Library shows pending items with status indicator** — "pending", "fetching", "enriching" badges so users know what's happening
- [ ] **Auto-enrich on save** — if Ollama is available, enrich immediately after fetch. Don't make users click a button.
- [ ] **Fly.io demo: set GEMINI_API_KEY** — so the live demo actually enriches bookmarks

## UX improvements

- [ ] **Cmd+K: show recent saves** — when opened with no query, show last 5 saved items
- [ ] **Home: show pending items** — "3 bookmarks waiting to be enriched" with a "Enrich all" button
- [ ] **Import flow** — after importing Chrome bookmarks, show a progress screen: "Imported 200 bookmarks. Enriching... 12/200"
- [ ] **Toast notifications** — "Saved!" toast when URL is ingested, "Enriched!" when complete
- [ ] **Keyboard shortcuts** — `/` to focus Cmd+K (already works), `n` for new note, `←` to go back
- [ ] **Mobile layout** — topbar nav hides on mobile, hamburger menu or bottom tabs
- [ ] **Loading states** — skeleton cards while library loads, spinner while enriching
- [ ] **Favicon** — a simple cat silhouette or the letter "c"

## Feature polish

- [ ] **Go deeper: auto-run after enrichment** — when a bookmark is enriched, automatically find related content and show suggestions
- [ ] **Review: show connection context** — "This resurfaced because it connects to 3 things you saved recently"
- [ ] **Spaces: remove hardcoded list** — generate spaces dynamically from topic clusters instead of the static SPACES dict in ui.py
- [ ] **Collections: drag-and-drop reorder** — or at least manual sort order
- [ ] **Dark mode: test every page** — some pages may have hardcoded colors that break in dark mode
- [ ] **RSS feeds: auto-fetch on a schedule** — currently manual. Add a background timer.
- [ ] **Export: markdown export from UI** — "Export my library" button that generates an Obsidian-compatible vault

## Code quality

- [ ] **Split ui.py** — 2,800 lines is too much for one file. Split into routes/, services/, db.py
- [ ] **Pin all dependencies** — requirements.txt or lock file for reproducible installs
- [ ] **Tests** — at least: ingest, enrich, search, library render. Pytest + TestClient.
- [ ] **Error handling** — unified error handler, proper logging, no bare `except Exception`
- [ ] **DB migrations** — the get_db() function has 40+ CREATE TABLE / ALTER TABLE statements. Move to a proper migration system.
- [ ] **Remove SPACES dict from globals** — caused Jinja cache hash errors on Fly.io. Pass per-request or use a function.

## Launch prep

- [ ] **Screenshots in README** — home, library, item, review, discover, cmd+k
- [ ] **Demo GIF** — 15-second loop: paste URL → see enrichment → click "go deeper"
- [ ] **Landing page** — single page at curiosity.dev or in /docs served by GitHub Pages
- [ ] **Chrome extension instructions** — how to install, what it does
- [ ] **Issue templates** — bug report + feature request on GitHub
- [ ] **CONTRIBUTING.md** — how to contribute, code style, PR process
- [ ] **Launch posts** — ready in LAUNCH-POSTS.md, need screenshots added
