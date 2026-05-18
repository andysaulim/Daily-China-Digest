"""
Xi Jinping Appearance Tracker
Persists confirmed appearances to xi_tracker.json across runs.
Exposes build_context_block() for the digest LLM prompt.

Xi appears more frequently than Kim Jong Un — typical absence threshold is 14 days
(vs. Kim's 7 days) before flagging as anomalous.
"""
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

TRACKER_FILE = Path(__file__).parent / "xi_tracker.json"
ABSENCE_THRESHOLD_DAYS = 14   # Xi normally appears more often than Kim


def _load() -> dict:
    if not TRACKER_FILE.exists():
        return {
            "appearances": [],
            "last_updated": None,
        }
    try:
        with open(TRACKER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"appearances": [], "last_updated": None}


def _save(data: dict) -> None:
    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    with open(TRACKER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def record_appearance(date_iso: str, activity: str, source: str, url: str = "") -> None:
    """Record a confirmed Xi appearance. date_iso = YYYY-MM-DD."""
    data = _load()
    entry = {
        "date": date_iso,
        "activity": activity,
        "source": source,
        "url": url,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    # Dedupe by (date, activity) tuple
    existing = {(a["date"], a.get("activity", "")) for a in data["appearances"]}
    if (entry["date"], entry["activity"]) not in existing:
        data["appearances"].append(entry)
        data["appearances"] = sorted(data["appearances"], key=lambda x: x["date"], reverse=True)
        # Keep last 90 days
        cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d")
        data["appearances"] = [a for a in data["appearances"] if a["date"] >= cutoff]
        _save(data)


def days_since_last_appearance() -> int | None:
    data = _load()
    if not data["appearances"]:
        return None
    latest = data["appearances"][0]["date"]
    try:
        latest_dt = datetime.strptime(latest, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - latest_dt
        return delta.days
    except ValueError:
        return None


def recent_appearances(n: int = 10) -> list:
    return _load()["appearances"][:n]


def build_context_block() -> str:
    """Build the prompt context block for digest.py."""
    data = _load()
    appearances = data["appearances"]
    if not appearances:
        return ""

    days_since = days_since_last_appearance()
    threshold_flag = ""
    if days_since is not None and days_since >= ABSENCE_THRESHOLD_DAYS:
        threshold_flag = f" ⚠ ABSENCE ANOMALY: {days_since} days since last confirmed appearance (threshold {ABSENCE_THRESHOLD_DAYS} days)"

    lines = [
        "CONFIRMED XI JINPING APPEARANCES (last 14 days, persistent tracker):",
        f"Days since last confirmed appearance: {days_since if days_since is not None else 'unknown'}{threshold_flag}",
        "",
        "Recent appearances:",
    ]
    cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%d")
    for a in appearances:
        if a["date"] >= cutoff:
            lines.append(f"  • {a['date']}: {a['activity']} (source: {a['source']})")
    if len(lines) == 4:
        lines.append("  (no confirmed appearances in tracker for last 14 days)")

    lines.append("")
    lines.append("Use this tracker as GROUND TRUTH for days_since_last_appearance in xinhua_delta.")
    lines.append("Only override if today's articles confirm a more recent appearance.")
    return "\n".join(lines)


if __name__ == "__main__":
    print(build_context_block())
