#!/usr/bin/env python3

from __future__ import annotations

import datetime as dt
import os
import random
import re
from pathlib import Path



POSTS_DIR = Path("content/posts")
LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
UPDATE_LOG = LOG_DIR / "update_log.txt"
REPORT_LOG = LOG_DIR / "needs_update.txt"

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"
FAQ_PROMPT = (
    "Read this German article and generate ONLY a new FAQ section with 3-5 relevant questions and answers. "
    "Return markdown only, starting with ## Häufig gestellte Fragen"
)


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


def log(msg: str) -> None:
    ts = dt.datetime.utcnow().isoformat()
    with UPDATE_LOG.open("a", encoding="utf-8") as fh:
        fh.write(f"[{ts}] {msg}\n")


def split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---"):
        return "", text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return "", text
    return parts[1], parts[2].lstrip("\n")


def has_faq(body: str) -> bool:
    return bool(re.search(r"^##\s*(FAQ|Häufig gestellte Fragen)", body, flags=re.IGNORECASE | re.MULTILINE))


def get_date_from_frontmatter(frontmatter: str) -> dt.date | None:
    for key in ("date", "lastmod"):
        m = re.search(rf"^{key}:\s*\"?([0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}})", frontmatter, flags=re.MULTILINE)
        if m:
            return dt.date.fromisoformat(m.group(1))
    return None


def update_lastmod(frontmatter: str) -> str:
    today = dt.date.today().isoformat()
    if re.search(r"^lastmod:\s*", frontmatter, flags=re.MULTILINE):
        return re.sub(r"^lastmod:\s*.*$", f"lastmod: {today}", frontmatter, flags=re.MULTILINE)
    return frontmatter.rstrip() + f"\nlastmod: {today}\n"


def word_count(body: str) -> int:
    return len(re.findall(r"\w+", body))


def internal_link_count(body: str) -> int:
    return len(re.findall(r"\[[^\]]+\]\(/posts/[^)]+/\)", body))


def call_groq(article_body: str) -> str:
    clean_key = validate_api_key("GROQ_API_KEY", GROQ_API_KEY)

    import requests

    model_candidates = [MODEL]
    if MODEL != FALLBACK_MODEL:
        model_candidates.append(FALLBACK_MODEL)

    for candidate_model in model_candidates:
        payload = {
            "model": candidate_model,
            "messages": [
                {"role": "system", "content": FAQ_PROMPT},
                {"role": "user", "content": article_body},
            ],
            "temperature": 0.4,
        }

        for attempt in range(1, 4):
            try:
                resp = requests.post(
                    GROQ_URL,
                    headers={"Authorization": f"Bearer {clean_key}", "Content-Type": "application/json"},
                    json=payload,
                    timeout=240,
                )
                if resp.status_code == 401:
                    raise RuntimeError("Groq authentication failed. Check GROQ_API_KEY secret.")
                if resp.status_code == 400 and "model_decommissioned" in (resp.text or ""):
                    if candidate_model != FALLBACK_MODEL:
                        log(f"Groq model {candidate_model} is decommissioned; retrying with fallback {FALLBACK_MODEL}")
                        break
                    raise RuntimeError("Groq model decommissioned and fallback model unavailable. Update configured model.")
                if resp.status_code >= 400:
                    raise RuntimeError(f"Groq API error {resp.status_code}: {resp.text[:400]}")
                content = resp.json()["choices"][0]["message"]["content"].strip()
                return re.sub(r"```(?:markdown|md)?|```", "", content, flags=re.IGNORECASE).strip()
            except Exception as exc:
                log(f"Groq attempt={attempt} model={candidate_model} failed err={exc}")
                if attempt == 3:
                    raise

    raise RuntimeError("All Groq model candidates failed")


def build_weekly_report(rows: list[tuple[str, int, str]]) -> None:
    with REPORT_LOG.open("w", encoding="utf-8") as fh:
        fh.write("Articles needing manual review\n")
        fh.write("=============================\n\n")
        for title, age, reason in rows:
            fh.write(f"- {title} | age: {age} days | reason: {reason}\n")


def main() -> None:
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    today = dt.date.today()
    candidates: list[Path] = []
    report_rows: list[tuple[str, int, str]] = []

    for path in POSTS_DIR.glob("*.md"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        frontmatter, body = split_frontmatter(text)
        title_match = re.search(r'^title:\s*"?(.*?)"?$', frontmatter, flags=re.MULTILINE)
        title = title_match.group(1).strip() if title_match else path.name
        pub_date = get_date_from_frontmatter(frontmatter)
        if not pub_date:
            continue
        age = (today - pub_date).days

        reasons = []
        if age > 180:
            reasons.append("older than 180 days")
        if word_count(body) < 600:
            reasons.append("under 600 words")
        if internal_link_count(body) == 0:
            reasons.append("no internal links")
        if reasons:
            report_rows.append((title, age, ", ".join(reasons)))

        if age > 90 and not has_faq(body):
            candidates.append(path)

    build_weekly_report(report_rows)
    random.shuffle(candidates)
    to_update = candidates[:2]

    for path in to_update:
        text = path.read_text(encoding="utf-8", errors="ignore")
        frontmatter, body = split_frontmatter(text)
        if has_faq(body):
            log(f"skip {path} faq already present")
            continue

        faq = call_groq(body)
        if not faq.lower().startswith("## häufig gestellte fragen"):
            faq = "## Häufig gestellte Fragen\n\n" + faq

        new_frontmatter = update_lastmod(frontmatter)
        updated_body = body.rstrip() + "\n\n" + faq.strip() + "\n"

        out_text = f"---\n{new_frontmatter.strip()}\n---\n\n{updated_body}"
        path.write_text(out_text, encoding="utf-8")
        log(f"updated {path} appended FAQ and lastmod only")

    log(f"run complete updated={len(to_update)}")


if __name__ == "__main__":
    main()
