#!/usr/bin/env python3
"""curiosity CLI — start the web UI or MCP server."""

import sys
from pathlib import Path

__all__ = ["main"]

def _find_ui_dir() -> str:
    """Find the directory containing ui.py. Works in dev and Docker."""
    # 1. Current working directory (Docker: /app)
    cwd = Path.cwd()
    if (cwd / "ui.py").exists():
        return str(cwd)
    # 2. Relative to this file (dev: mcp/curiosity/src/curiosity/cli.py -> mcp/curiosity/)
    dev_root = Path(__file__).resolve().parent.parent.parent
    if (dev_root / "ui.py").exists():
        return str(dev_root)
    # 3. Fallback: search common locations
    for candidate in [Path("/app"), Path.home() / "curiosity"]:
        if (candidate / "ui.py").exists():
            return str(candidate)
    return str(cwd)  # last resort


def _serve(port: int = 8080, host: str = "127.0.0.1") -> None:
    """Start the curiosity web UI."""
    import uvicorn

    ui_dir = _find_ui_dir()
    if ui_dir not in sys.path:
        sys.path.insert(0, ui_dir)

    print(f"curiosity — http://{host}:{port}")
    uvicorn.run("ui:app", host=host, port=port)


def main() -> None:
    args = sys.argv[1:]
    cmd = args[0] if args else "serve"

    if cmd == "serve":
        port = 8080
        host = "127.0.0.1"
        if "--port" in args:
            port = int(args[args.index("--port") + 1])
        if "--host" in args:
            host = args[args.index("--host") + 1]
        _serve(port=port, host=host)

    elif cmd == "mcp":
        # Delegate to the existing MCP server entry point
        from curiosity.server import main as mcp_main
        mcp_main()

    elif cmd == "version":
        from curiosity import __version__
        print(f"curiosity {__version__}")

    else:
        print("Usage: curiosity <command>")
        print()
        print("Commands:")
        print("  serve [--port 8080] [--host 127.0.0.1]   Start the web UI (default)")
        print("  mcp                                       Start the MCP server")
        print("  version                                   Show version")
        sys.exit(1)


if __name__ == "__main__":
    main()
