#!/usr/bin/env python3
"""Smoke-test keyword tracker and sitemap ping system."""

from __future__ import annotations

from keyword_tracker import KeywordTracker
from sitemap_ping import ping_search_engines


def test_keyword_tracker() -> None:
    print("Testing Keyword Tracker...")
    tracker = KeywordTracker()
    stats = tracker.get_stats()
    print(f"Queue: {stats['queue_remaining']}")
    print(f"Status: {stats['status']}")
    print(f"Next: {tracker.get_next_keyword()}")
    print("Keyword Tracker OK")


def test_sitemap_ping() -> None:
    print("Testing Sitemap Ping...")
    ping_search_engines()
    print("Sitemap Ping completed")


if __name__ == "__main__":
    test_keyword_tracker()
    test_sitemap_ping()
