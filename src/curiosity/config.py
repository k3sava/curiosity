"""Configuration management for Curiosity (Artemis Learning Management System)."""

from __future__ import annotations

import os
import platform
from pathlib import Path
from dataclasses import dataclass, field


def _artemis_root() -> Path:
    """Detect Artemis project root from this file's location.

    Path: config.py → src/curiosity/ → src/ → mcp/curiosity/ → mcp/ → artemis/
    """
    return Path(__file__).resolve().parent.parent.parent.parent.parent


def _default_db_path() -> Path:
    """Default database path inside Artemis data/ directory."""
    return _artemis_root() / "data" / "curiosity.db"


def _default_chrome_bookmarks_path() -> Path | None:
    """Find Chrome's Bookmarks file on this platform."""
    system = platform.system()
    candidates = []
    if system == "Darwin":
        candidates = [
            Path.home() / "Library/Application Support/Google/Chrome/Default/Bookmarks",
            Path.home() / "Library/Application Support/Google/Chrome/Profile 1/Bookmarks",
        ]
    elif system == "Linux":
        candidates = [
            Path.home() / ".config/google-chrome/Default/Bookmarks",
            Path.home() / ".config/chromium/Default/Bookmarks",
        ]
    elif system == "Windows":
        local = Path(os.environ.get("LOCALAPPDATA", ""))
        candidates = [
            local / "Google/Chrome/User Data/Default/Bookmarks",
        ]

    for path in candidates:
        if path.exists():
            return path
    return None


def _default_knowledge_dir() -> Path:
    """Default export directory for Artemis-format markdown files."""
    return _artemis_root() / "knowledge" / "sources" / "articles"


@dataclass
class CuriosityConfig:
    """All configuration for Curiosity, loaded from env vars with sensible defaults."""

    # Database — lives in Artemis data/ directory
    db_path: Path = field(default_factory=_default_db_path)

    # Artemis integration
    artemis_root: Path = field(default_factory=_artemis_root)
    knowledge_export_dir: Path = field(default_factory=_default_knowledge_dir)

    # Chrome integration
    chrome_bookmarks_path: Path | None = field(default_factory=_default_chrome_bookmarks_path)
    chrome_poll_interval: int = 60  # seconds

    # Webhook server (receives events from Chrome extension)
    webhook_host: str = "127.0.0.1"
    webhook_port: int = 7277

    # Ingestion
    fetch_timeout: int = 15  # seconds per URL
    max_content_length: int = 12000  # chars for raw text truncation
    fetch_max_workers: int = 8  # concurrent URL fetches

    # Research agent
    discoveries_per_bookmark: int = 5
    max_discoveries_per_day: int = 50
    discovery_delay: float = 2.0  # seconds between fetches

    # Supabase (optional)
    supabase_url: str = ""
    supabase_key: str = ""
    sync_interval: int = 300  # seconds (5 min)

    @classmethod
    def from_env(cls) -> "CuriosityConfig":
        """Load config from environment variables."""
        config = cls()

        if db := os.environ.get("CURIOSITY_DB"):
            config.db_path = Path(db).expanduser()

        if root := os.environ.get("ARTEMIS_ROOT"):
            config.artemis_root = Path(root).expanduser()
            # Re-derive dependent paths if artemis root overridden
            config.knowledge_export_dir = config.artemis_root / "knowledge" / "sources" / "articles"
            if not os.environ.get("CURIOSITY_DB"):
                config.db_path = config.artemis_root / "data" / "curiosity.db"

        if export_dir := os.environ.get("CURIOSITY_KNOWLEDGE_DIR"):
            config.knowledge_export_dir = Path(export_dir).expanduser()

        if chrome := os.environ.get("CURIOSITY_CHROME_BOOKMARKS"):
            config.chrome_bookmarks_path = Path(chrome).expanduser()

        if port := os.environ.get("CURIOSITY_WEBHOOK_PORT"):
            config.webhook_port = int(port)

        if url := os.environ.get("SUPABASE_URL"):
            config.supabase_url = url

        if key := os.environ.get("SUPABASE_KEY"):
            config.supabase_key = key

        return config

    def ensure_data_dir(self):
        """Create the data directory if it doesn't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
