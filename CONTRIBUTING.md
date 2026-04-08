# Contributing to curiosity

Thanks for your interest. Here's how to get started.

## Setup

```bash
git clone https://github.com/k3sava/curiosity.git
cd curiosity
pip install -e ".[all]"
curiosity serve
```

Open `http://localhost:8080`. That's it. SQLite database gets created automatically on first run.

## Running tests

```bash
pip install -e ".[dev]"
pytest tests/
```

Tests use a temporary database, so they won't touch your real data.

## Architecture

- **Python / FastAPI** for the web server
- **SQLite** with FTS5 for storage and search
- **Jinja2 templates** for HTML, server-rendered
- **Vanilla JS + CSS** in `static/`, no build step
- **MCP server** in `src/curiosity/server.py` for Claude Code integration

Key files:
- `ui.py` -- FastAPI routes and application logic
- `src/curiosity/db.py` -- schema and database operations
- `src/curiosity/server.py` -- MCP tool definitions
- `templates/` -- Jinja2 HTML templates
- `static/` -- CSS, JS, images

No React. No Webpack. No Electron. Just Python and HTML.

## Code style

Follow what's already there. No strict linter config yet. The basics:

- Python 3.10+
- `snake_case` for Python, `kebab-case` for filenames
- Prefer stdlib over adding dependencies
- Keep it simple

## Contributing

PRs are welcome. For small fixes (typos, bugs, CSS tweaks), go ahead and open a PR directly. For bigger changes (new features, architectural shifts), open an issue first so we can discuss.

1. Fork the repo, create a branch from `main`
2. Make your changes
3. Run `pytest tests/`
4. Open a PR. Describe what changed and why.
