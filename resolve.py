"""
Google News URL canonicalizer.

Ported from the Australia-Pacific brief (which ported it from the Middle East
pipeline). Google News RSS links are opaque redirect blobs of ~280 characters:
    https://news.google.com/rss/articles/CBMivgFBVV95cUxN...?oc=5

Why this exists for the China brief specifically: the run logs from June 15 and
August 17 both read "0/303 resolved" and "0/251 resolved". The old resolver in
run.py followed HTTP redirects, but Google serves a JavaScript interstitial for
these links, so the final URL never left news.google.com. Roughly 77 percent of
the corpus therefore reached the model as a 280-character string it cannot copy
verbatim, and the sanitiser then blanked every URL it could not match. The June
issues carried links to SCMP and three static CSIS pages and nothing else.

Two decode paths, tried in order, both best-effort:
  A. Base64 path, for older article IDs that embed the target URL directly.
  B. Batch API path, for newer IDs: fetch the article page for its signature and
     timestamp, then ask Google's batchexecute endpoint to resolve the ID.

Every failure keeps the original Google News URL, which still opens in a
browser, so resolution can only improve the brief. Resolved URLs are cached in
url_cache.json (committed by the workflow) so catch-up reruns cost nothing.

Stdlib only. Disable with RESOLVE_URLS=0.
"""

import base64
import json
import os
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

CACHE_PATH = Path(__file__).parent / "url_cache.json"
CACHE_MAX_ENTRIES = 4000

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) "
                     "Chrome/120.0 Safari/537.36"}
_BATCH_URL = "https://news.google.com/_/DotsSplashUi/data/batchexecute"

ENABLED = os.environ.get("RESOLVE_URLS", "1") not in ("0", "false", "False", "")
TIME_BUDGET_S = float(os.environ.get("RESOLVE_TIME_BUDGET", "240"))
WORKERS = int(os.environ.get("RESOLVE_WORKERS", "4"))   # polite to Google
PAUSE_S = 0.15

_ARTICLE_ID_RE = re.compile(r"/articles/([^/?]+)")
_SG_RE = re.compile(r'data-n-a-sg="([^"]+)"')
_TS_RE = re.compile(r'data-n-a-ts="([^"]+)"')
_HTTP_RE = re.compile(rb"https?://[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+")


def is_gnews(url: str) -> bool:
    return "news.google.com" in (url or "")


def _article_id(url: str):
    m = _ARTICLE_ID_RE.search(url or "")
    return m.group(1) if m else None


def _get(url: str, timeout: int = 15) -> bytes:
    req = urllib.request.Request(url, headers=_UA)
    return urllib.request.urlopen(req, timeout=timeout).read()


def _decode_base64(article_id: str):
    """Older format: the target URL is embedded in the base64 article ID."""
    try:
        raw = base64.urlsafe_b64decode(article_id + "==")
    except Exception:
        return None
    m = _HTTP_RE.search(raw)
    if not m:
        return None
    url = m.group(0).decode("latin-1", "ignore")
    url = re.split(r"[\x00-\x1f]", url)[0]
    if url.startswith("http") and "news.google.com" not in url:
        return url
    return None


def _decode_api(article_id: str):
    """Newer format: fetch the article page for its signature + timestamp, then
    ask Google's batchexecute endpoint to resolve the ID to the publisher URL."""
    try:
        html = _get(f"https://news.google.com/rss/articles/{article_id}").decode(
            "utf-8", "ignore")
    except Exception:
        return None
    sg, ts = _SG_RE.search(html), _TS_RE.search(html)
    if not (sg and ts):
        return None
    inner = json.dumps([
        "garturlreq",
        [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1,
          None, None, None, None, None, 0, 1],
         "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0],
        article_id, int(ts.group(1)), sg.group(1),
    ])
    freq = json.dumps([[["Fbv4je", inner, None, "generic"]]])
    data = urllib.parse.urlencode({"f.req": freq}).encode()
    try:
        req = urllib.request.Request(
            _BATCH_URL, data=data,
            headers={**_UA,
                     "content-type": "application/x-www-form-urlencoded;charset=UTF-8"})
        resp = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "ignore")
        # Response is ")]}'\n\n<json>"; the payload we want is the second block.
        blocks = resp.split("\n\n")
        arr = json.loads(blocks[1] if len(blocks) > 1 else resp)
        url = json.loads(arr[0][2])[1]
        if url and url.startswith("http") and not is_gnews(url):
            return url
    except Exception:
        return None
    return None


def resolve_url(article_id_or_url: str):
    """Resolve one Google News URL (or bare article id). Returns a canonical URL or None."""
    aid = article_id_or_url if "/" not in (article_id_or_url or "") \
        else _article_id(article_id_or_url)
    if not aid:
        return None
    return _decode_base64(aid) or _decode_api(aid)


# ── cache ────────────────────────────────────────────────────────────────────

def _load_cache() -> dict:
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_cache(cache: dict) -> None:
    # Keep the newest entries: dict preserves insertion order.
    if len(cache) > CACHE_MAX_ENTRIES:
        keys = list(cache.keys())[-CACHE_MAX_ENTRIES:]
        cache = {k: cache[k] for k in keys}
    try:
        CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=0),
                              encoding="utf-8")
    except Exception as e:
        print(f"  ! url_cache.json not written: {e}")


# ── batch resolution ─────────────────────────────────────────────────────────

def resolve_items(items: list, label: str = "") -> dict:
    """Rewrite each item's `url` to its canonical publisher URL where possible.

    Items are processed in list order, so callers should put the most valuable
    items first (prestige outlets, tier 1) in case the time budget runs out.
    Keeps the original under `gnews_url`. Returns a stats dict.
    """
    stats = {"resolved": 0, "cached": 0, "failed": 0, "skipped": 0, "budget_hit": 0}
    if not ENABLED:
        print("  [resolve] disabled (RESOLVE_URLS=0)")
        return stats

    cache = _load_cache()
    todo = []
    for it in items:
        url = it.get("url") or ""
        if not is_gnews(url):
            stats["skipped"] += 1
            continue
        if url in cache and cache[url]:
            it["gnews_url"], it["url"] = url, cache[url]
            stats["cached"] += 1
            continue
        todo.append(it)

    # Dedupe by URL so the same link seen in two feeds costs one lookup.
    by_url: dict[str, list] = {}
    for it in todo:
        by_url.setdefault(it["url"], []).append(it)

    start = time.monotonic()
    pending = list(by_url.keys())

    def _work(u):
        if time.monotonic() - start > TIME_BUDGET_S:
            return u, None, True
        out = resolve_url(u)
        time.sleep(PAUSE_S)
        return u, out, False

    if pending:
        with ThreadPoolExecutor(max_workers=max(1, WORKERS)) as pool:
            futures = [pool.submit(_work, u) for u in pending]
            for fut in as_completed(futures):
                try:
                    u, canonical, over_budget = fut.result()
                except Exception:
                    continue
                if over_budget:
                    stats["budget_hit"] += 1
                    continue
                if canonical:
                    cache[u] = canonical
                    for it in by_url[u]:
                        it["gnews_url"], it["url"] = u, canonical
                    stats["resolved"] += len(by_url[u])
                else:
                    stats["failed"] += len(by_url[u])

    if stats["resolved"]:
        _save_cache(cache)

    took = time.monotonic() - start
    tag = f" {label}" if label else ""
    print(f"  [resolve{tag}] {stats['resolved']} resolved + {stats['cached']} cached, "
          f"{stats['failed']} kept as redirect, {stats['budget_hit']} over budget, "
          f"{stats['skipped']} already direct ({took:.0f}s)")
    return stats


def _priority(a: dict) -> int:
    score = 0
    if a.get("prestige_outlet"):
        score += 100
    if a.get("flagged_journalist"):
        score += 40
    if a.get("prestige_tier") == "A" or a.get("journal_tier") in ("A+", "A"):
        score += 30
    return -score


def resolve_payload(payload: dict) -> dict:
    """Resolve Google News URLs across every article list in a collected payload."""
    pool = []
    for key in ("tier1", "tier2", "tier3", "tier4",
                "xi_tracker_articles", "hidden_reach_articles", "gray_zone_articles"):
        pool.extend(payload.get(key) or [])
    pool.sort(key=_priority)          # stable: prestige first, then feed order
    stats = resolve_items(pool)
    total_gnews = stats["resolved"] + stats["cached"] + stats["failed"] + stats["budget_hit"]
    payload["resolve_stats"] = {**stats, "gnews_total": total_gnews}
    return payload


# ── self-test (offline: base64 path + id parsing only) ───────────────────────
if __name__ == "__main__":
    embedded = "https://www.reuters.com/world/china/example-story-2026-09-04/"
    payload = b"\x08\x13\x22" + bytes([len(embedded)]) + embedded.encode() + b"\xd2\x01\x00"
    fake_id = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    assert _decode_base64(fake_id) == embedded, _decode_base64(fake_id)
    fake_url = f"https://news.google.com/rss/articles/{fake_id}?oc=5"
    assert _article_id(fake_url) == fake_id
    assert is_gnews(fake_url) and not is_gnews(embedded)
    assert _decode_base64("CBMiAU_yqLNfakenewformatid") is None
    print("resolve.py self-test passed (base64 path)")
