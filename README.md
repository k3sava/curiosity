# curiosity

*makes the cat. meow.*

I wanted to learn about positioning. I found one good article. Then I wanted more — different angles, counterpoints, frameworks I hadn't seen. I ended up with 40 tabs open and no system for any of it.

That's the pattern. You find one thing. You want the full picture. You go down the rabbit hole. And everything you find lives in a different tab, a different bookmark folder, a different app. None of it connects. None of it sticks.

So I built curiosity.

## What is it

Save a link. curiosity reads it, pulls out the key ideas, and finds more — different perspectives, deeper dives, related work you wouldn't have found on your own. Then it quietly organizes everything, connects ideas across topics, and makes sure you don't forget the important parts.

One place for every rabbit hole. That's it.

## How it works

Save a link. Any link.

curiosity reads the whole page and gives you back what matters — a summary, the key insights, topic tags, who wrote it, and whether it's worth your time. No manual tagging. No folders. It just reads.

Then you hit "go deeper." curiosity searches the web for related pieces — alternatives, counterpoints, deeper dives on the same topic. Save the ones worth keeping with one click. Your library grows around the things you're actually curious about.

Over time, it starts connecting things. That positioning article from March? It shares three ideas with a design thinking piece you saved last week. You didn't see the connection. curiosity did.

And every morning, it pulls out something you saved weeks ago and says: *remember this?*

## Get started

```
pip install curiosity-kb
curiosity serve
```

Open localhost:8080. Paste a URL. Hit "go deeper." Watch what happens.

Docker:

```
docker run -p 8080:8080 -v curiosity_data:/data ghcr.io/k3sava/curiosity
```

## What you can do with it

**Go deeper.** Save one link on a topic. Find 5 more perspectives you wouldn't have searched for. Save the good ones. Follow the rabbit hole.

**Let it learn.** Import your Chrome bookmarks. Subscribe to RSS feeds. Upload PDFs and images. curiosity reads everything and organizes it automatically. No tagging, no folders, no maintenance.

**Remember what matters.** Daily review cards resurface old insights. Connections show how ideas link across topics. Highlights save the sentences worth keeping.

**Power tools.** Automation rules, bulk actions, collections, page archival, video downloads, dark mode, ⌘K command palette. The nerdy stuff lives in the background until you need it.

## The AI part

curiosity uses AI to read your bookmarks. It tries three providers in order — you only need one:

**Ollama (free, local):** Install [Ollama](https://ollama.com), pull a model, done. No API key, no cloud, no cost. This is the default.

```
ollama pull llama3
curiosity serve
```

**Google Gemini (free tier):** Get a free key from [Google AI Studio](https://aistudio.google.com). 15 requests/min, 1M tokens/day. More than enough.

```
export GEMINI_API_KEY=your-key
curiosity serve
```

**Anthropic (paid):** If you want Claude quality. About a tenth of a penny per bookmark.

```
export ANTHROPIC_API_KEY=sk-ant-...
curiosity serve
```

**Without any AI:** The web UI works fine. You can save, search, organize, and browse. AI adds the automatic summaries, insights, and tagging — but it's not required.

## Why "curiosity"

Because that's what it's for. You found something interesting. You want to learn more. curiosity helps you follow that thread — and makes sure you actually retain what you find along the way.

Also: curiosity makes the cat. Meow.

## Tech

Python. FastAPI. SQLite. Jinja2 templates. No React. No Electron. No build step. Server-rendered. Lightweight.

## Contributing

This started as a personal tool and still feels like one. If you want to help, open an issue first. I have opinions about the design.

## License

MIT
