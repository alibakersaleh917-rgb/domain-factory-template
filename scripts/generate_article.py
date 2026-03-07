import os
import re
import time
import random
import datetime
from pathlib import Path

import requests
from difflib import SequenceMatcher

OPENROUTER_KEY = os.environ["OPENROUTER_KEY"]

# اقتصادي وعملي
WRITER_MODEL = "google/gemini-2.0-flash-lite-001"
REVIEW_MODEL = "mistralai/mistral-small-24b-instruct-2501"

CONFIG = {
    "domain": "anwaltsagent.de",
    "niche": "Rechtsberatung",
    "geo": "Deutschland",
    "audience": "Unternehmen und Privatpersonen",
    "keywords": [
        "Anwalt finden Deutschland",
        "Rechtsanwalt beauftragen online",
        "Anwaltssuche Deutschland",
        "günstige Rechtsberatung online",
        "Anwalt Erstberatung Kosten",
        "bester Anwalt Deutschland finden",
    ],
}

POSTS_DIR = Path("content/posts")
TODAY = datetime.datetime.utcnow().strftime("%Y-%m-%d")
KEYWORD = random.choice(CONFIG["keywords"])


def call_openrouter(prompt: str, model: str, max_tokens: int = 2200) -> str:
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.8,
        },
        timeout=180,
    )

    if response.status_code != 200:
        raise Exception(f"{response.status_code}: {response.text[:500]}")

    return response.json()["choices"][0]["message"]["content"].strip()


def slugify(text: str) -> str:
    text = text.lower().strip()
    replacements = {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "ß": "ss",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)

    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-{2,}", "-", text)
    return text.strip("-")


def extract_markdown_block(text: str) -> str:
    # لو رجّع الموديل markdown fenced block
    match = re.search(r"```(?:markdown|md)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text.strip()


def has_valid_frontmatter(article: str) -> bool:
    if not article.startswith("---"):
        return False

    parts = article.split("---", 2)
    if len(parts) < 3:
        return False

    fm = parts[1]
    required = ["title:", "date:", "description:", "keywords:"]
    return all(field in fm for field in required)


def parse_frontmatter(article: str):
    parts = article.split("---", 2)
    if len(parts) < 3:
        return None, None

    frontmatter = parts[1].strip()
    body = parts[2].strip()

    def grab(pattern: str, default: str = "") -> str:
        m = re.search(pattern, frontmatter, re.MULTILINE)
        return m.group(1).strip() if m else default

    title = grab(r'^title:\s*["\']?(.*?)["\']?$')
    description = grab(r'^description:\s*["\']?(.*?)["\']?$')
    date_value = grab(r'^date:\s*["\']?(.*?)["\']?$')
    keywords_line = grab(r"^keywords:\s*(.*?)$")

    return {
        "title": title,
        "description": description,
        "date": date_value,
        "keywords_line": keywords_line,
    }, body


def normalize_keywords_line(keywords_line: str, fallback_keyword: str) -> str:
    if not keywords_line:
        return f'["{fallback_keyword}"]'

    keywords_line = keywords_line.strip()

    # لو كانت جاهزة كـ list
    if keywords_line.startswith("[") and keywords_line.endswith("]"):
        return keywords_line

    # لو رجعت كنص عادي
    return f'["{fallback_keyword}"]'


def normalize_article(article: str) -> str:
    article = extract_markdown_block(article)

    # إزالة أي نص قبل أول frontmatter
    if "---" in article:
        article = article[article.find("---"):].strip()

    parsed, body = parse_frontmatter(article)

    if not parsed or not body:
        raise ValueError("Invalid article structure")

    title = parsed["title"] or f"{KEYWORD} – Ratgeber und Tipps"
    description = parsed["description"] or f"Erfahren Sie mehr über {KEYWORD} auf {CONFIG['domain']}."
    keywords_line = normalize_keywords_line(parsed["keywords_line"], KEYWORD)

    # تثبيت التاريخ بصيغة آمنة لهوغو
    date_value = TODAY

    clean = f"""---
title: "{title}"
date: "{date_value}"
description: "{description}"
keywords: {keywords_line}
---

{body.strip()}
"""
    return clean


def keyword_count(text: str, keyword: str) -> int:
    return text.lower().count(keyword.lower())


def is_duplicate(new_article: str, threshold: float = 0.70) -> bool:
    POSTS_DIR.mkdir(parents=True, exist_ok=True)

    for path in POSTS_DIR.glob("*.md"):
        old = path.read_text(encoding="utf-8", errors="ignore")
        ratio = SequenceMatcher(None, old, new_article).ratio()
        if ratio > threshold:
            return True

    return False


def generate_prompt(keyword: str) -> str:
    return f"""
Du bist ein professioneller deutscher SEO-Content-Writer.

Schreibe einen hochwertigen Blogartikel für die Domain {CONFIG["domain"]}.

WICHTIG:
- Schreibe NUR auf Deutsch.
- Keine Einleitung außerhalb des Artikels.
- Gib NUR Markdown zurück.
- Der Artikel muss mit gültigem YAML-Frontmatter beginnen.
- Verwende exakt dieses Datumsformat: "{TODAY}"

Kontext:
- Domain: {CONFIG["domain"]}
- Nische: {CONFIG["niche"]}
- Region: {CONFIG["geo"]}
- Zielgruppe: {CONFIG["audience"]}
- Haupt-Keyword: {keyword}

Anforderungen:
- Länge: 1000 bis 1300 Wörter
- Struktur: 1 H1, 4 bis 5 H2, kurzes Fazit
- Professioneller, vertrauenswürdiger Stil
- Keine übertriebene Werbung
- Das Keyword natürlich verwenden
- Am Ende eine dezente Erwähnung, dass diese Domain für passende Kanzleien, Legal-Tech-Projekte oder Vermittlungsdienste interessant sein kann

Verwende dieses genaue Format:

---
title: "..."
date: "{TODAY}"
description: "..."
keywords: ["{keyword}"]
---

# Titel

Artikeltext...
""".strip()


def review_prompt(article: str, keyword: str) -> str:
    return f"""
Du bist ein strenger deutscher SEO-Editor.

Überarbeite den folgenden Artikel.

Regeln:
- Behalte YAML-Frontmatter.
- Behalte die deutsche Sprache.
- Gib NUR Markdown zurück.
- Entferne Füllsätze und KI-typische Formulierungen.
- Mache den Stil natürlicher und klarer.
- Stelle sicher, dass das Haupt-Keyword "{keyword}" natürlich ungefähr 3 bis 5 Mal vorkommt.
- Erhalte die Struktur.
- Ändere das Datum nicht.

Artikel:
{article}
""".strip()


def save_article(article: str, title: str) -> Path:
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    slug = slugify(title) or f"artikel-{random.randint(1000, 9999)}"
    filename = POSTS_DIR / f"{TODAY}-{slug}.md"
    filename.write_text(article, encoding="utf-8")
    return filename


def main():
    print(f"Keyword selected: {KEYWORD}")

    for attempt in range(3):
        try:
            draft = call_openrouter(generate_prompt(KEYWORD), WRITER_MODEL)
            draft = normalize_article(draft)

            if not has_valid_frontmatter(draft):
                raise ValueError("Draft frontmatter invalid")

            reviewed = call_openrouter(review_prompt(draft, KEYWORD), REVIEW_MODEL)
            reviewed = normalize_article(reviewed)

            if not has_valid_frontmatter(reviewed):
                print("Reviewed version invalid, using draft.")
                reviewed = draft

            count = keyword_count(reviewed, KEYWORD)
            if count < 2 or count > 6:
                print(f"Keyword count out of preferred range: {count}")

            if is_duplicate(reviewed):
                raise ValueError("Generated article is too similar to an existing post")

            parsed, _ = parse_frontmatter(reviewed)
            title = parsed["title"] if parsed else f"artikel-{random.randint(1000, 9999)}"

            saved_path = save_article(reviewed, title)
            print(f"Saved: {saved_path}")
            return

        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(2 ** attempt)

    raise Exception("Failed after 3 attempts")


if __name__ == "__main__":
    main()
