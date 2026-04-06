"""Chrome bookmark file watcher + webhook receiver for real-time sync."""

import json
import time
import threading
import hashlib
from pathlib import Path
from typing import Optional, Callable
from http.server import HTTPServer, BaseHTTPRequestHandler

from .config import CuriosityConfig


class ChromeBookmarkWatcher:
    """Polls Chrome's Bookmarks JSON file for changes.

    Chrome stores bookmarks at a platform-specific path as a JSON file.
    This watcher polls it periodically and calls a callback when new
    bookmarks are detected.
    """

    def __init__(
        self,
        bookmarks_path: Path,
        on_new_bookmark: Callable[[dict], None],
        poll_interval: int = 60,
    ):
        self.bookmarks_path = bookmarks_path
        self.on_new_bookmark = on_new_bookmark
        self.poll_interval = poll_interval
        self._last_hash: Optional[str] = None
        self._known_urls: set[str] = set()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Start the watcher in a background thread."""
        if self._running:
            return

        # Initialize known URLs
        self._load_known_urls()
        self._last_hash = self._file_hash()
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _poll_loop(self):
        while self._running:
            try:
                current_hash = self._file_hash()
                if current_hash and current_hash != self._last_hash:
                    self._last_hash = current_hash
                    self._check_for_new()
            except Exception:
                pass
            time.sleep(self.poll_interval)

    def _file_hash(self) -> Optional[str]:
        try:
            content = self.bookmarks_path.read_bytes()
            return hashlib.md5(content).hexdigest()
        except (FileNotFoundError, PermissionError):
            return None

    def _load_known_urls(self):
        """Load all URLs from Chrome's current bookmarks file."""
        try:
            data = json.loads(self.bookmarks_path.read_text(encoding="utf-8"))
            self._extract_urls(data.get("roots", {}), self._known_urls)
        except Exception:
            pass

    def _check_for_new(self):
        """Check for newly added bookmarks."""
        try:
            data = json.loads(self.bookmarks_path.read_text(encoding="utf-8"))
            current_urls: set[str] = set()
            all_bookmarks: list[dict] = []
            self._extract_bookmarks(data.get("roots", {}), current_urls, all_bookmarks)

            new_urls = current_urls - self._known_urls
            if new_urls:
                for bookmark in all_bookmarks:
                    if bookmark.get("url") in new_urls:
                        self.on_new_bookmark(bookmark)

            self._known_urls = current_urls
        except Exception:
            pass

    def _extract_urls(self, node: dict, urls: set):
        """Recursively extract URLs from Chrome bookmark JSON."""
        if isinstance(node, dict):
            if node.get("type") == "url" and node.get("url"):
                urls.add(node["url"])
            for key in ("children", "bookmark_bar", "other", "synced"):
                child = node.get(key)
                if isinstance(child, dict):
                    self._extract_urls(child, urls)
                elif isinstance(child, list):
                    for item in child:
                        self._extract_urls(item, urls)

    def _extract_bookmarks(self, node: dict, urls: set, bookmarks: list, folder_path: str = ""):
        """Recursively extract bookmark details from Chrome JSON."""
        if isinstance(node, dict):
            if node.get("type") == "url" and node.get("url"):
                urls.add(node["url"])
                bookmarks.append({
                    "url": node["url"],
                    "title": node.get("name", ""),
                    "folder": folder_path,
                    "chrome_added_at": node.get("date_added"),
                })
            name = node.get("name", "")
            current_path = f"{folder_path}/{name}" if folder_path and name else (name or folder_path)

            for key in ("children", "bookmark_bar", "other", "synced"):
                child = node.get(key)
                if isinstance(child, dict):
                    self._extract_bookmarks(child, urls, bookmarks, current_path)
                elif isinstance(child, list):
                    for item in child:
                        self._extract_bookmarks(item, urls, bookmarks, current_path)


class WebhookHandler(BaseHTTPRequestHandler):
    """HTTP handler for receiving bookmark events from the Chrome extension."""

    callback: Optional[Callable] = None

    def do_POST(self):
        if self.path == "/bookmark":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)

            try:
                data = json.loads(body)
                if self.callback:
                    self.callback(data)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok"}).encode())
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress default logging


class WebhookServer:
    """Runs a tiny HTTP server for receiving Chrome extension events."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7277,
        on_bookmark: Optional[Callable[[dict], None]] = None,
    ):
        self.host = host
        self.port = port
        self.on_bookmark = on_bookmark
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self):
        WebhookHandler.callback = self.on_bookmark
        self._server = HTTPServer((self.host, self.port), WebhookHandler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self):
        if self._server:
            self._server.shutdown()
