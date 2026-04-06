"""Parse Chrome bookmark HTML export files."""

from __future__ import annotations

from html.parser import HTMLParser
from datetime import datetime
from urllib.parse import urlparse
from collections import Counter

from .models import ChromeBookmark


class ChromeBookmarkParser(HTMLParser):
    """Parse Chrome's Netscape Bookmark HTML format."""

    def __init__(self):
        super().__init__()
        self.bookmarks: list[ChromeBookmark] = []
        self.folder_stack: list[str] = []
        self.current_link: dict | None = None
        self.in_h3 = False
        self.h3_text = ""
        self.in_a = False
        self.a_text = ""

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        if tag == "a":
            self.in_a = True
            self.a_text = ""
            self.current_link = {
                "url": attrs_dict.get("href", ""),
                "add_date": self._parse_timestamp(attrs_dict.get("add_date", "")),
                "folder_path": "/".join(self.folder_stack) if self.folder_stack else "Uncategorized",
            }
        elif tag == "h3":
            self.in_h3 = True
            self.h3_text = ""

    def handle_endtag(self, tag):
        if tag == "a" and self.current_link:
            self.in_a = False
            url = self.current_link["url"]
            title = self.a_text.strip()
            domain = urlparse(url).netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]

            self.bookmarks.append(ChromeBookmark(
                url=url,
                title=title or url,
                folder_path=self.current_link["folder_path"],
                add_date=self.current_link["add_date"],
                domain=domain,
            ))
            self.current_link = None

        elif tag == "h3":
            self.in_h3 = False
            folder_name = self.h3_text.strip()
            if folder_name:
                self.folder_stack.append(folder_name)

        elif tag == "dl":
            if self.folder_stack:
                self.folder_stack.pop()

    def handle_data(self, data):
        if self.in_a:
            self.a_text += data
        elif self.in_h3:
            self.h3_text += data

    @staticmethod
    def _parse_timestamp(ts_str: str) -> str | None:
        if not ts_str:
            return None
        try:
            return datetime.fromtimestamp(int(ts_str)).isoformat()
        except (ValueError, OSError):
            return None


def parse_chrome_bookmarks(html_content: str) -> list[ChromeBookmark]:
    """Parse Chrome bookmark export HTML and return structured bookmarks."""
    parser = ChromeBookmarkParser()
    parser.feed(html_content)
    return parser.bookmarks


def get_import_stats(bookmarks: list[ChromeBookmark]) -> dict:
    """Generate summary statistics for a parsed bookmark collection."""
    domains = Counter(b.domain for b in bookmarks)
    folders = Counter(b.folder_path for b in bookmarks)

    dates = sorted([b.add_date for b in bookmarks if b.add_date])
    http_bookmarks = [b for b in bookmarks if b.url.startswith(("http://", "https://"))]

    return {
        "total": len(bookmarks),
        "http_urls": len(http_bookmarks),
        "unique_domains": len(domains),
        "folders": len(folders),
        "top_domains": domains.most_common(15),
        "top_folders": folders.most_common(15),
        "date_range": {
            "earliest": dates[0] if dates else None,
            "latest": dates[-1] if dates else None,
        },
    }


def main():
    """CLI entry point for importing Chrome bookmarks."""
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: curiosity-import <bookmarks.html>")
        print("\nExport from Chrome: Bookmark Manager → ⋮ → Export bookmarks")
        sys.exit(1)

    file_path = sys.argv[1]

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            html = f.read()
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        sys.exit(1)

    bookmarks = parse_chrome_bookmarks(html)
    stats = get_import_stats(bookmarks)

    print(f"\nParsed {stats['total']} bookmarks ({stats['http_urls']} HTTP URLs)")
    print(f"  {stats['unique_domains']} unique domains, {stats['folders']} folders")

    if stats["date_range"]["earliest"]:
        print(f"  Date range: {stats['date_range']['earliest'][:10]} → {stats['date_range']['latest'][:10]}")

    print(f"\n  Top domains:")
    for domain, count in stats["top_domains"][:10]:
        print(f"    {count:4d}  {domain}")

    print(f"\n  Top folders:")
    for folder, count in stats["top_folders"][:10]:
        print(f"    {count:4d}  {folder}")


if __name__ == "__main__":
    main()
