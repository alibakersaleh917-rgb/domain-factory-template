#!/usr/bin/env python3
"""Ping Google and Bing sitemaps after article publication."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from urllib.request import urlopen


def ping_search_engines(sitemap_url: str = "https://anwaltsagent.de/sitemap.xml") -> list[str]:
    endpoints = {
        "Google": f"https://www.google.com/ping?sitemap={sitemap_url}",
        "Bing": f"https://www.bing.com/ping?sitemap={sitemap_url}",
    }

    log_file = Path("logs/ping_log.txt")
    log_file.parent.mkdir(parents=True, exist_ok=True)

    results: list[str] = []
    for engine, url in endpoints.items():
        try:
            with urlopen(url, timeout=10) as response:
                status_code = response.getcode()
            status = "SUCCESS" if status_code == 200 else f"FAILED ({status_code})"
            message = f"[{datetime.now().isoformat()}] {engine}: {status}"
        except Exception as exc:
            message = f"[{datetime.now().isoformat()}] {engine}: ERROR - {exc}"
        results.append(message)

    with log_file.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(results) + "\n")

    for result in results:
        print(result)
    return results


if __name__ == "__main__":
    ping_search_engines()
