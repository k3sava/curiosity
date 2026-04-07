# curiosity

*makes the cat. meow.*

I browse a lot. Articles, repos, threads, talks, PDFs. I save them everywhere — Chrome bookmarks, Pocket, Slack, tabs I swear I'll get back to. I never do.

Over 10 years I built up thousands of saved links. A personal internet I'd never revisit. Sound familiar?

I tried Raindrop. Pocket. Hoarder. They organize your links. That was never my problem. My problem was that I had no system. No way to make sense of what I'd collected. No way to connect ideas across topics. No way to remember the good stuff before it faded into the pile.

So I built curiosity.

## What is it

One place for everything you find on the web. Save it. curiosity reads it, pulls out the ideas worth keeping, connects it to what you already know, and makes sure you don't forget the important parts.

That's it. That's the whole thing.

## How it works

Save a link. Any link.

curiosity fetches the page, reads the whole thing, and gives you back what matters — a summary, the key insights, topic tags, who wrote it, and whether it's worth your time. No tagging. No folders. No organizing. It just reads.

Then it starts connecting things. That positioning article from March? It shares three ideas with a design thinking piece you saved last week. You didn't see the connection. curiosity did.

And every morning, it pulls out something you saved weeks ago and says: *remember this?*

## Get started

```
pip install curiosity-kb
curiosity serve
```

Open localhost:8080. Paste a URL. Watch what happens.

Want Docker instead?

```
docker run -p 8080:8080 -v curiosity_data:/data ghcr.io/k3sava/curiosity
```

## What you can do with it

**The basics.** Save URLs. Import your Chrome bookmarks. Upload PDFs and images. Subscribe to RSS feeds. Search across everything you've ever saved.

**The interesting stuff.** Daily review cards that resurface forgotten insights. Connections between bookmarks you didn't know were related. A quiet tracker that notices what topics you read about and which ones you're ignoring.

**The power tools.** Automation rules ("anything from github.com goes in my Dev collection"). Bulk actions. Highlights. Collections. Page archival. Video downloads. Dark mode. A command palette that does everything.

**The nerdy stuff.** MCP server with 17 tools for Claude Code and Claude Desktop. Full-text search via SQLite FTS5. Local-first, no cloud, no account, no subscription.

## The AI part

curiosity uses AI to read your bookmarks. Two ways to do it:

**Free way:** It runs as an MCP server inside Claude Code. Claude reads the page in your session. No API calls. No cost. This is how I use it.

**Standalone way:** Set your `ANTHROPIC_API_KEY` and curiosity calls the API directly. Uses Haiku. Costs about a tenth of a penny per bookmark.

Either way, the AI is invisible. You save a link. Insights appear. You don't think about models or tokens or prompts. It just works.

## Why "curiosity"

Because that's what it's for. Following your curiosity. Saving the things that catch your eye. And having something that helps you actually learn from them instead of letting them rot in a bookmark folder called "Read Later."

Also: curiosity makes the cat. Meow.

## Tech

Python. FastAPI. SQLite. Jinja2 templates. No React. No Electron. No complex build step. One file for the web UI, one for the MCP server. Runs on a Raspberry Pi if you want.

## Contributing

This started as a personal tool and still feels like one. If it's useful to you, that's great. If you want to help make it better, open an issue first. I'm opinionated about the design.

## License

MIT
