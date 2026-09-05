"""
Best-effort article body fetcher.

Ported from the Australia-Pacific brief. The problem it solves is the same
here: Google News search feeds carry a title and almost nothing else, so the
model was writing two- and three-sentence bodies from a headline. That is the
worst possible setup for SOURCE-OR-SKIP, because every specific the reader
wants (a figure, a named official, a dated commitment, a quote) has to come
from somewhere, and a headline does not carry it.

Fetching the real article text gives the model grounded material. It cannot
make the brief less accurate: the model may still only use what is in front of
it, and this puts more real text in front of it, not less.

Design notes carried over:
  - Fetch ONLY canonical URLs. A Google News redirect returns an interstitial.
    Run resolve.py first.
  - Paywalled outlets still contribute: the <meta>/og:description sits before
    the wall, so WSJ, NYT, FT, Bloomberg and the Economist each give a sentence
    of real detail even though the body is unreachable.
  - Fetch in parallel, with a short timeout, and never fail the run.

Enriched summaries are stored in collected.json, so --from-cache reruns reuse
them. Disable with FULLTEXT=0. Stdlib only.
"""
import concurrent.futures as cf
import os
import re
import urllib.request

ENABLED = os.environ.get("FULLTEXT", "1") not in ("0", "false", "False", "")

MAX_ITEMS = int(os.environ.get("FULLTEXT_MAX_ITEMS", "160"))
WORKERS = 8
BODY_CHARS = 2200
TIMEOUT = 6

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
       "Accept": "text/html,application/xhtml+xml"}

# Bodies sit behind a wall, so take the meta description and stop.
PAYWALLED = (
    "wsj.com", "nytimes.com", "ft.com", "economist.com", "bloomberg.com",
    "washingtonpost.com", "telegraph.co.uk", "thetimes.co.uk", "caixinglobal.com",
    "asia.nikkei.com", "foreignaffairs.com", "sinocism.com", "scmp.com",
)

_PRESTIGE_HINTS = (
    "WSJ", "NYT", "WaPo", "FT", "Reuters", "Bloomberg", "AP ", "AFP", "Economist",
    "CNN", "CNBC", "CSIS", "Sinocism", "Nikkei",
)

_SCRIPT_RE = re.compile(r"<(script|style|noscript|svg)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_REGION_RE = re.compile(r"<(article|main)[^>]*>(.*?)</\1>", re.DOTALL | re.IGNORECASE)
_P_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.DOTALL | re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_META_A = re.compile(
    r'<meta[^>]+?(?:name|property)=["\'](?:og:)?description["\'][^>]+?content=["\']([^"\']+)["\']',
    re.IGNORECASE)
_META_B = re.compile(
    r'<meta[^>]+?content=["\']([^"\']+)["\'][^>]+?(?:name|property)=["\'](?:og:)?description["\']',
    re.IGNORECASE)
_ENTITY_MAP = {"&amp;": "&", "&quot;": '"', "&#39;": "'", "&apos;": "'",
               "&lt;": "<", "&gt;": ">", "&nbsp;": " ", "&#8217;": "'",
               "&#8216;": "'", "&#8220;": '"', "&#8221;": '"'}


def _clean(text: str) -> str:
    text = text or ""
    for k, v in _ENTITY_MAP.items():
        text = text.replace(k, v)
    return re.sub(r"\s+", " ", text).strip()


def is_gnews(url: str) -> bool:
    return "news.google.com" in (url or "").lower()


def _is_paywalled(url: str) -> bool:
    u = (url or "").lower()
    return any(p in u for p in PAYWALLED)


def extract_meta(html: str) -> str:
    for rx in (_META_A, _META_B):
        m = rx.search(html or "")
        if m:
            return _clean(m.group(1))
    return ""


def extract_body(html: str) -> str:
    """Readable paragraph text from an article page, best-effort."""
    if not html:
        return ""
    html = _SCRIPT_RE.sub(" ", html)
    m = _REGION_RE.search(html)
    region = m.group(2) if m else html
    paras = [_clean(_TAG_RE.sub(" ", pm.group(1))) for pm in _P_RE.finditer(region)]
    # The 40-character floor drops nav links, bylines and share prompts.
    return " ".join(p for p in paras if len(p) >= 40)[:BODY_CHARS].strip()


def extract(html: str, want_body: bool = True) -> str:
    desc = extract_meta(html)
    body = extract_body(html) if want_body else ""
    combined = f"{desc} {body}".strip() if desc else body
    return combined[:BODY_CHARS].strip()


def _fetch(url: str, want_body: bool, timeout: int = TIMEOUT) -> str:
    try:
        req = urllib.request.Request(url, headers=_UA)
        raw = urllib.request.urlopen(req, timeout=timeout).read(600_000)
        return extract(raw.decode("utf-8", "ignore"), want_body)
    except Exception:                                       # noqa: BLE001
        return ""


def _is_prestige(item: dict) -> bool:
    if item.get("prestige_outlet"):
        return True
    src = item.get("source", "") or ""
    return any(h in src for h in _PRESTIGE_HINTS)


def _rank(item: dict):
    # Prestige first, then the items carrying the least text.
    return (_is_prestige(item), bool(item.get("flagged_journalist")),
            -len(item.get("summary") or ""))


def _apply(item: dict, body: str) -> None:
    base = item.get("summary") or ""
    # Do not duplicate a meta description that the feed already carried.
    if base and body.startswith(base[:80]):
        merged = body
    else:
        merged = f"{base} {body}".strip() if base else body
    item["summary"] = merged[:2400]
    item["fulltext"] = True


def enrich(items: list, limit: int = MAX_ITEMS) -> dict:
    """Append fetched article text to each item's `summary`, in place."""
    stats = {"considered": 0, "fetched": 0, "enriched": 0, "gnews_skipped": 0}
    if not ENABLED:
        print("  [fulltext] disabled (FULLTEXT=0)")
        return stats

    seen = set()
    cands = []
    for it in items:
        u = it.get("url") or ""
        if not u or is_gnews(u):
            stats["gnews_skipped"] += 1
            continue
        if it.get("fulltext"):
            continue        # already enriched (from-cache rerun)
        if u in seen:
            continue
        seen.add(u)
        cands.append(it)
    cands.sort(key=_rank, reverse=True)
    cands = cands[:limit]
    stats["considered"] = len(cands)

    fetched: dict[str, str] = {}
    if cands:
        with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futs = {ex.submit(_fetch, it["url"], not _is_paywalled(it["url"])): it
                    for it in cands}
            for fut in cf.as_completed(futs):
                url = futs[fut]["url"]
                try:
                    fetched[url] = fut.result() or ""
                except Exception:                           # noqa: BLE001
                    fetched[url] = ""
    stats["fetched"] = len(fetched)
    # Apply to every item sharing that URL (the same story can sit in two lists).
    for it in items:
        body = fetched.get(it.get("url") or "", "")
        if body and not it.get("fulltext"):
            _apply(it, body)
            stats["enriched"] += 1

    print(f"  [fulltext] {stats['considered']} canonical items fetched, "
          f"{stats['enriched']} enriched, {stats['gnews_skipped']} unresolved skipped")
    return stats


def enrich_payload(payload: dict) -> dict:
    """Enrich every article list in a collected payload."""
    if not ENABLED:
        print("  [fulltext] disabled (FULLTEXT=0)")
        return payload
    pool = []
    for key in ("tier1", "tier2", "tier3", "tier4",
                "xi_tracker_articles", "hidden_reach_articles", "gray_zone_articles"):
        pool.extend(payload.get(key) or [])
    payload["fulltext_stats"] = enrich(pool)
    return payload


if __name__ == "__main__":
    html = (
        '<html><head>'
        '<meta property="og:description" content="Beijing tied the next tranche of '
        'chip subsidies to fab milestones, the ministry said.">'
        '</head><body><nav><p>Home</p></nav>'
        '<article>'
        '<p>China will release the next tranche of semiconductor subsidies only '
        'once SMIC reaches an agreed milestone, the ministry said on Tuesday.</p>'
        '<p>Short.</p>'
        '<p>A second substantial paragraph carrying more than forty characters of real '
        'text, so the extractor keeps it as body content rather than navigation.</p>'
        '</article></body></html>'
    )
    assert extract_meta(html).startswith("Beijing tied"), extract_meta(html)
    body = extract_body(html)
    assert "China will release" in body, body
    assert "Home" not in body and "Short." not in body, body
    both = extract(html, want_body=True)
    assert both.startswith("Beijing tied") and "China will release" in both
    meta_only = extract(html, want_body=False)
    assert "Beijing tied" in meta_only and "second substantial" not in meta_only
    assert is_gnews("https://news.google.com/rss/search?q=x")
    assert _is_paywalled("https://www.wsj.com/world/china/x")
    print("fulltext.py self-test passed")
