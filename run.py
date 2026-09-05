"""
China Daily Brief — Pipeline Entry Point
Orchestrates collect → resolve → enrich → digest → post-process → validate
(regenerate on failure) → trackers → render → archive → send → ledger → metrics.

Posture, carried over from the Korea, Japan and Australia briefs after each of
them learned it the hard way:

  * SOURCE-OR-SKIP is enforced in code, not only in the prompt. An item whose
    URL is not in the collected corpus is repaired by headline match or
    deleted. Nothing unsourced ships.
  * The send is fail-closed. A CRITICAL validation finding regenerates (Sonnet,
    then Opus); if it persists the brief is rendered for review, NOT sent, and
    the run exits non-zero so the failure alert fires. The previous version
    printed the failures and sent anyway.
  * Trackers, the published ledger and last_sent.txt are written only after
    validation passes and (for the ledger and marker) only after the email
    actually went out, so a failed run cannot poison state or block a retry.
"""
import argparse
import json
import os
import re
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import wordcount


# ─────────────────────────────────────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent
COLLECTED_JSON = ROOT / "collected.json"
DIGEST_JSON = ROOT / "digest.json"
DIGEST_HTML = ROOT / "digest.html"
PUBLIC_DIR = ROOT / "public"
LEDGER_JSON = ROOT / "published_ledger.json"
LAST_SENT_TXT = ROOT / "last_sent.txt"
METRICS_JSONL = ROOT / "metrics.jsonl"

_LEDGER_WINDOW_DAYS = 14
MAX_VALIDATION_RETRIES = 2

ET = ZoneInfo("America/New_York")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION MAPS
# ─────────────────────────────────────────────────────────────────────────────

# Every list section whose items carry a url. Placement priority order: an item
# that appears twice is kept in the earlier section.
_DEDUPE_ORDER = (
    "top_stories", "korea_china", "overnight_items", "indo_pacific",
    "business_economy", "also_today", "official_line", "opeds_today",
    "academic_today", "social_statements", "prc_government",
    "congressional_watch", "npc_politburo", "personnel_changes",
)
_ALL_ITEM_SECTIONS = _DEDUPE_ORDER

# Sections where an item is an article and therefore MUST carry a URL from the
# corpus. The remaining sections (statements, personnel, committee activity)
# may legitimately summarise something reported inside another article.
_ARTICLE_SECTIONS = (
    "top_stories", "korea_china", "overnight_items", "indo_pacific",
    "business_economy", "also_today", "opeds_today", "academic_today",
)

SECTION_CAPS = {
    "top_stories":       (3, 5),
    "overnight_items":   (4, 8),
    "morning_memo":      (3, 3),
    "korea_china":       (0, 3),
    "also_today":        (0, 8),
    "business_economy":  (0, 6),
    "indo_pacific":      (0, 7),
    "official_line":     (3, 6),
    "social_statements": (0, 6),
    "opeds_today":       (0, 6),
    "academic_today":    (0, 4),
    "prc_government":    (0, 5),
    "congressional_watch": (0, 4),
    "personnel_changes": (0, 5),
    "calendar_watch":    (0, 5),
    "on_this_day":       (0, 1),
}

# 1,600 hard floor, 2,000-2,500 target, 2,700 ceiling: an eight to ten minute
# read. Run 118 landed 1,898 words only because the trim deleted 17 items to
# get there, and the casualties included Xi's expected New Delhi visit and
# Japan's record defence budget. Cutting real stories to protect a number is
# the wrong trade for the flagship brief, so the band moved up to fit the
# reporting rather than the reporting down to fit the band. What did not
# change: the extra words buy MORE ITEMS, never longer bodies. Section caps
# rose with the band; per-item body limits did not.
WORD_FLOOR_CRITICAL = 1600
WORD_TARGET_LOW = 2000
WORD_TARGET_HIGH = 2500
WORD_CEILING = 2700

# Sections the length trim may cut from, in the order the editorial rule says
# to cut: the tail first, never the top stories or Beijing's own words. Each
# entry is (section, floor) — the trim stops at the floor even if still long.
_TRIM_ORDER = (
    ("also_today", 0),
    ("academic_today", 0),
    ("opeds_today", 2),
    ("social_statements", 2),
    ("business_economy", 3),
    ("overnight_items", 5),
    ("indo_pacific", 4),
)

# Gmail truncates a message body over 102 KB and shows "[Message clipped] View
# entire message", which on this brief would cut the tail sections off mid-item
# for every Gmail reader, silently. The June-era issues never came close; the
# relaunch issue hit 79,924 bytes at 2,833 words (~28 bytes/word), and the
# Chinese text in official_line costs three bytes per character. So: warn with
# room to spare, and block the send outright before Gmail can mangle it.
GMAIL_CLIP_BYTES = 102_400
EMAIL_BYTES_WARN = 78_000
EMAIL_BYTES_CRITICAL = 96_000


def check_email_size(html: str) -> list[str]:
    """Guard against Gmail clipping the message body."""
    n = len(html.encode("utf-8"))
    pct = 100 * n / GMAIL_CLIP_BYTES
    if n >= EMAIL_BYTES_CRITICAL:
        return [f"EMAIL SIZE CRITICAL: {n:,} bytes ({pct:.0f}% of Gmail's "
                f"{GMAIL_CLIP_BYTES:,}-byte clipping limit); Gmail would truncate the "
                f"brief mid-item. Shorten the digest."]
    if n >= EMAIL_BYTES_WARN:
        return [f"EMAIL SIZE: {n:,} bytes ({pct:.0f}% of Gmail's clipping limit)"]
    return []

_TEXT_FIELDS = ("body", "body_text", "summary", "detail", "quote_text", "statement",
                "context", "so_what", "pattern_note", "central_argument", "analyst_note",
                "headline", "action", "policy_so_what", "policy_implication", "topic")

_STOP_WORDS = frozenset({
    "the", "a", "an", "in", "on", "of", "to", "for", "and", "is", "at", "by", "as",
    "with", "from", "that", "this", "its", "it", "are", "was", "be", "has", "have",
    "after", "over", "into", "amid", "says", "said", "china", "chinese", "beijing",
    "chinas", "us", "new", "will", "more", "than", "not", "but", "about",
})

_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\U0001F900-\U0001F9FF]")

_HOLLOW_RE = re.compile(
    r"(held (its|a|the) (daily|regular|routine) (press )?(briefing|conference)|"
    r"specific (topics|details) were not (detailed|provided|disclosed)|"
    r"no (further|additional) details were (provided|available|given)|"
    r"addressed (a range of|several|various) (topics|issues|questions)|"
    r"details (remain|were) (unclear|unavailable))",
    re.IGNORECASE,
)


# ─────────────────────────────────────────────────────────────────────────────
# SMALL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _count_words(digest: dict) -> int:
    """Words the reader sees. Defined once in wordcount.py so the prompt target,
    this gate and the rendered header cannot drift apart (they did: run 114
    counted 1,787 here and 2,253 in the validator for the same digest)."""
    return wordcount.count_words(digest)


def _item_url(item: dict) -> str:
    return (item.get("url") or "").strip() if isinstance(item, dict) else ""


def _primary_title(item: dict) -> str:
    if not isinstance(item, dict):
        return ""
    for f in ("headline", "title", "topic", "action", "quote_text", "statement"):
        v = item.get(f)
        if v and isinstance(v, str):
            return v.strip()
    return ""


def _norm_title(text: str) -> str:
    t = re.sub(r"[^a-z0-9一-鿿 ]+", " ", (text or "").lower())
    return re.sub(r"\s+", " ", t).strip()


def _headline_tokens(text: str) -> set[str]:
    return {w for w in re.split(r"\W+", (text or "").lower())
            if len(w) > 3 and w not in _STOP_WORDS}


def _all_text(digest: dict):
    """Yield (location, text) for every string field the reader will see."""
    for i, m in enumerate(digest.get("morning_memo") or []):
        if isinstance(m, str):
            yield f"morning_memo[{i}]", m
    for key in ("re_line", "editor_note"):
        if isinstance(digest.get(key), str):
            yield key, digest[key]
    for section in _ALL_ITEM_SECTIONS:
        for i, item in enumerate(digest.get(section) or []):
            if isinstance(item, dict):
                for f in _TEXT_FIELDS:
                    if isinstance(item.get(f), str):
                        yield f"{section}[{i}].{f}", item[f]
    delta = digest.get("xinhua_delta") or {}
    for f in ("bottom_line", "doctrinal_shift", "propaganda_focus"):
        if isinstance(delta.get(f), str):
            yield f"xinhua_delta.{f}", delta[f]


def _corpus(payload: dict) -> list:
    out = []
    for key in ("tier1", "tier2", "tier3", "tier4",
                "xi_tracker_articles", "hidden_reach_articles", "gray_zone_articles"):
        out.extend(a for a in (payload.get(key) or []) if isinstance(a, dict))
    return out


# ─────────────────────────────────────────────────────────────────────────────
# POST-PROCESSING: the code-level SOURCE-OR-SKIP
# ─────────────────────────────────────────────────────────────────────────────

_PP_STATS: dict = {}


def _strip_style(digest: dict) -> list[str]:
    """Remove emojis; turn em-dashes into plain punctuation. Reports counts."""
    log = []
    emoji_n = dash_n = 0

    def _fix(s: str):
        nonlocal emoji_n, dash_n
        if not isinstance(s, str):
            return s
        n = len(_EMOJI_RE.findall(s))
        if n:
            emoji_n += n
            s = _EMOJI_RE.sub("", s)
        d = s.count("—")
        if d:
            dash_n += d
            s = re.sub(r"\s*—\s*", ", ", s)
        return s

    for i, m in enumerate(digest.get("morning_memo") or []):
        if isinstance(m, str):
            digest["morning_memo"][i] = _fix(m)
    for key in ("re_line", "editor_note"):
        if isinstance(digest.get(key), str):
            digest[key] = _fix(digest[key])
    for section in _ALL_ITEM_SECTIONS:
        for item in (digest.get(section) or []):
            if isinstance(item, dict):
                for f in _TEXT_FIELDS:
                    if isinstance(item.get(f), str):
                        item[f] = _fix(item[f])
    delta = digest.get("xinhua_delta") or {}
    for f in ("bottom_line", "doctrinal_shift"):
        if isinstance(delta.get(f), str):
            delta[f] = _fix(delta[f])
    if emoji_n:
        log.append(f"    - style: stripped {emoji_n} emoji(s)")
    if dash_n:
        log.append(f"    - style: replaced {dash_n} em-dash(es)")
    return log


def _repair_and_gate_urls(digest: dict, payload: dict) -> list[str]:
    """Exact-URL allowlist with headline repair; unsourced article items are deleted.

    The previous sanitiser allowed any URL whose *domain* had been collected,
    so a hallucinated reuters.com path passed, and it blanked everything else
    to "" while leaving the item in place. Both are wrong: the reader got an
    unverifiable item either way.
    """
    log = []
    corpus = _corpus(payload)
    valid_urls = {a.get("url", "") for a in corpus if a.get("url")}
    gnews_to_real = {a.get("gnews_url"): a.get("url") for a in corpus if a.get("gnews_url")}
    index = [(a.get("url", ""), _headline_tokens(a.get("title", "")),
              _norm_title(a.get("title", "")))
             for a in corpus if a.get("url")]
    repaired = dropped = kept_unsourced = 0

    def _match(item: dict):
        title = _primary_title(item)
        nt = _norm_title(title)
        if nt:
            for cand_url, _, cand_nt in index:
                if cand_nt and cand_nt == nt:
                    return cand_url, 1.0
        tokens = _headline_tokens(title)
        if len(tokens) < 3:
            return None, 0.0
        best_url, best = None, 0.0
        for cand_url, cand_tokens, _ in index:
            if not cand_tokens:
                continue
            score = len(tokens & cand_tokens) / min(len(tokens), len(cand_tokens))
            if score > best:
                best_url, best = cand_url, score
        return best_url, best

    def _process(section: str, items: list) -> list:
        nonlocal repaired, dropped, kept_unsourced
        out = []
        for item in items:
            if not isinstance(item, dict):
                continue
            url = _item_url(item)
            if url in gnews_to_real:
                item["url"] = url = gnews_to_real[url]
            if url and url in valid_urls:
                out.append(item)
                continue
            cand, score = _match(item)
            if cand and score >= 0.6:
                item["url"] = cand
                repaired += 1
                log.append(f"    - {section}: '{_primary_title(item)[:50]}' -> repaired URL ({score:.0%})")
                out.append(item)
                continue
            if section in _ARTICLE_SECTIONS:
                dropped += 1
                log.append(f"    - {section}: DROPPED unsourced item '{_primary_title(item)[:60]}'"
                           + (f" (url {url[:50]})" if url else " (no url)"))
                continue
            # Non-article sections: keep the item but never ship an unknown URL.
            if url:
                item["url"] = ""
            kept_unsourced += 1
            out.append(item)
        return out

    for section in _ALL_ITEM_SECTIONS:
        if isinstance(digest.get(section), list):
            digest[section] = _process(section, digest[section])
    _PP_STATS.update({"urls_repaired": repaired, "items_dropped_unsourced": dropped,
                      "unsourced_kept_nonarticle": kept_unsourced})
    if repaired or dropped:
        log.insert(0, f"    - urls: {repaired} repaired by headline, {dropped} unsourced item(s) deleted")
    return log


def _enforce_section_caps(digest: dict) -> list[str]:
    """Truncate any section over its maximum.

    Being over a cap is a counting mistake, not an editorial one, and the model
    cannot fix it more cheaply than a slice can. Run 116 spent a whole $0.80
    regeneration because it returned 7 op-eds against a cap of 6, then came
    back with the same length problem it started with. Under-cap still
    regenerates: too few items is a real content shortfall.
    """
    log = []
    for section, (_min_ct, max_ct) in SECTION_CAPS.items():
        items = digest.get(section)
        if isinstance(items, list) and len(items) > max_ct:
            log.append(f"    - {section}: trimmed {len(items)} -> {max_ct} (cap)")
            digest[section] = items[:max_ct]
    return log


def _trim_to_length(digest: dict) -> list[str]:
    """Cut tail items until the digest is inside the length target.

    The prompt asks for 1,500-1,900 words and the model reliably overshoots
    (run 116: 2,322 after a regeneration that was itself meant to fix length).
    Being over the ceiling was only an advisory, so nothing ever brought it
    down. Trimming here is deterministic, free, and follows the same rule the
    prompt states: cut from also_today and overnight first, never from
    top_stories or official_line.
    """
    log = []
    start = _count_words(digest)
    if start <= WORD_TARGET_HIGH:
        return log

    removed = 0
    for section, floor in _TRIM_ORDER:
        items = digest.get(section)
        if not isinstance(items, list):
            continue
        while len(items) > floor and _count_words(digest) > WORD_TARGET_HIGH:
            dropped = items.pop()
            removed += 1
            log.append(f"    - length: dropped from {section}: "
                       f"'{_primary_title(dropped)[:50]}'")
        if _count_words(digest) <= WORD_TARGET_HIGH:
            break

    end = _count_words(digest)
    if removed:
        log.insert(0, f"    - length: {start} -> {end} words "
                      f"({removed} tail item(s) cut to reach {WORD_TARGET_HIGH})")
    elif end > WORD_CEILING:
        log.append(f"    - length: {end} words, over the ceiling but the tail "
                   f"sections are already at their floors")
    _PP_STATS["words_before_trim"] = start
    _PP_STATS["items_trimmed_for_length"] = removed
    return log


def _dedupe_within(digest: dict) -> list[str]:
    """One topic = one entry. Same URL or a near-identical headline across sections."""
    log = []
    seen_urls: dict[str, str] = {}
    seen_sigs: list[tuple[str, set, str]] = []
    removed = 0

    # Statements ABOUT a story are not duplicates of it: official_line and
    # social_statements quote the same articles the top stories cite, on
    # purpose. They are deduplicated only against themselves.
    _QUOTE_SECTIONS = ("official_line", "social_statements")

    for section in _DEDUPE_ORDER:
        items = digest.get(section)
        if not isinstance(items, list):
            continue
        kept = []
        for item in items:
            if not isinstance(item, dict):
                continue
            url = _item_url(item)
            title = _primary_title(item)
            toks = _headline_tokens(title)
            dup_reason = None
            if section in _QUOTE_SECTIONS:
                q = _norm_title(item.get("statement") or item.get("quote_text") or "")
                for prev_sec, prev_toks, prev_title in seen_sigs:
                    if prev_sec == section and q and q == _norm_title(prev_title):
                        dup_reason = f"same quote already in {section}"
                        break
                if not dup_reason:
                    kept.append(item)
                    seen_sigs.append((section, set(),
                                      item.get("statement") or item.get("quote_text") or title))
                else:
                    removed += 1
                    log.append(f"    - {section}: removed '{title[:50]}' ({dup_reason})")
                continue
            if url and url in seen_urls:
                dup_reason = f"same URL as {seen_urls[url]}"
            elif len(toks) >= 4:
                for prev_sec, prev_toks, prev_title in seen_sigs:
                    if not prev_toks or prev_sec in _QUOTE_SECTIONS:
                        continue
                    overlap = len(toks & prev_toks) / min(len(toks), len(prev_toks))
                    if overlap >= 0.6 and (section != prev_sec or section in _ARTICLE_SECTIONS):
                        dup_reason = f"near-duplicate of {prev_sec}: '{prev_title[:40]}'"
                        break
            if dup_reason:
                removed += 1
                log.append(f"    - {section}: removed '{title[:50]}' ({dup_reason})")
                continue
            kept.append(item)
            if url:
                seen_urls.setdefault(url, section)
            seen_sigs.append((section, toks, title))
        digest[section] = kept
    _PP_STATS["duplicates_removed"] = removed
    return log


def _drop_hollow_items(digest: dict) -> list[str]:
    log = []
    n = 0
    for section in ("overnight_items", "also_today", "prc_government", "official_line",
                    "business_economy", "indo_pacific", "korea_china"):
        items = digest.get(section)
        if not isinstance(items, list):
            continue
        kept = []
        for item in items:
            text = " ".join(str(item.get(f, "")) for f in ("headline", "body", "body_text",
                                                             "detail", "statement", "context")
                            if isinstance(item, dict))
            body = " ".join(str(item.get(f, "")) for f in ("body", "body_text", "detail", "statement")
                            if isinstance(item, dict))
            if _HOLLOW_RE.search(text) and len(body.split()) < 45:
                n += 1
                log.append(f"    - {section}: dropped hollow item '{_primary_title(item)[:50]}'")
                continue
            kept.append(item)
        digest[section] = kept
    _PP_STATS["hollow_dropped"] = n
    return log


_MONTH_NUM = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


def _drop_stale_calendar(digest: dict, today) -> list[str]:
    log = []
    items = digest.get("calendar_watch")
    if not isinstance(items, list):
        return log
    kept = []
    for it in items:
        if not isinstance(it, dict):
            continue
        mon = str(it.get("month", "")).strip().lower()[:3]
        day = it.get("day")
        try:
            if mon in _MONTH_NUM and day:
                from datetime import date as _date
                year = today.year
                d = _date(year, _MONTH_NUM[mon], int(day))
                # A January entry seen in December is next year's.
                if d < today - timedelta(days=60):
                    d = _date(year + 1, _MONTH_NUM[mon], int(day))
                if d < today:
                    log.append(f"    - calendar_watch: dropped past date "
                               f"'{(it.get('headline') or '')[:50]}' ({mon.upper()} {day})")
                    continue
        except (ValueError, TypeError):
            pass
        kept.append(it)
    digest["calendar_watch"] = kept
    return log


_OTD_RE = re.compile(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})")


def _drop_offdate_on_this_day(digest: dict, today) -> list[str]:
    """on_this_day must match today's month and day; the model still reaches
    for famous anniversaries a week off."""
    log = []
    items = digest.get("on_this_day")
    if not isinstance(items, list):
        return log
    kept = []
    for it in items:
        m = _OTD_RE.search(str(it.get("date", "")) if isinstance(it, dict) else "")
        if m:
            mon = _MONTH_NUM.get(m.group(1).lower()[:3])
            if mon and (mon != today.month or int(m.group(2)) != today.day):
                log.append(f"    - on_this_day: dropped off-date entry '{it.get('date')}'")
                continue
        kept.append(it)
    digest["on_this_day"] = kept
    return log


_SOURCE_SUFFIX_RE = re.compile(r"\s*(\(direct\)|China|Asia|ZH\)|EN)\s*$", re.IGNORECASE)


def _normalize_source(src: str) -> str:
    s = (src or "").strip()
    s = re.sub(r"\s*\(.*?\)\s*", " ", s)
    s = _SOURCE_SUFFIX_RE.sub("", s).strip().lower()
    return s or (src or "").lower()


def _enforce_source_diversity(digest: dict, cap: int = 3) -> list[str]:
    """No outlet more than `cap` times across top_stories + overnight_items.
    Excess overnight items move to also_today when there is room."""
    log = []
    counts: dict[str, int] = {}
    for section in ("top_stories", "overnight_items"):
        items = digest.get(section)
        if not isinstance(items, list):
            continue
        kept = []
        for item in items:
            key = _normalize_source(item.get("source", "") if isinstance(item, dict) else "")
            counts[key] = counts.get(key, 0) + 1
            if key and counts[key] > cap and section == "overnight_items":
                also = digest.setdefault("also_today", [])
                if isinstance(also, list) and len(also) < SECTION_CAPS["also_today"][1]:
                    also.append({**item, "body_text": item.get("body_text") or item.get("body", ""),
                                 "category": item.get("category", "")})
                    log.append(f"    - source cap: moved '{_primary_title(item)[:40]}' "
                               f"({item.get('source')}) to also_today")
                else:
                    log.append(f"    - source cap: dropped '{_primary_title(item)[:40]}' "
                               f"({item.get('source')})")
                continue
            kept.append(item)
        digest[section] = kept
    return log


# ── Cross-day memory ─────────────────────────────────────────────────────────

def _load_ledger() -> list:
    try:
        data = json.loads(LEDGER_JSON.read_text(encoding="utf-8"))
        return data.get("entries", []) if isinstance(data, dict) else []
    except Exception:
        return []


def _ledger_recent(entries: list, today, window: int = _LEDGER_WINDOW_DAYS):
    """URLs, normalised titles and display headlines published in the window,
    excluding today's own entries so a same-day rerun is not starved."""
    cutoff = today - timedelta(days=window)
    urls, titles, headlines = set(), set(), []
    for e in entries:
        try:
            d = datetime.strptime(str(e.get("date", "")), "%Y-%m-%d").date()
        except Exception:
            continue
        if d < cutoff or d >= today:
            continue
        if e.get("url"):
            urls.add(e["url"])
        if e.get("title"):
            titles.add(e["title"])
        if e.get("headline"):
            headlines.append(f"{d.strftime('%b %-d')}: {e['headline']}")
    return urls, titles, headlines


def _dedupe_cross_day(digest: dict, prev_urls: set, prev_titles: set) -> list[str]:
    """Drop items already published in a recent edition (same URL or identical
    headline). Follow-up coverage with a new article still comes through."""
    log = []
    removed = 0
    for section in _ARTICLE_SECTIONS:
        items = digest.get(section)
        if not isinstance(items, list):
            continue
        kept = []
        for it in items:
            u, t = _item_url(it), _norm_title(_primary_title(it))
            if (u and u in prev_urls) or (t and t in prev_titles):
                removed += 1
                log.append(f"    - {section}: already published '{_primary_title(it)[:50]}'")
                continue
            kept.append(it)
        digest[section] = kept
    _PP_STATS["cross_day_removed"] = removed
    return log


def _record_ledger(digest: dict, today_iso: str) -> None:
    entries = _load_ledger()
    for section in _ARTICLE_SECTIONS:
        for it in (digest.get(section) or []):
            if not isinstance(it, dict):
                continue
            u, t = _item_url(it), _primary_title(it)
            if u or t:
                entries.append({"date": today_iso, "url": u, "title": _norm_title(t),
                                "headline": t[:120]})
    cutoff = datetime.strptime(today_iso, "%Y-%m-%d").date() - timedelta(days=_LEDGER_WINDOW_DAYS)
    pruned = []
    for e in entries:
        try:
            if datetime.strptime(str(e.get("date", "")), "%Y-%m-%d").date() >= cutoff:
                pruned.append(e)
        except Exception:
            continue
    LEDGER_JSON.write_text(json.dumps({"entries": pruned}, ensure_ascii=False, indent=1),
                           encoding="utf-8")
    print(f"   ✓ Published ledger updated ({len(pruned)} entries, last {_LEDGER_WINDOW_DAYS}d)")


def _postprocess_digest(digest: dict, payload: dict, prev_urls: set, prev_titles: set,
                        today) -> tuple[dict, list[str]]:
    _PP_STATS.clear()
    log = []
    if payload.get("market_indicators") and not digest.get("market_indicators"):
        digest["market_indicators"] = payload["market_indicators"]
    log += _strip_style(digest)
    log += _repair_and_gate_urls(digest, payload)
    log += _dedupe_cross_day(digest, prev_urls, prev_titles)
    log += _dedupe_within(digest)
    log += _drop_hollow_items(digest)
    log += _drop_stale_calendar(digest, today)
    log += _drop_offdate_on_this_day(digest, today)
    log += _enforce_source_diversity(digest)
    # Caps first (a slice), then length (drops tail items). Both run after the
    # filters above so they measure what will actually ship.
    log += _enforce_section_caps(digest)
    log += _trim_to_length(digest)
    digest["source_count"] = len({a.get("source") for a in _corpus(payload) if a.get("source")})
    return digest, log


# ─────────────────────────────────────────────────────────────────────────────
# LIVE URL CHECK (advisory)
# ─────────────────────────────────────────────────────────────────────────────

def _check_url(url: str, timeout: float = 5.0) -> tuple[str, bool, str]:
    """HEAD-check a URL. Only 404 and 410 count as dead: 403, 405, 429 and 451
    are normal for paywalled publishers and bot-protected servers."""
    import requests
    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True,
                             headers={"User-Agent": "Mozilla/5.0 CSIS-China-Brief-Validator/1.0"})
        if resp.status_code in (404, 410):
            return (url, False, f"HTTP {resp.status_code}")
        return (url, True, "")
    except Exception as e:                                   # noqa: BLE001
        return (url, False, type(e).__name__)


def _validate_urls(urls: list[str], limit: int = 40) -> list[tuple[str, str]]:
    broken = []
    urls = [u for u in urls if u.startswith("http") and "news.google.com" not in u][:limit]
    if not urls:
        return broken
    try:
        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = {pool.submit(_check_url, u): u for u in urls}
            for fut in as_completed(futures, timeout=40):
                url, ok, reason = fut.result()
                if not ok and reason.startswith("HTTP"):
                    broken.append((url, reason))
    except Exception:
        pass
    return broken


# ─────────────────────────────────────────────────────────────────────────────
# VALIDATION GATE
# ─────────────────────────────────────────────────────────────────────────────

PRESTIGE_NAMES = ("WSJ", "NYT", "WaPo", "Bloomberg", "FT", "Economist", "CNN", "Reuters",
                  "CNBC", "AP ", "AFP")


def validate_digest(digest: dict, payload: dict | None = None, today=None,
                    check_links: bool = True) -> list[str]:
    """Pre-send quality gate. Returns findings; anything containing CRITICAL blocks the send."""
    w: list[str] = []
    today = today or datetime.now(ET).date()

    for section, (min_ct, max_ct) in SECTION_CAPS.items():
        items = digest.get(section) or []
        label = section.upper().replace("_", " ")
        if min_ct and len(items) < min_ct:
            w.append(f"{label} CRITICAL: only {len(items)} (min {min_ct})")
        elif len(items) > max_ct:
            w.append(f"{label} CRITICAL: {len(items)} items (max {max_ct})")

    memo = digest.get("morning_memo") or []
    texts = [str(m).strip() for m in memo]
    if len(texts) >= 2 and len(set(texts)) < len(texts):
        w.append("MORNING MEMO CRITICAL: duplicate items, all 3 must be distinct")

    re_line = digest.get("re_line")
    if not re_line or len(str(re_line).strip()) < 10:
        w.append("RE: LINE CRITICAL: missing or too short")

    # The Bottom Line renders above everything and is the only thing many
    # readers read. It was generated but never rendered until Sep 4 2026, and it
    # has never been checked at all — so a blank or a one-line recap shipped
    # silently. It is now the one prose field with a gate of its own.
    note = str(digest.get("editor_note") or "").strip()
    n_words = len(note.split())
    if n_words < 25:
        w.append(f"BOTTOM LINE CRITICAL: editor_note is {n_words} words "
                 f"(needs 70-100; it renders above every section)")
    elif not (55 <= n_words <= 130):
        w.append(f"BOTTOM LINE: editor_note is {n_words} words (target 70-100)")
    if note and "watch:" not in note.lower():
        w.append("BOTTOM LINE: no 'Watch:' sentence naming what would confirm "
                 "or break the judgment")
    if note and re.match(r"^\s*(today|this morning)('s)?\s+(brief|digest|edition)",
                         note, re.IGNORECASE):
        w.append("BOTTOM LINE CRITICAL: editor_note opens with throat-clearing "
                 "instead of a judgment")

    word_count = _count_words(digest)
    if word_count < WORD_FLOOR_CRITICAL:
        w.append(f"WORD COUNT CRITICAL: ~{word_count} words (hard minimum {WORD_FLOOR_CRITICAL}, "
                 f"target {WORD_TARGET_LOW}-{WORD_TARGET_HIGH})")
    elif word_count < WORD_TARGET_LOW:
        w.append(f"WORD COUNT: ~{word_count} words (target {WORD_TARGET_LOW}-{WORD_TARGET_HIGH})")
    elif word_count > WORD_CEILING:
        w.append(f"WORD COUNT: ~{word_count} words, over the {WORD_CEILING} ceiling; "
                 f"cut also_today and overnight_items")

    dropped = _PP_STATS.get("items_dropped_unsourced", 0)
    if dropped >= 4:
        w.append(f"UNSOURCED CRITICAL: {dropped} items had URLs not in the input and were deleted; "
                 f"copy urls verbatim from the input data")
    elif dropped:
        w.append(f"UNSOURCED: {dropped} item(s) deleted for URLs not in the input")

    if len(digest.get("calendar_watch") or []) < 3:
        w.append("CALENDAR: fewer than 3 upcoming events after date filtering")

    digest_date = digest.get("digest_date", "")
    today_str = today.strftime("%A, %B %-d, %Y")
    if digest_date and digest_date != today_str:
        w.append(f"DATE MISMATCH CRITICAL: digest_date='{digest_date}' vs today='{today_str}'")
    for field in ("re_line", "digest_date"):
        if str(digest.get(field)).strip() == "None":
            w.append(f'NONE STRING: "{field}" contains literal "None"')

    seen_urls: dict[str, str] = {}
    bad_urls = thin = 0
    source_counts: dict[str, int] = {}
    for section in _ALL_ITEM_SECTIONS:
        for item in (digest.get(section) or []):
            if not isinstance(item, dict):
                continue
            url = _item_url(item)
            if url and (url == "#" or not url.startswith("http")):
                bad_urls += 1
            if url.startswith("http"):
                seen_urls.setdefault(url, section)
            body = (item.get("body") or item.get("body_text") or item.get("statement")
                    or item.get("detail") or item.get("summary") or "").strip()
            if section in _ARTICLE_SECTIONS and len(body) < 20:
                thin += 1
            if section in ("top_stories", "overnight_items", "also_today"):
                key = _normalize_source(item.get("source", ""))
                if key:
                    source_counts[key] = source_counts.get(key, 0) + 1
    if bad_urls:
        w.append(f"BAD URLS: {bad_urls} placeholder or invalid URL(s)")
    if thin:
        w.append(f"THIN BODIES: {thin} article item(s) with under 20 characters")
    for src, n in source_counts.items():
        if n > 7:
            w.append(f"SOURCE DIVERSITY: '{src}' appears {n} times across top sections")

    # Verbatim-quote check: a quote must appear in some collected summary.
    if payload:
        haystack = " ".join((a.get("summary") or "") + " " + (a.get("title") or "")
                            for a in _corpus(payload)).lower()
        haystack = re.sub(r"\s+", " ", haystack)
        unverifiable = 0
        for section, field in (("social_statements", "quote_text"), ("official_line", "statement")):
            for item in (digest.get(section) or []):
                q = str(item.get(field, "") if isinstance(item, dict) else "").strip().strip('"“”')
                if len(q) < 25:
                    continue
                probe = re.sub(r"\s+", " ", q.lower())[:60]
                if probe not in haystack and not (item.get("original_zh") and
                                                  str(item.get("original_zh"))[:20] in haystack):
                    unverifiable += 1
        if unverifiable:
            w.append(f"QUOTES: {unverifiable} quote(s) not found verbatim in collected text "
                     f"(translation or paraphrase); flagged for review")

    xd = digest.get("xinhua_delta")
    if not isinstance(xd, dict):
        w.append("XINHUA DELTA: missing (non-blocking)")

    if not (digest.get("korea_china") or []):
        w.append("KOREA: no China-Korea item today (empty is allowed; flagged so a "
                 "run of empty days is visible)")

    # Prestige coverage: name the dropped stories, not just the outlets.
    if payload:
        used = set(seen_urls)
        dropped_p = [a for a in (payload.get("tier1") or [])
                     if a.get("prestige_outlet") and a.get("url") and a["url"] not in used]
        if dropped_p:
            shown = "; ".join(f"{a.get('source', '?')}: {(a.get('title') or '')[:60]}"
                              for a in dropped_p[:5])
            more = f" (+{len(dropped_p) - 5} more)" if len(dropped_p) > 5 else ""
            w.append(f"PRESTIGE: {len(dropped_p)} collected but unused: {shown}{more}")

    if check_links and seen_urls:
        for url, reason in _validate_urls(list(seen_urls))[:5]:
            w.append(f"BROKEN URL ({reason}): {url[:80]} in {seen_urls.get(url, '?')}")

    return w


# ─────────────────────────────────────────────────────────────────────────────
# ARCHIVE, METRICS
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_WEB_URL = "https://andysaulim.github.io/Daily-China-Digest"


def _web_base() -> str:
    return (os.environ.get("WEB_URL") or DEFAULT_WEB_URL).rstrip("/")


def _build_archive_index(archive: list) -> str:
    """public/archive.html: every issue, newest first, with word count and links."""
    from html import escape
    rows = []
    for a in archive:
        d = a.get("date", "")
        try:
            label = datetime.strptime(d, "%Y-%m-%d").strftime("%A, %B %-d, %Y")
        except ValueError:
            label = d
        re_line = escape(str(a.get("re_line") or ""))
        wc = a.get("word_count") or ""
        pdf = f' &middot; <a href="{d}.pdf" style="color:#2980B9;text-decoration:none;">PDF</a>' if a.get("pdf") else ""
        rows.append(
            f'<tr><td style="padding:10px 8px;border-bottom:1px solid #EBEBEB;white-space:nowrap;'
            f'font-family:Arial,sans-serif;font-size:13px;color:#1B2A4A;font-weight:700;">'
            f'<a href="{d}.html" style="color:#1B2A4A;text-decoration:none;">{label}</a>{pdf}</td>'
            f'<td style="padding:10px 8px;border-bottom:1px solid #EBEBEB;font-family:Georgia,serif;'
            f'font-size:13px;color:#444;">{re_line}</td>'
            f'<td style="padding:10px 8px;border-bottom:1px solid #EBEBEB;font-family:Arial,sans-serif;'
            f'font-size:11px;color:#888;text-align:right;white-space:nowrap;">{wc} words</td></tr>')
    body = "\n".join(rows) or '<tr><td style="padding:12px;">No issues archived yet.</td></tr>'
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>China Daily Brief · Archive</title></head>
<body style="margin:0;background:#F4F4F1;">
<div style="max-width:760px;margin:0 auto;background:#fff;">
<div style="background:#1B2A4A;color:#fff;padding:18px 32px 14px;">
<div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:2px;color:#D4AC0D;font-family:Arial,sans-serif;margin-bottom:6px;">CSIS Korea Chair</div>
<h1 style="margin:0 0 4px 0;font-size:28px;font-weight:700;font-family:Georgia,serif;">China Daily Brief</h1>
<div style="font-size:14px;color:rgba(255,255,255,0.85);font-family:Georgia,serif;">Archive &middot; {len(archive)} issues &middot; <a href="index.html" style="color:#D4AC0D;text-decoration:none;">Latest issue &#8594;</a></div>
</div>
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="padding:8px 24px 24px;">{body}</table>
<div style="padding:16px 32px;font-size:10px;color:#888;font-family:Arial,sans-serif;text-align:center;">Generated automatically; every item links to its source. Prepared by Andy Lim, CSIS Korea Chair.</div>
</div></body></html>"""


def _archive_html(html: str, digest: dict, date_str: str) -> None:
    PUBLIC_DIR.mkdir(exist_ok=True)
    (PUBLIC_DIR / f"{date_str}.html").write_text(html, encoding="utf-8")
    (PUBLIC_DIR / "index.html").write_text(html, encoding="utf-8")
    archive_index = PUBLIC_DIR / "archive.json"
    archive = []
    if archive_index.exists():
        try:
            archive = json.loads(archive_index.read_text())
        except json.JSONDecodeError:
            archive = []

    pdf_ok = False
    try:
        from pdf_export import export_pdf
        pdf_ok = export_pdf(PUBLIC_DIR / f"{date_str}.html") is not None
    except Exception as e:                                   # noqa: BLE001
        print(f"   ⚠ PDF export unavailable: {e}")

    entry = {
        "date": date_str,
        "filename": f"{date_str}.html",
        "re_line": digest.get("re_line", ""),
        "top_stories": len(digest.get("top_stories") or []),
        "overnight_items": len(digest.get("overnight_items") or []),
        "word_count": _count_words(digest),
        "sources": digest.get("source_count"),
        "pdf": pdf_ok,
    }
    archive = [a for a in archive if a.get("date") != date_str]
    archive.insert(0, entry)
    archive = archive[:400]
    archive_index.write_text(json.dumps(archive, indent=2))
    (PUBLIC_DIR / "archive.html").write_text(_build_archive_index(archive), encoding="utf-8")
    print(f"📁 Archived to {date_str}.html (+ archive.html, {len(archive)} issues)")


def _write_metrics(record: dict) -> None:
    try:
        with METRICS_JSONL.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"⚠ metrics.jsonl not written: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

def run_pipeline(args: argparse.Namespace) -> int:
    now = datetime.now(ET)
    today = now.date()
    today_iso = today.isoformat()
    print(f"\n{'=' * 64}")
    print(f"  CHINA DAILY BRIEF — {now.strftime('%A, %B %-d, %Y at %I:%M %p ET')}")
    print(f"{'=' * 64}\n")
    pipeline_start = time.time()
    test_mode = bool(args.send_to)
    metrics: dict = {"date": today_iso, "started": now.isoformat(), "test_mode": test_mode}

    # ─── Collect ─────────────────────────────────────────────────────────
    if args.from_cache and COLLECTED_JSON.exists():
        print("📂 Loading cached collection from disk...")
        payload = json.loads(COLLECTED_JSON.read_text(encoding="utf-8"))
    else:
        print("🌐 Collecting from RSS feeds...")
        from collect import collect_all
        payload = collect_all()
        COLLECTED_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    corpus = _corpus(payload)
    unique_sources = {a.get("source") for a in corpus if a.get("source")}
    print(f"   • {len(corpus)} articles from {len(unique_sources)} unique sources")
    metrics["articles"] = len(corpus)
    metrics["sources"] = len(unique_sources)

    # ─── Resolve Google News redirects, fetch article text ───────────────
    print("\n🔗 Canonicalising Google News URLs...")
    try:
        from resolve import resolve_payload
        payload = resolve_payload(payload)
    except Exception as e:                                   # noqa: BLE001
        print(f"   ⚠ URL resolution failed (non-fatal): {e}")
    metrics["resolve"] = payload.get("resolve_stats")

    print("\n📄 Fetching article text...")
    try:
        from fulltext import enrich_payload
        payload = enrich_payload(payload)
    except Exception as e:                                   # noqa: BLE001
        print(f"   ⚠ Full-text enrichment failed (non-fatal): {e}")
    metrics["fulltext"] = payload.get("fulltext_stats")

    # ─── Cross-day memory ────────────────────────────────────────────────
    prev_urls, prev_titles, prev_headlines = _ledger_recent(_load_ledger(), today)
    payload["recent_coverage"] = prev_headlines
    for a in corpus:
        if (a.get("url") in prev_urls) or (_norm_title(a.get("title", "")) in prev_titles):
            a["seen_before"] = True
    if prev_headlines:
        print(f"\n🧠 Cross-day memory: {len(prev_headlines)} headlines from the last "
              f"{_LEDGER_WINDOW_DAYS} days")

    COLLECTED_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.dry_run:
        print(f"\n✅ Dry run complete. Cached to {COLLECTED_JSON.name}")
        _write_metrics({**metrics, "dry_run": True})
        return 0

    # ─── Database context ────────────────────────────────────────────────
    db_context = ""
    try:
        from databases import build_db_context
        db_context = build_db_context()
    except Exception as e:                                   # noqa: BLE001
        print(f"⚠ Database context unavailable: {e}")

    # ─── Generate → post-process → validate (retry with feedback) ────────
    print("\n🤖 Generating digest...")
    from digest import generate_digest, regenerate_digest, TOKEN_LEDGER, run_cost
    digest = generate_digest(payload, db_context=db_context)
    digest, pp_log = _postprocess_digest(digest, payload, prev_urls, prev_titles, today)
    for line in pp_log:
        print(line)
    DIGEST_JSON.write_text(json.dumps(digest, ensure_ascii=False, indent=2), encoding="utf-8")

    validation_passed = False
    findings: list[str] = []
    attempts = 0
    for attempt in range(1 + MAX_VALIDATION_RETRIES):
        attempts = attempt + 1
        print(f"\n🔍 Validating digest (attempt {attempts}/{1 + MAX_VALIDATION_RETRIES})...")
        findings = validate_digest(digest, payload=payload, today=today,
                                   check_links=not args.no_link_check)
        critical = [f for f in findings if "CRITICAL" in f]
        advisory = [f for f in findings if f not in critical]
        if not critical:
            print("   ✓ Validation passed" + (" with advisories:" if advisory else ""))
            for f in advisory:
                print(f"     - {f}")
            validation_passed = True
            break
        print("   ✖ BLOCKING:")
        for f in critical:
            print(f"     - {f}")
        if advisory:
            print("   ⚠ also, not blocking:")
            for f in advisory:
                print(f"     - {f}")
        if attempt < MAX_VALIDATION_RETRIES:
            try:
                digest = regenerate_digest(payload, digest, critical, attempt=attempt,
                                           db_context=db_context)
            except Exception as e:                           # noqa: BLE001
                print(f"   ⚠ Regeneration failed: {e}")
                break
            digest, pp_log = _postprocess_digest(digest, payload, prev_urls, prev_titles, today)
            for line in pp_log:
                print(line)
            DIGEST_JSON.write_text(json.dumps(digest, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
        else:
            print("\n   ✖ CRITICAL findings after all retries. The brief will NOT be sent.")
            print("     HTML is still rendered for review (digest.html).")

    metrics.update({
        "validation_attempts": attempts,
        "validation_passed": validation_passed,
        "critical": [f for f in findings if "CRITICAL" in f],
        "advisory_count": len([f for f in findings if "CRITICAL" not in f]),
        "postprocess": dict(_PP_STATS),
        "word_count": _count_words(digest),
        "sections": {k: len(digest.get(k) or []) for k in SECTION_CAPS},
        "tokens": list(TOKEN_LEDGER),
        "cost_usd": run_cost(),
    })

    # ─── Health checks (never block) ─────────────────────────────────────
    print("\n🩺 Health checks...")
    try:
        import pipeline_health
        report = pipeline_health.check(payload, digest)
        pipeline_health.print_report(report)
        metrics["health"] = report
    except Exception as e:                                   # noqa: BLE001
        print(f"   ⚠ Health check failed: {e}")

    # ─── Trackers: only after validation, never on a test send ───────────
    if validation_passed and not args.no_track and not test_mode:
        # bp_tracker persisted monitored_locations, a section that no longer
        # exists. Left on disk in case the satellite watch ever returns.
        for name, mod in (("Xi", "xi_tracker"), ("Xinhua", "xinhua_tracker")):
            try:
                module = __import__(mod)
                module.update_from_digest(digest)
            except Exception as e:                           # noqa: BLE001
                print(f"⚠ {name} tracker update failed (non-fatal): {e}")

    # ─── Render ──────────────────────────────────────────────────────────
    print("\n🎨 Rendering HTML email...")
    from render import render_html
    base = _web_base()
    digest["web_url"] = f"{base}/{today_iso}.html"
    digest["pdf_url"] = f"{base}/{today_iso}.pdf"
    digest["archive_url"] = f"{base}/archive.html"
    html = render_html(digest)
    DIGEST_HTML.write_text(html, encoding="utf-8")
    html_bytes = len(html.encode("utf-8"))
    print(f"   • Wrote {html_bytes:,} bytes to {DIGEST_HTML.name} "
          f"({100 * html_bytes / GMAIL_CLIP_BYTES:.0f}% of Gmail's clipping limit)")
    metrics["html_bytes"] = html_bytes

    size_findings = check_email_size(html)
    for f in size_findings:
        print(f"   {'✖' if 'CRITICAL' in f else '⚠'} {f}")
    if any("CRITICAL" in f for f in size_findings):
        # A clipped brief is a broken brief, so this blocks the send exactly as
        # a validation failure does. The rendered HTML is still on disk.
        validation_passed = False
        findings += size_findings
    metrics["size_findings"] = size_findings

    # ─── Archive + README (real, validated runs only) ────────────────────
    archived = False
    if validation_passed and not args.no_archive and not test_mode:
        _archive_html(html, digest, today_iso)
        archived = True
        try:
            from update_readme import update_readme
            update_readme(metrics)
        except Exception as e:                               # noqa: BLE001
            print(f"⚠ README update failed (non-fatal): {e}")

    # ─── Send (fail-closed) ──────────────────────────────────────────────
    sent = False
    exit_code = 0
    if args.no_send:
        print("\n📭 --no-send: skipping email send.")
    elif not validation_passed and not args.force_send:
        print("\n⛔ Send BLOCKED by validation. Use --force-send to override.")
        exit_code = 2
    else:
        from send_email import send_digest
        recipients = None
        subject = None
        if test_mode:
            recipients = [r.strip() for r in args.send_to.split(",") if r.strip()]
            subject = (f"China Daily Brief — {now.strftime('%a %b %-d %Y')} (test run)")
            print(f"\n📧 Test send to {', '.join(recipients)}...")
        else:
            print("\n📧 Sending email...")
        sent = send_digest(html, subject=subject, recipients=recipients)
        if sent and not test_mode:
            _record_ledger(digest, today_iso)
            LAST_SENT_TXT.write_text(today_iso + "\n", encoding="utf-8")
        elif not sent:
            print("   ❌ Send failed; the run is marked failed so the alert and the next "
                  "catch-up cron can act.")
            exit_code = 3

    elapsed = time.time() - pipeline_start
    metrics.update({"sent": sent, "archived": archived, "seconds": round(elapsed),
                    "exit_code": exit_code})
    _write_metrics(metrics)
    print(f"\n{'=' * 64}")
    status = "✅ Pipeline complete" if exit_code == 0 else f"⚠ Pipeline finished with exit code {exit_code}"
    print(f"  {status} in {elapsed:.0f}s — est. cost ${run_cost():.2f}")
    print(f"{'=' * 64}\n")
    return exit_code


def main():
    parser = argparse.ArgumentParser(description="China Daily Brief — orchestration entry point")
    parser.add_argument("--dry-run", action="store_true", help="Collect + resolve + enrich only")
    parser.add_argument("--from-cache", action="store_true", help="Reuse cached collected.json")
    parser.add_argument("--no-send", action="store_true", help="Generate HTML but don't email")
    parser.add_argument("--no-archive", action="store_true", help="Skip writing to public/")
    parser.add_argument("--no-track", action="store_true", help="Do not update tracker JSON")
    parser.add_argument("--no-link-check", action="store_true", help="Skip live URL HEAD checks")
    parser.add_argument("--force-send", action="store_true",
                        help="Send even if validation has CRITICAL findings")
    parser.add_argument("--send-to", default="",
                        help="Test run: email only these comma-separated addresses; no archive, "
                             "ledger, marker or tracker writes")
    args = parser.parse_args()
    try:
        return run_pipeline(args)
    except KeyboardInterrupt:
        print("\n\n⚠ Interrupted by user")
        return 130
    except Exception as e:                                   # noqa: BLE001
        print(f"\n❌ Pipeline failed: {e}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
