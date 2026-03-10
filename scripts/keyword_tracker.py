#!/usr/bin/env python3
"""Keyword tracking system for Anwaltsagent.de."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


class KeywordTracker:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or Path(".")
        self.queue_file = self.base_dir / "keywords/queue.txt"
        self.used_file = self.base_dir / "keywords/used.txt"
        self.log_file = self.base_dir / "logs/keyword_log.txt"
        self.archive_dir = self.base_dir / "keywords/archive"

        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        for path in (self.queue_file, self.used_file, self.log_file):
            path.touch(exist_ok=True)

    def _log(self, message: str) -> None:
        entry = f"[{datetime.now().isoformat()}] {message}"
        with self.log_file.open("a", encoding="utf-8") as handle:
            handle.write(entry + "\n")
        print(entry)

    def _read_queue(self) -> list[str]:
        with self.queue_file.open("r", encoding="utf-8") as handle:
            return [line.strip() for line in handle if line.strip()]

    def _used_keywords(self) -> set[str]:
        with self.used_file.open("r", encoding="utf-8") as handle:
            return {line.split("|", 1)[0].strip() for line in handle if line.strip()}

    def _remove_from_queue(self, keyword: str) -> None:
        queue = [item for item in self._read_queue() if item != keyword]
        content = "\n".join(queue)
        if content:
            content += "\n"
        self.queue_file.write_text(content, encoding="utf-8")

    def _archive_keyword(self, keyword: str) -> None:
        archive_file = self.archive_dir / f"{datetime.now().strftime('%Y-%m-%d')}.txt"
        with archive_file.open("a", encoding="utf-8") as handle:
            handle.write(keyword + "\n")

    def get_next_keyword(self) -> str | None:
        queue = self._read_queue()
        if not queue:
            self._log("ERROR: Queue is empty")
            return None

        if len(queue) < 5:
            self._log(f"WARNING: Only {len(queue)} keywords remaining in queue")

        used = self._used_keywords()
        for keyword in queue:
            if keyword not in used:
                self._log(f"SELECTED: {keyword}")
                return keyword
            self._log(f"DUPLICATE: {keyword} already used; removing from queue")
            self._remove_from_queue(keyword)
        return None

    def mark_as_used(self, keyword: str) -> None:
        timestamp = datetime.now().isoformat()
        with self.used_file.open("a", encoding="utf-8") as handle:
            handle.write(f"{keyword}|{timestamp}\n")
        self._remove_from_queue(keyword)
        self._archive_keyword(keyword)
        self._log(f"USED: {keyword}")

    def get_stats(self) -> dict[str, int | str]:
        queue_remaining = len(self._read_queue())
        used_count = len(self._used_keywords())
        return {
            "queue_remaining": queue_remaining,
            "total_used": used_count,
            "status": "OK" if queue_remaining >= 5 else "WARNING",
        }


if __name__ == "__main__":
    tracker = KeywordTracker()
    stats = tracker.get_stats()
    print(f"Queue: {stats['queue_remaining']}")
    print(f"Used: {stats['total_used']}")
    print(f"Status: {stats['status']}")
    print(f"Next keyword: {tracker.get_next_keyword()}")
