"""
Xinhua / People's Daily Rhetoric Tracker
Persists phrase frequency baselines across runs in xinhua_tracker.json.
Exposes build_context_block() for the digest LLM prompt.

Tracks doctrinal phrases (Xi's signature concepts) and propaganda focus over time.
"""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

TRACKER_FILE = Path(__file__).parent / "xinhua_tracker.json"

# Doctrinal phrases that signal policy direction (CN + EN variants)
TRACKED_PHRASES = [
    # Economic doctrine
    ("new productive forces", "新质生产力"),
    ("common prosperity", "共同富裕"),
    ("Chinese-style modernization", "中国式现代化"),
    ("dual circulation", "双循环"),
    ("high-quality development", "高质量发展"),
    ("self-reliance", "自力更生"),

    # Political doctrine
    ("great rejuvenation", "伟大复兴"),
    ("two establishes", "两个确立"),
    ("two safeguards", "两个维护"),
    ("Xi Jinping Thought", "习近平思想"),
    ("whole-process democracy", "全过程人民民主"),
    ("Community of Common Destiny", "人类命运共同体"),

    # Foreign policy / security
    ("Global Security Initiative", "全球安全倡议"),
    ("Global Development Initiative", "全球发展倡议"),
    ("Global Civilization Initiative", "全球文明倡议"),
    ("national reunification", "祖国统一"),
    ("Taiwan independence", "台独"),
    ("hegemonism", "霸权主义"),
    ("Cold War mentality", "冷战思维"),
    ("decoupling", "脱钩"),
    ("small yard high fence", "小院高墙"),
    ("de-risking", "去风险"),

    # Military / posture
    ("strong military", "强军"),
    ("integrated joint operations", "联合作战"),
    ("informatized warfare", "信息化战争"),
    ("new era strong military thought", "新时代强军思想"),
]


def _load() -> dict:
    if not TRACKER_FILE.exists():
        return {
            "daily_counts": {},     # {YYYY-MM-DD: {phrase: count}}
            "tone_history": {},     # {YYYY-MM-DD: {target: tone}}
            "last_updated": None,
        }
    try:
        with open(TRACKER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"daily_counts": {}, "tone_history": {}, "last_updated": None}


def _save(data: dict) -> None:
    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    with open(TRACKER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def record_day(date_iso: str, phrase_counts: dict, tones: dict | None = None) -> None:
    """Record phrase counts and tone quadrants for one day.
    phrase_counts: {phrase: count}
    tones: {target_country: tone_label} e.g. {"US": "Hostile", "Japan": "Neutral"}
    """
    data = _load()
    data["daily_counts"][date_iso] = phrase_counts
    if tones:
        data["tone_history"][date_iso] = tones
    # Trim to last 60 days
    cutoff = (datetime.now(timezone.utc) - timedelta(days=60)).strftime("%Y-%m-%d")
    data["daily_counts"] = {k: v for k, v in data["daily_counts"].items() if k >= cutoff}
    data["tone_history"] = {k: v for k, v in data["tone_history"].items() if k >= cutoff}
    _save(data)


def aggregate_phrase_counts(days: int = 7) -> dict:
    """Aggregate phrase counts over the last N days."""
    data = _load()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    agg = {}
    for date_iso, counts in data["daily_counts"].items():
        if date_iso >= cutoff:
            for phrase, count in counts.items():
                agg[phrase] = agg.get(phrase, 0) + count
    return agg


def build_context_block() -> str:
    """Build the prompt context block for digest.py."""
    data = _load()
    if not data["daily_counts"]:
        return ""

    lines = [
        "XINHUA / PEOPLE'S DAILY RHETORIC HISTORY (persistent tracker, last 60 days):",
        "",
        "TRACKED DOCTRINAL PHRASES (CN / EN variants):",
    ]
    for en, cn in TRACKED_PHRASES:
        lines.append(f"  • {en} / {cn}")
    lines.append("")

    agg_7d = aggregate_phrase_counts(days=7)
    if agg_7d:
        lines.append("AGGREGATE PHRASE COUNTS (last 7 days):")
        for phrase, count in sorted(agg_7d.items(), key=lambda x: -x[1])[:20]:
            lines.append(f"  • {phrase}: ×{count}")
        lines.append("")

    # Recent daily entries
    recent_dates = sorted(data["daily_counts"].keys(), reverse=True)[:5]
    if recent_dates:
        lines.append("RECENT DAILY COUNTS (last 5 days with data):")
        for d in recent_dates:
            counts = data["daily_counts"][d]
            top = sorted(counts.items(), key=lambda x: -x[1])[:5]
            top_str = ", ".join(f"{p} ×{c}" for p, c in top)
            lines.append(f"  • {d}: {top_str}")
        lines.append("")

    # Tone history
    if data["tone_history"]:
        recent_tone = sorted(data["tone_history"].keys(), reverse=True)[:5]
        lines.append("RECENT TONE QUADRANTS (last 5 days with data):")
        for d in recent_tone:
            tones = data["tone_history"][d]
            tone_str = " · ".join(f"{tgt}: {t}" for tgt, t in tones.items())
            lines.append(f"  • {d}: {tone_str}")
        lines.append("")

    lines.append("Use this tracker as GROUND TRUTH for count_prior values in key_phrase_changes.")
    lines.append("If a phrase has no prior count, use 0 and label as 'no baseline'.")
    return "\n".join(lines)


if __name__ == "__main__":
    print(build_context_block())
