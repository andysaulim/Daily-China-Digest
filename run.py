"""
China Daily Brief — Pipeline Entry Point
Orchestrates collect → digest → validate → render → send → archive.
"""
import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


# ─────────────────────────────────────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent
COLLECTED_JSON = ROOT / "collected.json"
DIGEST_JSON = ROOT / "digest.json"
DIGEST_HTML = ROOT / "digest.html"
PUBLIC_DIR = ROOT / "public"


# ─────────────────────────────────────────────────────────────────────────────
# VALIDATION GATE
# ─────────────────────────────────────────────────────────────────────────────

PRESTIGE_SOURCES = {
    "WSJ China", "NYT China", "WaPo China", "Bloomberg China", "FT China",
    "Economist China", "CNN China", "Reuters China", "CNBC China",
}

ENTERTAINMENT_BLOCK = ("celebrity", "lifestyle", "fashion", "drama", "boyband",
                      "girlband", "concert tour")


def _count_words(digest: dict) -> int:
    """Count readable words across all text fields."""
    text_fields = ("body", "body_text", "summary", "detail", "quote_text",
                   "so_what", "pattern_note", "central_argument", "analyst_note",
                   "headline", "action")
    words = 0

    for mi in (digest.get("morning_memo") or []):
        if isinstance(mi, dict):
            for v in mi.values():
                if isinstance(v, str):
                    words += len(v.split())
        elif isinstance(mi, str):
            words += len(mi.split())

    for key in ("top_stories", "overnight_items", "also_today", "business_economy",
                "indo_pacific", "social_statements", "opeds_today", "academic_today",
                "prc_government", "congressional_watch", "personnel_changes"):
        for item in (digest.get(key) or []):
            if not isinstance(item, dict):
                continue
            for field in text_fields:
                val = item.get(field, "")
                if val:
                    words += len(str(val).split())

    delta = digest.get("xinhua_delta") or {}
    for field in ("bottom_line", "doctrinal_shift"):
        val = delta.get(field, "")
        if val:
            words += len(str(val).split())

    return words


def _validate_digest(digest: dict) -> list[str]:
    """Run pre-send quality checks. Returns list of failures (empty = pass)."""
    failures = []

    word_count = _count_words(digest)
    if word_count < 1000:
        failures.append(f"WORD COUNT: {word_count} words (minimum 1000)")

    top_count = len(digest.get("top_stories") or [])
    if top_count < 2:
        failures.append(f"TOP STORIES: {top_count} (minimum 2)")
    if top_count > 4:
        failures.append(f"TOP STORIES: {top_count} (maximum 4)")

    overnight_count = len(digest.get("overnight_items") or [])
    if overnight_count < 3:
        failures.append(f"OVERNIGHT ITEMS: {overnight_count} (minimum 3)")

    memo = digest.get("morning_memo") or []
    if len(memo) != 3:
        failures.append(f"MORNING MEMO: {len(memo)} items (must be exactly 3)")

    # Source diversity check
    all_items = (digest.get("top_stories") or []) + (digest.get("overnight_items") or [])
    source_counts = {}
    for item in all_items:
        src = (item.get("source") or "").strip()
        if src:
            source_counts[src] = source_counts.get(src, 0) + 1
    for src, count in source_counts.items():
        if count > 3:
            failures.append(f"SOURCE DIVERSITY: '{src}' appears {count} times "
                          f"in top + overnight (max 3)")

    # Date integrity
    digest_date = digest.get("digest_date", "")
    today_str = datetime.now(ZoneInfo("America/New_York")).strftime("%A, %B %-d, %Y")
    if digest_date and digest_date != today_str:
        failures.append(f"DATE MISMATCH: digest_date='{digest_date}' vs today='{today_str}'")

    # Placeholder URL check
    for key in ("top_stories", "overnight_items", "also_today"):
        for item in (digest.get(key) or []):
            url = (item.get("url") or "").strip()
            if url in ("#", "None", "null", ""):
                continue  # missing URL is OK; will be handled by render
            if "example.com" in url or "placeholder" in url.lower():
                failures.append(f"PLACEHOLDER URL in {key}: {url}")

    return failures


# ─────────────────────────────────────────────────────────────────────────────
# ARCHIVE TO GITHUB PAGES
# ─────────────────────────────────────────────────────────────────────────────

def _archive_html(html: str, digest: dict) -> None:
    """Write the dated HTML to public/ for GitHub Pages."""
    PUBLIC_DIR.mkdir(exist_ok=True)
    date_str = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")

    dated_file = PUBLIC_DIR / f"{date_str}.html"
    dated_file.write_text(html, encoding="utf-8")

    # Latest pointer
    latest_file = PUBLIC_DIR / "index.html"
    latest_file.write_text(html, encoding="utf-8")

    # Append to archive index
    archive_index = PUBLIC_DIR / "archive.json"
    archive = []
    if archive_index.exists():
        try:
            archive = json.loads(archive_index.read_text())
        except json.JSONDecodeError:
            archive = []

    entry = {
        "date": date_str,
        "filename": f"{date_str}.html",
        "top_stories": len(digest.get("top_stories") or []),
        "overnight_items": len(digest.get("overnight_items") or []),
        "word_count": _count_words(digest),
    }
    # Replace today's entry if it already exists
    archive = [a for a in archive if a.get("date") != date_str]
    archive.insert(0, entry)
    archive_index.write_text(json.dumps(archive[:120], indent=2))

    print(f"📁 Archived to {dated_file.name}")


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

def run_pipeline(args: argparse.Namespace) -> int:
    """Execute the full pipeline. Returns exit code."""
    print(f"\n{'=' * 64}")
    print(f"  CHINA DAILY BRIEF — {datetime.now(ZoneInfo('America/New_York')).strftime('%A, %B %-d, %Y at %I:%M %p ET')}")
    print(f"{'=' * 64}\n")

    pipeline_start = time.time()

    # ─── Collect ─────────────────────────────────────────────────────────
    if args.from_cache and COLLECTED_JSON.exists():
        print("📂 Loading cached collection from disk...")
        payload = json.loads(COLLECTED_JSON.read_text(encoding="utf-8"))
        print(f"   • Loaded {sum(len(v) for k, v in payload.items() if isinstance(v, list))} articles")
    else:
        print("🌐 Collecting from RSS feeds...")
        from collect import collect_all
        payload = collect_all()
        COLLECTED_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
        total = sum(len(v) for k, v in payload.items() if isinstance(v, list))
        unique_sources = set()
        for tier in ("tier1", "tier2", "tier3", "tier4"):
            for art in payload.get(tier, []):
                src = art.get("source")
                if src:
                    unique_sources.add(src)
        print(f"   • {total} articles from {len(unique_sources)} unique sources")

    if args.dry_run:
        print(f"\n✅ Dry run complete. Cached to {COLLECTED_JSON.name}")
        return 0

    # ─── Database context (Hidden Reach / AMTI updates if available) ─────
    db_context = ""
    try:
        from databases import build_db_context
        db_context = build_db_context()
        if db_context:
            print(f"📊 Database context loaded ({len(db_context)} chars)")
    except Exception as e:
        print(f"⚠ Database context unavailable: {e}")

    # ─── Digest ──────────────────────────────────────────────────────────
    print("\n🤖 Generating digest...")
    from digest import generate_digest
    digest = generate_digest(payload, db_context=db_context)
    DIGEST_JSON.write_text(json.dumps(digest, ensure_ascii=False, indent=2),
                          encoding="utf-8")

    # ─── Update persistent trackers ──────────────────────────────────────
    try:
        from xi_tracker import update_from_digest as update_xi
        update_xi(digest)
    except Exception as e:
        print(f"⚠ Xi tracker update failed (non-fatal): {e}")

    try:
        from xinhua_tracker import update_from_digest as update_xinhua
        update_xinhua(digest)
    except Exception as e:
        print(f"⚠ Xinhua tracker update failed (non-fatal): {e}")

    try:
        from bp_tracker import update_from_digest as update_bp
        update_bp(digest)
    except Exception as e:
        print(f"⚠ BP tracker update failed (non-fatal): {e}")

    # ─── Validate ────────────────────────────────────────────────────────
    print("\n🔍 Validating digest...")
    failures = _validate_digest(digest)
    if failures:
        print("⚠ Validation failures:")
        for f in failures:
            print(f"   • {f}")
        if not args.force_send:
            print("\n   Use --force-send to override validation gate.")
            # Non-fatal: continue to render so Sau can review
    else:
        print("   ✓ All validation checks passed")

    # ─── Render ──────────────────────────────────────────────────────────
    print("\n🎨 Rendering HTML email...")
    from render import render_html
    html = render_html(digest)
    DIGEST_HTML.write_text(html, encoding="utf-8")
    print(f"   • Wrote {len(html):,} bytes to {DIGEST_HTML.name}")

    # ─── Archive ─────────────────────────────────────────────────────────
    if not args.no_archive:
        _archive_html(html, digest)

    # ─── Update README ───────────────────────────────────────────────────
    try:
        from update_readme import update_readme
        update_readme()
    except Exception as e:
        print(f"⚠ README update failed (non-fatal): {e}")

    # ─── Send ────────────────────────────────────────────────────────────
    if args.no_send:
        print("\n📭 --no-send: skipping email send.")
    else:
        print("\n📧 Sending email...")
        from send_email import send_digest
        sent = send_digest(html)
        if not sent:
            print("   ⚠ Send failed or skipped")

    elapsed = time.time() - pipeline_start
    print(f"\n{'=' * 64}")
    print(f"  ✅ Pipeline complete in {elapsed:.0f}s")
    print(f"{'=' * 64}\n")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="China Daily Brief — orchestration entry point"
    )
    parser.add_argument("--dry-run", action="store_true",
                       help="Collect only; skip digest/render/send")
    parser.add_argument("--from-cache", action="store_true",
                       help="Reuse cached collected.json (skip collection)")
    parser.add_argument("--no-send", action="store_true",
                       help="Generate HTML but don't email")
    parser.add_argument("--no-archive", action="store_true",
                       help="Skip writing to public/ archive")
    parser.add_argument("--force-send", action="store_true",
                       help="Send even if validation gates fail")
    args = parser.parse_args()

    try:
        return run_pipeline(args)
    except KeyboardInterrupt:
        print("\n\n⚠ Interrupted by user")
        return 130
    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
