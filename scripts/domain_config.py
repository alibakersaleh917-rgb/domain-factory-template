import json
from pathlib import Path

DEFAULT_CONFIG = {
    "domain": "example.com",
    "brand_name": "Example",
    "niche": "digitale Services",
    "geo": "Deutschland",
    "language": "de",
    "audience": "Unternehmen und Privatpersonen",
    "brand_positioning": "Vertrauenswürdige, moderne Marke mit klarem Nutzenversprechen.",
    "keywords": [
        "digitale beratung",
        "online dienstleister finden",
        "service vergleich",
    ],
    "seo_keyword_hints": "vergleich, kosten, auswahl, tipps",
    "article_tone": "informativ, klar und professionell",
    "image_style_hints": "professional office; consultation; business meeting",
    "article_cta": (
        "Wenn Sie eine starke Marke in dieser Nische aufbauen möchten, "
        "kann **Example** eine interessante Domain für Ihr Projekt sein."
    ),
    "topic_buckets": [
        "informational",
        "comparison",
        "cost/pricing",
        "checklist/how-to",
        "mistakes to avoid",
        "faq",
        "niche-specific subtopics",
        "location-based topics",
        "trends / future of the niche",
        "tools / software / platforms",
    ],
    "title_angle_patterns": [
        "how-to",
        "guide",
        "checklist",
        "comparison",
        "mistakes",
        "costs",
        "best practices",
        "trends",
        "faq",
        "decision framework",
    ],
    "recent_posts_memory_limit": 30,
    "title_similarity_threshold": 0.75,
    "intent_similarity_threshold": 0.70,
    "slug_similarity_threshold": 0.70,
}


def parse_simple_yaml(path: Path) -> dict:
    root = {}
    stack = [(0, root)]

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue

        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()

        while stack and indent < stack[-1][0]:
            stack.pop()

        container = stack[-1][1]

        if stripped.startswith("- "):
            value = stripped[2:].strip().strip('"')
            if isinstance(container, list):
                container.append(value)
            continue

        if ":" not in stripped:
            continue

        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()

        if value == "":
            next_container = {}
            container[key] = next_container
            stack.append((indent + 2, next_container))
        else:
            container[key] = value.strip('"')

    lines = path.read_text(encoding="utf-8").splitlines()

    seo = root.get("seo") if isinstance(root.get("seo"), dict) else {}
    vals = []
    in_seo = False
    seo_indent = None
    in_kw = False
    kw_indent = None
    for raw in lines:
        if not in_seo and raw.strip() == "seo:":
            in_seo = True
            seo_indent = len(raw) - len(raw.lstrip(" "))
            continue
        if in_seo:
            if not raw.strip():
                continue
            indent = len(raw) - len(raw.lstrip(" "))
            st = raw.strip()
            if indent <= seo_indent:
                break
            if not in_kw and st == "keywords:":
                in_kw = True
                kw_indent = indent
                continue
            if in_kw:
                if indent <= kw_indent:
                    break
                if st.startswith("- "):
                    vals.append(st[2:].strip().strip('"'))
    if vals:
        seo["keywords"] = vals
        root["seo"] = seo

    return root


def _normalize_loaded_config(loaded: dict) -> dict:
    if not loaded:
        return {}

    content = loaded.get("content") or {}
    seo = loaded.get("seo") or {}

    normalized = {
        "domain": loaded.get("domain"),
        "brand_name": loaded.get("brand_name"),
        "niche": loaded.get("niche"),
        "geo": loaded.get("country") or loaded.get("geo"),
        "language": loaded.get("language"),
        "audience": loaded.get("audience"),
        "brand_positioning": loaded.get("brand_positioning") or (loaded.get("homepage") or {}).get("subheadline"),
        "keywords": seo.get("keywords") or loaded.get("keywords"),
        "seo_keyword_hints": content.get("seo_keyword_hints") or loaded.get("seo_keyword_hints"),
        "article_tone": content.get("article_tone") or loaded.get("article_tone"),
        "image_style_hints": content.get("image_style_hints") or loaded.get("image_style_hints"),
        "article_cta": content.get("article_cta") or loaded.get("article_cta"),
        "topic_buckets": _split_pipe_or_comma_list(content.get("topic_buckets") or loaded.get("topic_buckets")),
        "title_angle_patterns": _split_pipe_or_comma_list(content.get("title_angle_patterns") or loaded.get("title_angle_patterns")),
        "recent_posts_memory_limit": _to_int(content.get("recent_posts_memory_limit") or loaded.get("recent_posts_memory_limit")),
        "title_similarity_threshold": _to_float(content.get("title_similarity_threshold") or loaded.get("title_similarity_threshold")),
        "intent_similarity_threshold": _to_float(content.get("intent_similarity_threshold") or loaded.get("intent_similarity_threshold")),
        "slug_similarity_threshold": _to_float(content.get("slug_similarity_threshold") or loaded.get("slug_similarity_threshold")),
    }
    return {k: v for k, v in normalized.items() if v is not None}


def _split_pipe_or_comma_list(raw: str | list | None):
    if not raw:
        return None
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    text = str(raw)
    separator = "|" if "|" in text else ","
    values = [item.strip() for item in text.split(separator)]
    return [item for item in values if item]


def _to_int(raw):
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _to_float(raw):
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def load_domain_config(config_path: Path | str) -> dict:
    path = Path(config_path)
    if not path.exists():
        return DEFAULT_CONFIG.copy()

    if path.suffix.lower() == ".json":
        loaded = json.loads(path.read_text(encoding="utf-8"))
    else:
        loaded = parse_simple_yaml(path)

    config = DEFAULT_CONFIG.copy()
    config.update(_normalize_loaded_config(loaded))
    if not config.get("keywords"):
        config["keywords"] = DEFAULT_CONFIG["keywords"]
    return config
