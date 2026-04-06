"""Autonomous orchestrator — the proactive brain of Curiosity.

NO direct Anthropic API calls. Background processes handle the mechanical work
(fetch pages, detect new bookmarks, run web searches). Enrichment (summarize,
tag, rate) happens when Claude Code reads the pending queue.

Background loop:
    New bookmark detected → fetch page → store raw text → mark as 'fetched'
    Claude Code reads curiosity://pending → analyzes in batch → calls enrich_bookmark

Daily sweep:
    Search for followed experts + knowledge gaps → store candidates
    Claude Code reads curiosity://sweep → reviews → calls ingest_url on the good ones
"""

import os
import time
import logging
import threading
import queue
from datetime import datetime
from typing import Optional

from .config import CuriosityConfig
from .db import CuriosityDB
from .ingestion import ingest_single
from .connections import find_topic_connections, store_connections
from .gaps import seed_default_domains
from .watcher import ChromeBookmarkWatcher, WebhookServer
from .models import now_iso

logger = logging.getLogger("curiosity.orchestrator")


class CuriosityOrchestrator:
    """Autonomous learning engine — fetch and queue, let Claude Code think."""

    def __init__(self, db: CuriosityDB, config: CuriosityConfig):
        self.db = db
        self.config = config
        self._db_path = config.db_path

        self._queue: queue.Queue = queue.Queue()
        self._worker_thread: Optional[threading.Thread] = None
        self._running = False

        self._sweep_thread: Optional[threading.Thread] = None
        self._last_sweep: Optional[datetime] = None
        self._sweep_hour: int = 8
        self._sweep_interval_hours: int = 24
        self._last_sweep_result: Optional[dict] = None

        self._watcher: Optional[ChromeBookmarkWatcher] = None
        self._webhook: Optional[WebhookServer] = None

        self._stats = {
            "started_at": None,
            "bookmarks_fetched": 0,
            "sweeps_completed": 0,
            "errors": 0,
            "queue_processed": 0,
            "last_activity": None,
        }

    def _new_db(self) -> CuriosityDB:
        return CuriosityDB(self._db_path)

    # ── Lifecycle ─────────────────────────────────────────────

    def start(self):
        if self._running:
            return

        self._running = True
        self._stats["started_at"] = now_iso()
        seed_default_domains(self.db)

        self._worker_thread = threading.Thread(
            target=self._pipeline_loop, name="curiosity-pipeline", daemon=True,
        )
        self._worker_thread.start()

        if self.config.chrome_bookmarks_path and self.config.chrome_bookmarks_path.exists():
            self._watcher = ChromeBookmarkWatcher(
                bookmarks_path=self.config.chrome_bookmarks_path,
                on_new_bookmark=self._on_chrome_bookmark,
                poll_interval=self.config.chrome_poll_interval,
            )
            self._watcher.start()
            logger.info(f"Chrome watcher started: {self.config.chrome_bookmarks_path}")

        try:
            self._webhook = WebhookServer(
                host=self.config.webhook_host,
                port=self.config.webhook_port,
                on_bookmark=self._on_webhook_event,
            )
            self._webhook.start()
            logger.info(f"Webhook server on {self.config.webhook_host}:{self.config.webhook_port}")
        except OSError as e:
            logger.warning(f"Webhook failed (port busy?): {e}")

        self._sweep_thread = threading.Thread(
            target=self._sweep_scheduler, name="curiosity-sweep", daemon=True,
        )
        self._sweep_thread.start()

        logger.info("Curiosity orchestrator started")

    def stop(self):
        self._running = False
        if self._watcher:
            self._watcher.stop()
        if self._webhook:
            self._webhook.stop()
        self._queue.put(None)
        if self._worker_thread:
            self._worker_thread.join(timeout=10)
        if self._sweep_thread:
            self._sweep_thread.join(timeout=5)
        logger.info("Curiosity orchestrator stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    # ── Event Handlers ────────────────────────────────────────

    def _on_chrome_bookmark(self, bookmark_data: dict):
        url = bookmark_data.get("url", "")
        if not url or not url.startswith(("http://", "https://")):
            return
        logger.info(f"Chrome watcher: {url[:80]}")
        self._queue.put({
            "url": url,
            "title": bookmark_data.get("title", ""),
            "source": "chrome",
            "chrome_folder": bookmark_data.get("folder", ""),
            "chrome_added_at": bookmark_data.get("chrome_added_at"),
        })

    def _on_webhook_event(self, event_data: dict):
        event_type = event_data.get("event", "")
        url = event_data.get("url", "")
        if not url or not url.startswith(("http://", "https://")):
            return
        if event_type in ("created", "manual_ingest"):
            logger.info(f"Extension: {event_type} {url[:80]}")
            self._queue.put({
                "url": url,
                "title": event_data.get("title", ""),
                "source": "chrome" if event_type == "created" else "manual",
            })

    def ingest_url(self, url: str, title: str = ""):
        self._queue.put({"url": url, "title": title, "source": "manual"})

    # ── Pipeline Worker (fetch only, no AI) ───────────────────

    def _pipeline_loop(self):
        thread_db = self._new_db()

        while self._running:
            try:
                item = self._queue.get(timeout=5)
            except queue.Empty:
                continue

            if item is None:
                break

            try:
                self._fetch_item(item, thread_db)
                self._stats["queue_processed"] += 1
                self._stats["last_activity"] = now_iso()
            except Exception as e:
                self._stats["errors"] += 1
                logger.error(f"Fetch error for {item.get('url', '?')}: {e}")

        thread_db.close()

    def _fetch_item(self, item: dict, db: CuriosityDB):
        """Fetch and store only — no AI calls."""
        url = item["url"]

        existing = db.get_bookmark_by_url(url)
        if existing and existing.status in ("enriched", "fetched"):
            return

        bookmark = ingest_single(
            url=url,
            db=db,
            config=self.config,
            source=item.get("source", "manual"),
            title=item.get("title") or None,
            chrome_folder=item.get("chrome_folder"),
            chrome_added_at=item.get("chrome_added_at"),
        )

        if bookmark.status == "fetched":
            self._stats["bookmarks_fetched"] += 1
            logger.info(f"Fetched: {bookmark.title or url[:60]}")

            # Build connections if topics exist
            try:
                conns = find_topic_connections(db, bookmark_id=bookmark.id, min_overlap=1)
                if conns:
                    store_connections(db, bookmark.id, conns, "same_topic")
            except Exception:
                pass

    # ── Daily Sweep Scheduler ─────────────────────────────────

    def _sweep_scheduler(self):
        thread_db = self._new_db()

        while self._running:
            try:
                now = datetime.now()
                should_sweep = False

                if self._last_sweep is None:
                    if now.hour >= self._sweep_hour:
                        should_sweep = True
                else:
                    hours_since = (now - self._last_sweep).total_seconds() / 3600
                    if hours_since >= self._sweep_interval_hours and now.hour >= self._sweep_hour:
                        should_sweep = True

                if should_sweep:
                    self._run_sweep(thread_db)

            except Exception as e:
                logger.error(f"Sweep scheduler error: {e}")

            for _ in range(60):
                if not self._running:
                    break
                time.sleep(5)

        thread_db.close()

    def _run_sweep(self, db: Optional[CuriosityDB] = None):
        """Run daily sweep — web search only, no AI. Results stored for Claude Code."""
        logger.info("=== Daily sweep starting ===")
        self._last_sweep = datetime.now()

        owns_db = False
        if db is None:
            db = self._new_db()
            owns_db = True

        try:
            from .research import daily_sweep
            brave_key = os.environ.get("BRAVE_SEARCH_API_KEY")

            result = daily_sweep(
                db,
                brave_api_key=brave_key,
                max_total=self.config.max_discoveries_per_day,
            )

            self._last_sweep_result = result
            self._stats["sweeps_completed"] += 1
            logger.info(f"Sweep found {result.get('total_found', 0)} candidates")

        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Daily sweep failed: {e}")
        finally:
            if owns_db:
                db.close()

    def trigger_sweep(self):
        threading.Thread(target=self._run_sweep, daemon=True).start()
        return {"status": "sweep_triggered"}

    # ── Status ────────────────────────────────────────────────

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "started_at": self._stats.get("started_at"),
            "queue_size": self._queue.qsize(),
            "watcher_active": self._watcher is not None and self._watcher._running,
            "webhook_active": self._webhook is not None and self._webhook._server is not None,
            "chrome_path": str(self.config.chrome_bookmarks_path) if self.config.chrome_bookmarks_path else None,
            "webhook_port": self.config.webhook_port,
            "last_sweep": self._last_sweep.isoformat() if self._last_sweep else None,
            "sweep_candidates": len(self._last_sweep_result.get("candidates", [])) if self._last_sweep_result else 0,
            "next_sweep_hour": f"{self._sweep_hour}:00",
            "stats": self._stats,
        }

    def get_sweep_results(self) -> Optional[dict]:
        return self._last_sweep_result
