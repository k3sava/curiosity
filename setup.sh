#!/bin/bash
# curiosity (Artemis LMS) — one-time setup script
# Run from: /Users/kesava/Projects/artemis/mcp/curiosity
# Requires: uv (installed at ~/.local/bin/uv)
set -e

CURIOSITY_DIR="/Users/kesava/Projects/artemis/mcp/curiosity"
VENV_DIR="$CURIOSITY_DIR/.venv"
UV="$HOME/.local/bin/uv"

echo "=== 1. Creating Python 3.12 virtual environment ==="
cd "$CURIOSITY_DIR"
"$UV" venv --python 3.12 "$VENV_DIR"
echo "  Created: $VENV_DIR"

echo ""
echo "=== 2. Installing curiosity ==="
"$UV" pip install -e ".[all]" --python "$VENV_DIR/bin/python" --quiet
echo "  Installed"

echo ""
echo "=== 3. Registering MCP server in Claude Code ==="
claude mcp add curiosity \
    -s user \
    -- "$VENV_DIR/bin/curiosity-mcp"
echo "  Registered"

echo ""
echo "=== 4. Verifying ==="
"$VENV_DIR/bin/python" -c "from curiosity.server import main; print('  Module imports OK')"
claude mcp list 2>/dev/null | grep -q curiosity && echo "  MCP server registered OK" || echo "  Check: run 'claude mcp list' to verify"

echo ""
echo "=== Done ==="
echo ""
echo "curiosity is now part of Artemis. Zero extra API cost."
echo "Open a new Claude Code session in artemis and try:"
echo '  /read https://example.com/article'
echo '  "what are my knowledge gaps?"'
echo '  /digest'
