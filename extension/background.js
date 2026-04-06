/**
 * Curiosity Chrome Extension — Background Service Worker
 *
 * Listens for bookmark creation, edit, and deletion events in Chrome,
 * then forwards them to the local Curiosity webhook server (port 7277).
 *
 * The MCP server ingests new bookmarks automatically.
 */

const WEBHOOK_URL = "http://127.0.0.1:7277/bookmark";

// ── Bookmark Events ──────────────────────────────────────────

chrome.bookmarks.onCreated.addListener((id, bookmark) => {
  if (!bookmark.url) return; // Folder, not a bookmark

  sendEvent("created", {
    chrome_id: id,
    url: bookmark.url,
    title: bookmark.title || "",
    folder_id: bookmark.parentId,
    index: bookmark.index,
  });
});

chrome.bookmarks.onChanged.addListener((id, changeInfo) => {
  // Get the full bookmark to include URL
  chrome.bookmarks.get(id, (results) => {
    if (chrome.runtime.lastError || !results || !results.length) return;
    const bookmark = results[0];
    if (!bookmark.url) return;

    sendEvent("updated", {
      chrome_id: id,
      url: bookmark.url,
      title: changeInfo.title || bookmark.title || "",
      old_url: changeInfo.url !== undefined ? bookmark.url : undefined,
    });
  });
});

chrome.bookmarks.onRemoved.addListener((id, removeInfo) => {
  if (!removeInfo.node.url) return; // Folder

  sendEvent("removed", {
    chrome_id: id,
    url: removeInfo.node.url,
    title: removeInfo.node.title || "",
  });
});

chrome.bookmarks.onMoved.addListener((id, moveInfo) => {
  chrome.bookmarks.get(id, (results) => {
    if (chrome.runtime.lastError || !results || !results.length) return;
    const bookmark = results[0];
    if (!bookmark.url) return;

    sendEvent("moved", {
      chrome_id: id,
      url: bookmark.url,
      title: bookmark.title || "",
      old_parent: moveInfo.oldParentId,
      new_parent: moveInfo.parentId,
    });
  });
});

// ── Send to Webhook ──────────────────────────────────────────

async function sendEvent(eventType, data) {
  const payload = {
    event: eventType,
    timestamp: new Date().toISOString(),
    ...data,
  };

  try {
    const response = await fetch(WEBHOOK_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      console.warn(`[Curiosity] Webhook responded ${response.status}`);
    }
  } catch (error) {
    // Server not running — that's fine, fail silently.
    // The file-based watcher is the fallback.
    console.debug(`[Curiosity] Server not reachable: ${error.message}`);
  }
}

// ── Extension Icon Click ─────────────────────────────────────

chrome.action.onClicked.addListener(async (tab) => {
  // Quick-ingest the current tab
  if (tab.url && tab.url.startsWith("http")) {
    sendEvent("manual_ingest", {
      url: tab.url,
      title: tab.title || "",
      source: "extension_click",
    });

    // Brief visual feedback
    chrome.action.setBadgeText({ text: "✓", tabId: tab.id });
    chrome.action.setBadgeBackgroundColor({ color: "#10B981" });
    setTimeout(() => {
      chrome.action.setBadgeText({ text: "", tabId: tab.id });
    }, 2000);
  }
});
