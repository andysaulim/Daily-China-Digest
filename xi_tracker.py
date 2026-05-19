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


def update_from_digest(digest: dict) -> None:
    """Extract Xi appearance data from digest output and persist it."""
    xd = digest.get("xinhua_delta") or {}
    if not xd.get("xi_appearance_today"):
        return
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    activity = xd.get("xi_activity_summary") or xd.get("xi_appearance_note") or "Confirmed appearance"
    source = "digest"
    record_appearance(today, activity, source)


def build_dot_calendar(today_appeared: bool | None = None) -> str:
    """Return an HTML dot-grid calendar of Xi appearances for the last 30 days."""
    data = _load()
    appearance_dates = {a["date"] for a in data["appearances"]}
    today = datetime.now(timezone.utc)

    cells = []
    for i in range(29, -1, -1):
        day = today - timedelta(days=i)
        date_str = day.strftime("%Y-%m-%d")
        label = day.strftime("%b %-d")
        if i == 0:
            appeared = today_appeared if today_appeared is not None else (date_str in appearance_dates)
        else:
            appeared = date_str in appearance_dates
        color = "#4CAF50" if appeared else "rgba(255,255,255,0.12)"
        cells.append(
            f'<span title="{label}" style="display:inline-block;width:10px;height:10px;'
            f'border-radius:2px;background:{color};margin:1px;"></span>'
        )

    return (
        '<div style="margin-top:8px;padding:8px 12px;background:rgba(255,255,255,0.04);border-radius:4px;">'
        '<div style="font-size:10px;text-transform:uppercase;letter-spacing:1px;'
        'color:rgba(255,255,255,0.6);margin-bottom:6px;">Xi Appearances — Last 30 Days</div>'
        '<div>' + "".join(cells) + '</div>'
        '</div>'
    )


if __name__ == "__main__":
    print(build_context_block())
