#!/usr/bin/env python3
"""Resolve [INTERNAL_LINK: keyword] placeholders into Hugo post links."""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

POSTS_DIR = Path("content/posts")
PLACEHOLDER_RE = re.compile(r"\[INTERNAL_LINK:\s*([^\]]+)\]", re.IGNORECASE)
HUGO_LINK_RE = re.compile(r"\[[^\]]+\]\(/posts/[^)]+/\)")


@dataclass
class PostMeta:
    slug: str
    title: str


def _parse_title(markdown_text: str) -> str:
    match = re.search(r'^title:\s*"?(.*?)"?$', markdown_text, flags=re.MULTILINE)
    return (match.group(1).strip() if match else "").strip()


def _read_posts() -> list[PostMeta]:
    posts: list[PostMeta] = []
    if not POSTS_DIR.exists():
        return posts

    for path in POSTS_DIR.glob("*.md"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        title = _parse_title(text) or path.stem
        slug = path.stem.split("-", 3)[-1] if "-" in path.stem else path.stem
        posts.append(PostMeta(slug=slug, title=title))
    return posts


def _score(query: str, post: PostMeta) -> float:
    query_l = query.lower().strip()
    title_l = post.title.lower()
    slug_l = post.slug.lower()
    return max(
        SequenceMatcher(None, query_l, title_l).ratio(),
        SequenceMatcher(None, query_l, slug_l).ratio(),
    )


def _best_match(query: str, posts: list[PostMeta], used_slugs: set[str]) -> PostMeta | None:
    candidates = [p for p in posts if p.slug not in used_slugs]
    if not candidates:
        return None
    ranked = sorted(candidates, key=lambda p: _score(query, p), reverse=True)
    top = ranked[0]
    return top if _score(query, top) >= 0.2 else None


def resolve_internal_links(markdown_text: str, min_links: int = 3, max_links: int = 5) -> str:
    posts = _read_posts()
    used_slugs: set[str] = set()
    replacements = 0

    def _replace(match: re.Match[str]) -> str:
        nonlocal replacements
        if replacements >= max_links:
            return ""
        keyword = match.group(1).strip()
        picked = _best_match(keyword, posts, used_slugs)
        if not picked:
            return keyword
        used_slugs.add(picked.slug)
        replacements += 1
        anchor = keyword if len(keyword) <= 60 else picked.title
        return f"[{anchor}](/posts/{picked.slug}/)"

    updated = PLACEHOLDER_RE.sub(_replace, markdown_text)
    link_count = len(HUGO_LINK_RE.findall(updated))

    if link_count < min_links:
        deficit = min_links - link_count
        pool = [p for p in posts if p.slug not in used_slugs][:deficit]
        if pool:
            lines = ["", "## Weiterführende interne Links", ""]
            for post in pool:
                lines.append(f"- [{post.title}](/posts/{post.slug}/)")
            updated = updated.rstrip() + "\n" + "\n".join(lines) + "\n"

    return updated
