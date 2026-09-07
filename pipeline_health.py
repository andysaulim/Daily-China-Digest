"""
Pipeline health checks.

Runs after every digest (and can be run alone) to catch the failures that do
not announce themselves: a retired model ID, a feed list that has quietly
shrunk to a handful of sources, Google News resolution collapsing to zero,
baselines nobody has verified in months. Each of those happened to this
pipeline between May and August 2026 and none produced an alert.

Returns {"warnings": [...], "alerts": [...]}. Alerts are the ones an operator
should act on this week; the run log prints both and metrics.jsonl keeps them.
Never raises and never blocks a send: that is the validator's job.
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).parent

# Model IDs the pipeline may pin. Update when Anthropic ships a new generation;
# a FAST_MODEL / PRIMARY_MODEL outside this set means the next retirement is
# already on the calendar and nothing else in the code will notice until the
# send fails (June 15, 2026, for both the Korea and China briefs).
KNOWN_MODEL_IDS = {
    "claude-opus-5", "claude-sonnet-5", "claude-fable-5", "claude-fable-5-1",
    "claude-opus-4-8", "claude-opus-4-7", "claude-opus-4-6",
    "claude-sonnet-4-6", "claude-haiku-4-5",
}

TIER_FLOORS = {"tier1": 40, "tier2": 2, "tier4": 8}
RESOLVE_ALERT_BELOW = 0.5        # share of Google News URLs canonicalised
FULLTEXT_WARN_BELOW = 20         # enriched items per run
BASELINE_WARN_DAYS = 60
BASELINE_ALERT_DAYS = 120
SEND_GAP_ALERT_DAYS = 2


def check(payload: dict | None = None, digest: dict | None = None) -> dict:
    warnings: list[str] = []
    alerts: list[str] = []

    # ── Model pins ──────────────────────────────────────────────────────
    try:
        import digest as _d
        for label, mid in (("FAST_MODEL", _d.FAST_MODEL), ("PRIMARY_MODEL", _d.PRIMARY_MODEL)):
            if mid not in KNOWN_MODEL_IDS:
                alerts.append(f"MODEL: {label}='{mid}' is not in KNOWN_MODEL_IDS; "
                              f"confirm it is still served and update the set")
        if "prefill" in _d.__doc__.lower() if _d.__doc__ else False:
            pass
        age = _d.baseline_age_days()
        if age >= BASELINE_ALERT_DAYS:
            alerts.append(f"BASELINES: hand-verified {age} days ago "
                          f"({_d.BASELINES_VERIFIED_AS_OF}); re-verify leaders, trade stack, "
                          f"upcoming dates and bump BASELINES_VERIFIED_AS_OF")
        elif age >= BASELINE_WARN_DAYS:
            warnings.append(f"BASELINES: hand-verified {age} days ago "
                            f"({_d.BASELINES_VERIFIED_AS_OF})")
    except Exception as e:                                   # noqa: BLE001
        warnings.append(f"HEALTH: could not inspect digest.py ({e})")

    # ── Corpus ──────────────────────────────────────────────────────────
    if payload:
        for tier, floor in TIER_FLOORS.items():
            n = len(payload.get(tier) or [])
            if n < floor:
                (alerts if tier == "tier1" else warnings).append(
                    f"CORPUS: {tier} has {n} articles (floor {floor})")
        srcs = {a.get("source") for t in ("tier1", "tier2", "tier3", "tier4")
                for a in (payload.get(t) or []) if a.get("source")}
        if len(srcs) < 20:
            alerts.append(f"CORPUS: only {len(srcs)} unique sources collected; "
                          f"the June issues shipped on ~10 (SCMP plus direct feeds) "
                          f"after every Google News link failed to resolve")

        rs = payload.get("resolve_stats") or {}
        total = rs.get("gnews_total", 0)
        if total:
            got = rs.get("resolved", 0) + rs.get("cached", 0)
            share = got / total
            if share < RESOLVE_ALERT_BELOW:
                alerts.append(f"RESOLVE: {got}/{total} Google News URLs canonicalised "
                              f"({share:.0%}); Google may have changed the redirect format, "
                              f"see resolve.py")
        fs = payload.get("fulltext_stats") or {}
        if fs and fs.get("enriched", 0) < FULLTEXT_WARN_BELOW:
            warnings.append(f"FULLTEXT: only {fs.get('enriched', 0)} items enriched with "
                            f"article text")

        fr = payload.get("feed_report") or {}
        if fr.get("major_empty"):
            warnings.append(f"FEEDS: major feeds empty: {', '.join(fr['major_empty'])}")
        if fr.get("dead"):
            alerts.append(f"FEEDS: dead for 5+ runs: {', '.join(fr['dead'][:12])}"
                          + (" ..." if len(fr['dead']) > 12 else ""))
        if fr.get("feeds_total") and fr.get("feeds_ok", 0) < 0.6 * fr["feeds_total"]:
            alerts.append(f"FEEDS: {fr.get('feeds_ok')}/{fr.get('feeds_total')} feeds "
                          f"returned entries; check for a Google News block")

        m = payload.get("market_indicators") or {}
        unavailable = [k for k, v in m.items() if isinstance(v, dict) and v.get("unavailable")]
        if len(unavailable) >= 3:
            warnings.append(f"MARKETS: {len(unavailable)} indicators unavailable "
                            f"({', '.join(unavailable)})")

    # ── Digest ──────────────────────────────────────────────────────────
    if digest:
        xd = digest.get("xinhua_delta") or {}
        if xd.get("silence_today") and "scraper" in str(xd.get("bottom_line", "")).lower():
            warnings.append("XINHUA: tier-4 collection returned nothing; check Xinhua / "
                            "Global Times feeds")

    # ── Send cadence ────────────────────────────────────────────────────
    try:
        last = (ROOT / "last_sent.txt").read_text(encoding="utf-8").strip()
        last_d = datetime.strptime(last, "%Y-%m-%d").date()
        today = datetime.now(ZoneInfo("America/New_York")).date()
        gap = (today - last_d).days
        if gap > SEND_GAP_ALERT_DAYS:
            warnings.append(f"CADENCE: last successful send was {last} ({gap} days ago)")
    except Exception:
        pass

    return {"warnings": warnings, "alerts": alerts}


def print_report(report: dict) -> None:
    if not report["alerts"] and not report["warnings"]:
        print("   ✓ Health checks clean")
        return
    if report["alerts"]:
        print("   ✖ Health ALERTS (act this week):")
        for a in report["alerts"]:
            print(f"      • {a}")
    if report["warnings"]:
        print("   ⚠ Health warnings:")
        for w in report["warnings"]:
            print(f"      • {w}")


if __name__ == "__main__":
    payload = None
    digest = None
    try:
        payload = json.loads((ROOT / "collected.json").read_text(encoding="utf-8"))
    except Exception:
        pass
    try:
        digest = json.loads((ROOT / "digest.json").read_text(encoding="utf-8"))
    except Exception:
        pass
    print_report(check(payload, digest))
