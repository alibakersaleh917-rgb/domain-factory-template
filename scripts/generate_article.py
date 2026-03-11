#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import random
import re
import time
from pathlib import Path


from domain_config import load_domain_config
from internal_links import resolve_internal_links
from keyword_tracker import KeywordTracker
from sitemap_ping import ping_search_engines

CONFIG_PATH = Path(os.environ.get("DOMAIN_CONFIG_PATH", "data/domain.yaml"))
CONFIG = load_domain_config(CONFIG_PATH)

POSTS_DIR = Path("content/posts")
LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

OPENROUTER_API_KEY = (os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENROUTER_KEY", "")).strip()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

STAGE_1_MODEL = "anthropic/claude-3.5-sonnet"
STAGE_2_MODEL = "llama-3.3-70b-versatile"
STAGE_3_MODEL = "llama-3.3-70b-versatile"
GROQ_FALLBACK_MODEL = "llama-3.3-70b-versatile"

logger = logging.getLogger("generation")
logger.setLevel(logging.INFO)
handler = logging.FileHandler(LOG_DIR / "generation.log", encoding="utf-8")
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(handler)


def log_stage_duration(stage: str, started_at: float) -> None:
    logger.info("stage=%s duration_s=%.2f", stage, time.perf_counter() - started_at)


def validate_api_key(key_name: str, key_value: str) -> str:
    key = (key_value or "").strip()
    if not key:
        raise RuntimeError(f"{key_name} is missing or empty")
    if key.startswith("Bearer "):
        raise RuntimeError(f"{key_name} should NOT include the 'Bearer ' prefix")
    if "\n" in key or "\r" in key:
        raise RuntimeError(f"{key_name} contains newline characters")
    if '"' in key or "'" in key:
        raise RuntimeError(f"{key_name} should not contain quotes")
    return key

def validate_api_key(key_name: str, key_value: str) -> str:
    key = (key_value or "").strip()
    if not key:
        raise RuntimeError(f"{key_name} is missing or empty")
    if key.startswith("Bearer "):
        raise RuntimeError(f"{key_name} should NOT include the 'Bearer ' prefix")
    if "\n" in key or "\r" in key:
        raise RuntimeError(f"{key_name} contains newline characters")
    if '"' in key or "'" in key:
        raise RuntimeError(f"{key_name} should not contain quotes")
    return key

def slugify(text: str) -> str:
    text = text.lower().strip()
    for src, dst in {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}.items():
        text = text.replace(src, dst)
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return re.sub(r"-{2,}", "-", text).strip("-")


def parse_frontmatter(md: str) -> tuple[dict[str, str], str]:
    if not md.startswith("---"):
        return {}, md
    parts = md.split("---", 2)
    if len(parts) < 3:
        return {}, md
    fm_raw = parts[1]
    body = parts[2].strip()
    fm: dict[str, str] = {}
    for line in fm_raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fm[key.strip()] = value.strip().strip('"')
    return fm, body


def strip_code_fence(text: str) -> str:
    m = re.search(r"```(?:markdown|md)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    return (m.group(1) if m else text).strip()


def call_with_retry(url: str, api_key: str, model: str, system_prompt: str, user_prompt: str) -> str:
    provider = "OpenRouter" if "openrouter.ai" in url else "Groq"
    clean_key = validate_api_key("OPENROUTER_API_KEY" if provider == "OpenRouter" else "GROQ_API_KEY", api_key)
    headers = {
        "Authorization": f"Bearer {clean_key}",
        "Content-Type": "application/json",
    }

    model_candidates = [model]
    if provider == "Groq" and model != GROQ_FALLBACK_MODEL:
        model_candidates.append(GROQ_FALLBACK_MODEL)

    import requests

    for candidate_model in model_candidates:
        payload = {
            "model": candidate_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.7,
        }

        for attempt in range(1, 4):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=300)
                if resp.status_code == 401:
                    if provider == "OpenRouter":
                        raise RuntimeError("OpenRouter authentication failed. Check OPENROUTER_API_KEY secret.")
                    raise RuntimeError("Groq authentication failed. Check GROQ_API_KEY secret.")

                if resp.status_code == 400 and provider == "Groq" and "model_decommissioned" in (resp.text or ""):
                    if candidate_model != GROQ_FALLBACK_MODEL:
                        logger.warning("Groq model %s is decommissioned; retrying with fallback model %s", candidate_model, GROQ_FALLBACK_MODEL)
                        break
                    raise RuntimeError("Groq model decommissioned and fallback model unavailable. Update configured model.")

                if resp.status_code >= 400:
                    raise RuntimeError(f"{provider} API error {resp.status_code}: {resp.text[:500]}")

                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
            except Exception as exc:
                logger.warning("API call failed model=%s attempt=%s err=%s", candidate_model, attempt, exc)
                if attempt >= 3:
                    raise
                time.sleep(2**attempt)

    raise RuntimeError("All API model candidates failed")


def article_stats() -> tuple[int, int, int]:
    total = pillar = needs_review = 0
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    for path in POSTS_DIR.glob("*.md"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        fm, _ = parse_frontmatter(text)
        total += 1
        if fm.get("pillar", "false").lower() == "true":
            pillar += 1
        if fm.get("needs_review", "false").lower() == "true":
            needs_review += 1
    return total, pillar, needs_review


def choose_publish_count(now: dt.datetime) -> int:
    weekday_base = {0: 3, 1: 0, 2: 1, 3: 2, 4: 1, 5: 0, 6: 1}
    base = weekday_base[now.weekday()]
    if base == 0:
        return random.choice([0, 0, 1])
    return max(0, min(3, base + random.choice([-1, 0, 1])))


def build_stage1_system_prompt() -> str:
    return """You are a professional German SEO content writer.
Write a high-quality article in German for the given keyword.
Requirements:
- Length: randomly choose between SHORT (700-900 words), MEDIUM (1200-1600 words), or LONG (2200-3000 words)
- Vary the article structure each time. Use one of these structures randomly:
  Option A: H1 > H2 > H2 > H2 > FAQ > Conclusion
  Option B: Introduction > H2 > Table > H3 > List > Conclusion
  Option C: H1 > H2 > Comparison table > H2 > FAQ > H2 > Conclusion
- Always include at least 2 of: tables, bullet lists, statistics, quotes, FAQ section
- Cover all SEO entities related to the topic (costs, process, providers, legal info, alternatives)
- Write naturally, vary sentence length, avoid repetition
- Output in markdown format"""


def build_stage2_system_prompt() -> str:
    return """You are an SEO editor. Review the following German article and return an improved version.
Tasks:
- Remove repetition
- Improve headings for SEO
- Improve readability and paragraph flow
- Add any missing SEO entities (cost, process, legal, providers, alternatives)
- Add or improve FAQ section (minimum 3 questions)
- Suggest and insert internal link placeholders as: [INTERNAL_LINK: keyword]
- Return only the improved article in markdown, no explanations"""


def build_stage3_system_prompt() -> str:
    return """You are a native German language editor.
Review the following article:
- Fix all grammar errors
- Improve sentence style and flow
- Make the text sound natural and human-written
- Do not change the structure, headings, or SEO content
- Return only the corrected article in markdown, no explanations"""


def build_frontmatter(title: str, slug: str, description: str, keywords: list[str], body: str, pillar: bool, needs_review: bool) -> str:
    today = dt.datetime.utcnow().strftime("%Y-%m-%d")
    word_count = len(re.findall(r"\w+", body))
    keywords_json = json.dumps(keywords, ensure_ascii=False)
    stages = json.dumps(["claude-3.5-sonnet", "llama-3.3-70b-versatile", "llama-3.3-70b"], ensure_ascii=False)
    return (
        "---\n"
        f'title: "{title}"\n'
        f"date: {today}\n"
        f"lastmod: {today}\n"
        "draft: false\n"
        f'slug: "{slug}"\n'
        f'description: "{description}"\n'
        f"keywords: {keywords_json}\n"
        f"pillar: {'true' if pillar else 'false'}\n"
        f"needs_review: {'true' if needs_review else 'false'}\n"
        f"word_count: {word_count}\n"
        f"pipeline_stages: {stages}\n"
        "---\n\n"
    )


def clean_markdown(md: str) -> str:
    md = strip_code_fence(md)
    if md.startswith("---"):
        _, body = parse_frontmatter(md)
        return body.strip()
    return md.strip()


def extract_title(body: str, keyword: str) -> str:
    m = re.search(r"^#\s+(.+)$", body, flags=re.MULTILINE)
    if m:
        return m.group(1).strip()
    return f"{keyword} – Ratgeber"




def select_keyword(args_keyword: str | None, tracker: KeywordTracker) -> str:
    if args_keyword:
        return args_keyword
    keyword = tracker.get_next_keyword()
    if keyword:
        return keyword
    fallback = CONFIG.get("keywords") or ["Rechtsberatung online"]
    logger.warning("Keyword queue empty; using config fallback")
    return random.choice(fallback)


def generate_one(keyword: str, force_pillar: bool, needs_review: bool, dry_run: bool) -> Path | None:
    validate_api_key("OPENROUTER_API_KEY", OPENROUTER_API_KEY)
    validate_api_key("GROQ_API_KEY", GROQ_API_KEY)

    length_hint = "3000-4000 words" if force_pillar else "700-3000 words"
    stage1_user = (
        f"Keyword: {keyword}\n"
        f"Brand: {CONFIG.get('brand_name', '')}\n"
        f"Domain: {CONFIG.get('domain', '')}\n"
        f"Please ensure roughly {length_hint}."
    )
    stage_start = time.perf_counter()
    stage1 = call_with_retry(OPENROUTER_URL, OPENROUTER_API_KEY, STAGE_1_MODEL, build_stage1_system_prompt(), stage1_user)
    log_stage_duration("stage1_write", stage_start)

    stage_start = time.perf_counter()
    stage2 = call_with_retry(GROQ_URL, GROQ_API_KEY, STAGE_2_MODEL, build_stage2_system_prompt(), stage1)
    log_stage_duration("stage2_seo_review", stage_start)

    stage_start = time.perf_counter()
    stage3 = call_with_retry(GROQ_URL, GROQ_API_KEY, STAGE_3_MODEL, build_stage3_system_prompt(), stage2)
    log_stage_duration("stage3_language_polish", stage_start)

    stage_start = time.perf_counter()
    body = clean_markdown(stage3)
    body = resolve_internal_links(body, min_links=3, max_links=5)
    log_stage_duration("stage4_internal_links", stage_start)

    title = extract_title(body, keyword)
    slug = slugify(title) or f"artikel-{random.randint(1000, 9999)}"
    description = f"Aktueller Überblick zu {keyword}: Kosten, Ablauf, Anbieter und Alternativen."
    article = build_frontmatter(title, slug, description, [keyword], body, force_pillar, needs_review) + body + "\n"

    if dry_run:
        logger.info("Dry-run article generated keyword=%s", keyword)
        return None

    today = dt.datetime.utcnow().strftime("%Y-%m-%d")
    out = POSTS_DIR / f"{today}-{slug}.md"
    out.write_text(article, encoding="utf-8")
    logger.info("Saved article %s", out)
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--keyword", default=None)
    parser.add_argument("--batch-mode", action="store_true", help="Use humanized daily publish counts")
    parser.add_argument("--count", type=int, default=None, help="Force number of generated articles")
    parser.add_argument("--allow-delay", action="store_true", help="Enable randomized publish delay (opt-in)")
    return parser.parse_args()

    if args.count is not None:
        target_count = max(0, min(3, args.count))
    elif args.batch_mode:
        target_count = choose_publish_count(now)
    else:
        target_count = 1

def main() -> None:
    args = parse_args()
    POSTS_DIR.mkdir(parents=True, exist_ok=True)

    now = dt.datetime.utcnow()
    tracker = KeywordTracker()

    if args.count is not None:
        target_count = max(0, min(3, args.count))
    elif args.batch_mode:
        target_count = choose_publish_count(now)
    else:
        target_count = 1

    run_started = time.perf_counter()
    logger.info("Run started target_count=%s batch_mode=%s allow_delay=%s", target_count, args.batch_mode, args.allow_delay)
    if target_count == 0:
        logger.info("No publication today (humanized schedule)")
        log_stage_duration("run_total", run_started)
        return

    total, _pillar_count, review_count = article_stats()

    for i in range(target_count):
        current_index = total + i + 1
        force_pillar = current_index % 10 == 0

        projected_total = total + i + 1
        projected_review = review_count + (1 if (review_count / projected_total) < 0.2 else 0)
        needs_review = (projected_review / projected_total) <= 0.2 and random.random() < 0.5

        keyword = select_keyword(args.keyword, tracker)
        if args.allow_delay:
            delay = random.randint(0, 14400)
            logger.info("Sleeping before publish delay_seconds=%s", delay)
            time.sleep(delay)

        item_started = time.perf_counter()
        path = generate_one(keyword, force_pillar=force_pillar, needs_review=needs_review, dry_run=args.dry_run)
        log_stage_duration("article_iteration", item_started)
        if path and not args.keyword:
            tracker.mark_as_used(keyword)
        logger.info("Article completed path=%s pillar=%s needs_review=%s", path, force_pillar, needs_review)

    if not args.dry_run:
        ping_started = time.perf_counter()
        logger.info("Pinging sitemap after generation")
        ping_search_engines()
        log_stage_duration("sitemap_ping", ping_started)
        stats = tracker.get_stats()
        logger.info("Keyword stats queue_remaining=%s total_used=%s", stats["queue_remaining"], stats["total_used"])

    log_stage_duration("run_total", run_started)


if __name__ == "__main__":
    main()
