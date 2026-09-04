"""
China Daily Brief — README Auto-Updater
Updates the 'Latest Run' table in README.md with metrics from the most recent digest.
Idempotent: replaces the table cleanly without duplicating sections.
"""
import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).parent
README = ROOT / "README.md"
DIGEST_JSON = ROOT / "digest.json"


def _count_words(digest: dict) -> int:
    """Approximate readable word count across all text fields."""
    fields = ("body", "body_text", "summary", "detail", "quote_text",
              "so_what", "pattern_note", "headline", "action")
    words = 0
    for memo in (digest.get("morning_memo") or []):
        if isinstance(memo, dict):
            for v in memo.values():
                if isinstance(v, str):
                    words += len(v.split())
        elif isinstance(memo, str):
            words += len(memo.split())
    for key in ("top_stories", "overnight_items", "also_today",
                "business_economy", "indo_pacific", "social_statements",
                "official_line", "opeds_today", "academic_today",
                "prc_government", "congressional_watch", "personnel_changes"):
        for item in (digest.get(key) or []):
            for f in fields + ("statement", "context", "central_argument", "analyst_note"):
                if isinstance(item, dict) and item.get(f):
                    words += len(str(item[f]).split())
    return words


def _unique_sources(digest: dict) -> int:
    sources = set()
    for key in ("top_stories", "overnight_items", "also_today",
                "business_economy", "indo_pacific", "social_statements"):
        for item in (digest.get(key) or []):
            src = (item.get("source") if isinstance(item, dict) else "") or ""
            if src.strip():
                sources.add(src.strip())
    return len(sources)


def update_readme(metrics: dict | None = None) -> bool:
    """Update the 'Latest Run' table in README.md. Returns True on success."""
    if not README.exists():
        print("⚠ README.md not found — skipping update")
        return False
    if not DIGEST_JSON.exists():
        print("⚠ digest.json not found — skipping README update")
        return False

    try:
        digest = json.loads(DIGEST_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"⚠ digest.json malformed: {e}")
        return False

    now = datetime.now(ZoneInfo("America/New_York"))
    last_generated = now.strftime("%b %-d, %Y at %-I:%M %p ET")
    digest_date = digest.get("digest_date", now.strftime("%A, %B %-d, %Y"))

    # Article count: prefer story_count from digest, else sum sections
    article_count = digest.get("story_count")
    if not article_count:
        article_count = sum(
            len(digest.get(k) or [])
            for k in ("top_stories", "overnight_items", "also_today",
                     "business_economy", "indo_pacific")
        )

    unique_sources = _unique_sources(digest)
    top_count = len(digest.get("top_stories") or [])
    overnight_count = len(digest.get("overnight_items") or [])
    word_count = _count_words(digest)

    xi_appeared = "Yes" if (digest.get("xinhua_delta") or {}).get("xi_appearance_today") else "No"

    m = metrics or {}
    collected = m.get("articles") or article_count
    collected_sources = m.get("sources") or digest.get("source_count") or "—"
    rs = m.get("resolve") or {}
    if rs.get("gnews_total"):
        resolved = f"{rs.get('resolved', 0) + rs.get('cached', 0)}/{rs['gnews_total']}"
    else:
        resolved = "—"
    fulltext = (m.get("fulltext") or {}).get("enriched", "—")
    cost = f"${m['cost_usd']:.2f}" if m.get("cost_usd") is not None else "—"
    attempts = m.get("validation_attempts", "—")
    health = m.get("health") or {}
    alerts = len(health.get("alerts") or [])
    official = len(digest.get("official_line") or [])

    new_table = (
        "| Metric | Value |\n"
        "| --- | --- |\n"
        f"| Last generated | {last_generated} |\n"
        f"| Digest date | {digest_date} |\n"
        f"| Articles collected | {collected} from {collected_sources} sources |\n"
        f"| Sources cited in digest | {unique_sources} |\n"
        f"| Google News URLs canonicalised | {resolved} |\n"
        f"| Items enriched with article text | {fulltext} |\n"
        f"| Top stories / overnight / official line | {top_count} / {overnight_count} / {official} |\n"
        f"| Word count | ~{word_count:,} |\n"
        f"| Validation attempts | {attempts} |\n"
        f"| Health alerts | {alerts} |\n"
        f"| Estimated model cost | {cost} |\n"
        f"| Xi appeared | {xi_appeared} |\n"
    )

    content = README.read_text(encoding="utf-8")

    # Replace the existing 'Latest Run' table
    pattern = re.compile(
        r"(## Latest Run\n+)"
        r"\| Metric \| Value \|\n"
        r"\| --- \| --- \|\n"
        r"(?:\|[^\n]*\|\n)+",
        re.MULTILINE,
    )
    if not pattern.search(content):
        print("⚠ Could not locate 'Latest Run' table in README — skipping")
        return False

    new_content = pattern.sub(r"\1" + new_table, content)
    README.write_text(new_content, encoding="utf-8")
    print(f"📝 README updated — {article_count} articles, {top_count} top stories, ~{word_count:,} words")
    return True


if __name__ == "__main__":
    update_readme()
