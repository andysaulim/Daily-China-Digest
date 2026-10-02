"""
China Daily Brief — Week in Review
Synthesizes Saturday-through-Friday daily digests into a top-10 weekly edition.
Run: python weekly.py [--no-send]
Triggered Fridays at 9:00 AM ET via GitHub Actions, or manually.
"""
import json
import os
import time
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import anthropic


WEEKLY_SYSTEM_PROMPT = """You are the senior intelligence analyst for the CSIS Korea Chair China Programs. You produce the China Daily Brief — Week in Review edition, a concise synthesis of the week's China-related developments for senior policymakers.

Your readers are experts who received the daily briefs but want a consolidated weekend read highlighting what mattered most this week. Be ruthlessly concise — they've already seen the details. Your job is synthesis, pattern recognition, and what the week's events collectively mean for the US-China relationship, the cross-strait situation, and China's global posture.

RULES:
- SOURCE-OR-SKIP: Every claim — every date, destination, name, number, and event — must appear explicitly in the daily digest data provided below. If a detail is not in the digests, it does not exist; omit it. An omission is always better than an invention. You have NO other knowledge; do not add anything from memory or general awareness.
- NO COMPOSITE FACTS: Do NOT merge separate developments into a single combined claim. State only the specific events each digest actually reported, exactly as reported.
- NO EXTRAPOLATION: Do not project, predict, or assume plans unless a daily digest explicitly reported that plan with that specific.
- Synthesis means CONDENSING what was reported across the week, not generating new connective facts.
- No editorializing. No "this is significant", "notably", "importantly". Present patterns and let readers draw conclusions.
- Highlight what CHANGED this week, not what remained stable.
- Return ONLY valid JSON. No markdown fences, no preamble."""


WEEKLY_USER_PROMPT_TEMPLATE = """Today is {date_str} (Friday). Synthesize this week's daily digests (Saturday through Friday) into a Week in Review.

DAILY DIGESTS THIS WEEK:
{digests_json}

Return a JSON object with exactly these fields:

- week_label: string (e.g. "Sep 26 – Oct 2, 2026")
- re_line: 1-sentence summary of the week's single most important development (under 90 chars)
- top_10: array of the 10 most consequential stories this week, ranked by significance. Each item: rank (1-10), headline (concise factual string), body (2-3 sentences synthesizing the week's coverage — every date, name, and figure must appear in the source digests), first_reported (date string "YYYY-MM-DD"), category (exactly one of: "US-China", "Cross-Strait", "PLA", "Technology", "Sanctions", "Economy", "Diplomacy", "PRC-Domestic", "Indo-Pacific", "Energy"), sources (array of outlet name strings that covered this story). If fewer than 10 consequential stories occurred, return fewer items — do not pad with trivial ones.
- us_china_weekly: object summarizing the week's US-China relationship — instruments (array of strings listing the policy instruments in play this week, e.g. "Tariff", "Export Controls", "Diplomacy"), high_point (string: the single most constructive US-China development this week, or null), low_point (string: the single most escalatory development, or null), summary (2-3 sentences on the week's overall trajectory)
- xi_weekly: object summarizing Xi Jinping's activities — appearances (count of days with Xi coverage), destinations (array of location strings from travel or meetings this week), key_quotes (up to 2 most significant Xi quotes from official_line, each as a string), summary (1-2 sentences on Xi's week)
- market_weekly: object — sse_change_pct (string weekly SSE Composite move e.g. "+1.2%" or null if unavailable), hsi_change_pct (string weekly Hang Seng move or null), usd_cny_change_pct (string weekly USD/CNY move or null), pboc_action (string describing any PBOC rate decision or null), notes (string with any notable market development or null)
- calendar_next_week: array of 3-5 key events in the coming 7 days. Each: date (string), headline (string), detail (1-sentence string)
- bottom_line: 2-3 sentences. The single most important takeaway from this week and what to watch next week. Ruthlessly concise.
- story_count_total: integer total Tier 1 articles processed across all daily digests this week
"""


def _load_week_digests() -> list[dict]:
    """Load daily digest JSON files from Saturday through Friday (today)."""
    tz = ZoneInfo("America/New_York")
    today = datetime.now(tz).date()
    days_since_saturday = (today.weekday() - 5) % 7
    if days_since_saturday == 0:
        days_since_saturday = 7
    start_date = today - timedelta(days=days_since_saturday)

    digests = []
    d = start_date
    while d <= today:
        date_slug = d.strftime("%Y-%m-%d")
        for pattern in [
            f"public/digest_{date_slug}.json",
            f"digest_{date_slug}.json",
        ]:
            path = Path(pattern)
            if path.exists():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    data["_date"] = date_slug
                    digests.append(data)
                except (json.JSONDecodeError, IOError):
                    continue
                break
        d += timedelta(days=1)
    return digests


def _summarize_digest(d: dict) -> dict:
    """Extract key fields from a daily digest for the weekly prompt."""
    def _heads(items, n=3):
        return [{"headline": s.get("headline", ""), "source": s.get("source", "")}
                for s in (items or [])[:n]]

    mkt = d.get("market_indicators") or {}

    return {
        "date": d.get("_date", d.get("digest_date", "unknown")),
        "re_line": d.get("re_line", ""),
        "top_stories": [
            {
                "headline": s.get("headline", ""),
                "category": s.get("category_tag", s.get("category", "")),
                "source": s.get("source", ""),
                "body": (s.get("body") or s.get("body_text") or "")[:300],
            }
            for s in (d.get("top_stories") or [])
        ],
        "us_china": _heads(d.get("us_china"), 4),
        "china_world": _heads(d.get("china_world"), 4),
        "business_economy": _heads(d.get("business_economy"), 3),
        "overnight_headlines": _heads(d.get("overnight_items"), 5),
        "also_today_headlines": [s.get("headline", "") for s in (d.get("also_today") or [])[:4]],
        "official_line": [
            {
                "source_label": s.get("source_label", ""),
                "quote": (s.get("quote_text") or s.get("body_text") or "")[:200],
            }
            for s in (d.get("official_line") or [])[:3]
        ],
        "prc_government": [
            {"ministry": a.get("ministry", ""), "action": a.get("action", "")}
            for a in (d.get("prc_government") or [])[:3]
        ],
        "market_indicators": {
            k: mkt.get(k) for k in
            ("sse_composite", "hsi", "usd_cny", "usd_cnh", "pboc_lpr_1y", "pboc_lpr_5y")
            if mkt.get(k) is not None
        },
        "calendar_watch": (d.get("calendar_watch") or [])[:4],
        "story_count": d.get("story_count", 0),
    }


def generate_weekly(digests: list[dict]) -> dict:
    """Generate weekly summary via Claude API."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("Missing ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key)

    summaries = [_summarize_digest(d) for d in digests]
    tz = ZoneInfo("America/New_York")
    date_str = datetime.now(tz).strftime("%A, %B %-d, %Y")

    user_prompt = WEEKLY_USER_PROMPT_TEMPLATE.format(
        date_str=date_str,
        digests_json=json.dumps(summaries, ensure_ascii=False, indent=1),
    )

    print(f"\n\U0001f916  Generating weekly summary ({len(digests)} daily digests)...")
    t0 = time.time()
    collected = []
    with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=6000,
        system=[{
            "type": "text",
            "text": WEEKLY_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{"role": "user", "content": user_prompt}],
    ) as stream:
        for text in stream.text_stream:
            collected.append(text)
    elapsed = time.time() - t0
    print(f"    ⏱  Weekly generation: {elapsed:.0f}s")

    text = "".join(collected).strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return json.loads(text.strip())


def _esc(text) -> str:
    if not text:
        return ""
    return (str(text)
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def render_weekly(weekly: dict) -> str:
    """Render the Week in Review in the China Daily Brief house style."""
    BAND        = "#DE2910"   # China red — masthead band
    NAVY        = "#1B2A4A"
    INK         = "#1A222E"
    MUTE        = "#6B7280"
    BODY_INK    = "#4A5260"
    BLUE_ON_NAVY = "#7EB8F7"
    UP_GREEN    = "#27AE60"
    DOWN_RED    = "#C0392B"

    SERIF = "Georgia,'Times New Roman',serif"
    SANS  = "Arial,Helvetica,sans-serif"
    RULE  = "#E4E7EB"
    PANEL = "#F8F9FA"

    week_label  = _esc(weekly.get("week_label", ""))
    re_line     = _esc(weekly.get("re_line", ""))
    bottom_line = _esc(weekly.get("bottom_line", ""))

    def _sec(title: str, body: str) -> str:
        label = (f'<div style="font-size:10px;font-weight:700;text-transform:uppercase;'
                 f'letter-spacing:2px;color:{NAVY};font-family:{SANS};margin-bottom:14px;'
                 f'padding-bottom:8px;border-bottom:2px solid {NAVY};">{title}</div>')
        return (f'<div style="padding:20px 32px;border-bottom:1px solid {RULE};" class="sec">'
                f'{label}{body}</div>')

    # ── Top 10 ───────────────────────────────────────────────────────────
    CAT_COLORS = {
        "US-China": "#C0392B", "Cross-Strait": "#1B2A4A", "PLA": "#6E0019",
        "Technology": "#1A5276", "Sanctions": "#784212", "Economy": "#1E8449",
        "Diplomacy": "#2980B9", "PRC-Domestic": "#6C3483", "Indo-Pacific": "#17798C",
        "Energy": "#B7950B",
    }
    top_html = ""
    for item in (weekly.get("top_10") or []):
        rank     = int(item.get("rank", 0))
        headline = _esc(item.get("headline", ""))
        body     = _esc(item.get("body", ""))
        cat      = _esc(item.get("category", ""))
        srcs     = " &middot; ".join(_esc(s) for s in (item.get("sources") or [])[:3])
        date     = _esc(item.get("first_reported", ""))
        cat_col  = CAT_COLORS.get(item.get("category", ""), NAVY)
        top_html += f"""
<tr><td style="padding:10px 0 12px;border-bottom:1px solid {RULE};vertical-align:top;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
    <td style="width:28px;vertical-align:top;padding-top:1px;">
      <div style="font-family:{SANS};font-size:18px;font-weight:700;color:#D0D5DC;line-height:1;">{rank}</div>
    </td>
    <td style="vertical-align:top;padding-left:8px;">
      <div style="margin-bottom:3px;">
        <span style="display:inline-block;padding:1px 7px;border-radius:3px;font-size:10px;
          font-weight:700;letter-spacing:0.5px;color:#fff;background:{cat_col};
          font-family:{SANS};">{cat}</span>
        {(f'<span style="font-family:{SANS};font-size:10px;color:{MUTE};margin-left:6px;">{date}</span>') if date else ""}
      </div>
      <div style="font-family:{SERIF};font-size:14px;font-weight:700;color:{NAVY};
        line-height:1.35;margin-bottom:4px;">{headline}</div>
      <div style="font-family:{SERIF};font-size:13px;color:{BODY_INK};line-height:1.55;
        margin-bottom:4px;">{body}</div>
      {(f'<div style="font-family:{SANS};font-size:10px;color:{MUTE};">{srcs}</div>') if srcs else ""}
    </td>
  </tr></table>
</td></tr>"""

    # ── US-China weekly ──────────────────────────────────────────────────
    usc = weekly.get("us_china_weekly") or {}
    usc_instruments = " &nbsp;&middot;&nbsp; ".join(
        f'<span style="display:inline-block;padding:1px 8px;border-radius:3px;'
        f'font-size:10px;font-weight:700;color:#fff;background:{NAVY};'
        f'font-family:{SANS};">{_esc(i)}</span>'
        for i in (usc.get("instruments") or [])
    )
    usc_hi  = _esc(usc.get("high_point") or "")
    usc_lo  = _esc(usc.get("low_point") or "")
    usc_sum = _esc(usc.get("summary") or "")
    usc_html = f"""
<div style="margin-bottom:10px;">{usc_instruments}</div>
{"".".join([
    f'<div style="padding:8px 12px;margin-bottom:6px;border-left:3px solid #27AE60;background:{PANEL};font-family:{SERIF};font-size:13px;color:{INK};line-height:1.5;"><strong style="font-size:10px;font-family:{SANS};text-transform:uppercase;letter-spacing:1px;color:#27AE60;">High point</strong><br>{usc_hi}</div>'
    if usc_hi else "",
    f'<div style="padding:8px 12px;margin-bottom:6px;border-left:3px solid #C0392B;background:{PANEL};font-family:{SERIF};font-size:13px;color:{INK};line-height:1.5;"><strong style="font-size:10px;font-family:{SANS};text-transform:uppercase;letter-spacing:1px;color:#C0392B;">Low point</strong><br>{usc_lo}</div>'
    if usc_lo else "",
    f'<div style="font-family:{SERIF};font-size:13px;color:{BODY_INK};line-height:1.6;margin-top:8px;">{usc_sum}</div>'
    if usc_sum else "",
])}"""

    # ── Xi weekly ────────────────────────────────────────────────────────
    xi = weekly.get("xi_weekly") or {}
    xi_appear = xi.get("appearances", 0)
    xi_dests  = ", ".join(_esc(d) for d in (xi.get("destinations") or []))
    xi_quotes_html = ""
    for q in (xi.get("key_quotes") or []):
        xi_quotes_html += (f'<div style="padding:8px 12px;margin-bottom:6px;'
                           f'border-left:3px solid {NAVY};background:{PANEL};'
                           f'font-family:{SERIF};font-size:13px;font-style:italic;'
                           f'color:{INK};line-height:1.5;">{_esc(q)}</div>')
    xi_sum = _esc(xi.get("summary") or "")
    xi_html = f"""
<div style="font-family:{SANS};font-size:11px;color:rgba(255,255,255,0.70);margin-bottom:9px;">
  Appearances: {xi_appear} days
  {f'&nbsp;&middot;&nbsp; Locations: {xi_dests}' if xi_dests else ''}
</div>
<div style="font-family:{SERIF};font-size:13px;color:#E8E6E1;line-height:1.55;margin-bottom:10px;">{xi_sum}</div>
{xi_quotes_html.replace(f'background:{PANEL}', 'background:rgba(255,255,255,0.08)').replace(f'color:{INK}', 'color:#E8E6E1')}"""

    xi_band = (f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
               f'style="background:{NAVY};margin-bottom:0;">'
               f'<tr><td style="padding:16px 20px;">'
               f'<div style="font-family:{SANS};font-size:11px;font-weight:700;'
               f'text-transform:uppercase;letter-spacing:2px;color:{BLUE_ON_NAVY};'
               f'margin-bottom:10px;">Xi Jinping &middot; Week Summary</div>'
               f'{xi_html}</td></tr></table>')

    # ── Markets ──────────────────────────────────────────────────────────
    mkt = weekly.get("market_weekly") or {}

    def _signed(raw):
        text = _esc(str(raw if raw not in (None, "") else "—"))
        s = text.lstrip()
        if s.startswith("+"):
            return text, UP_GREEN
        if s.startswith(("-", "−")):
            return text, DOWN_RED
        return text, INK

    sse_txt, sse_col = _signed(mkt.get("sse_change_pct"))
    hsi_txt, hsi_col = _signed(mkt.get("hsi_change_pct"))
    cny_txt, cny_col = _signed(mkt.get("usd_cny_change_pct"))
    pboc = _esc(mkt.get("pboc_action") or "No action")
    notes = _esc(mkt.get("notes") or "")
    _cell = (f'font-family:{SANS};font-size:10px;font-weight:700;'
             f'text-transform:uppercase;letter-spacing:1.5px;color:{MUTE};')
    mkt_html = f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0" class="mkt-table" style="background:{PANEL};">
  <tr>
    <td style="padding:13px 16px;text-align:center;width:25%;">
      <div style="{_cell}">SSE</div>
      <div style="font-family:{SERIF};font-size:17px;font-weight:700;color:{sse_col};margin-top:3px;">{sse_txt}</div>
    </td>
    <td style="padding:13px 16px;text-align:center;width:25%;border-left:1px solid {RULE};">
      <div style="{_cell}">Hang Seng</div>
      <div style="font-family:{SERIF};font-size:17px;font-weight:700;color:{hsi_col};margin-top:3px;">{hsi_txt}</div>
    </td>
    <td style="padding:13px 16px;text-align:center;width:25%;border-left:1px solid {RULE};border-right:1px solid {RULE};">
      <div style="{_cell}">USD/CNY</div>
      <div style="font-family:{SERIF};font-size:17px;font-weight:700;color:{cny_col};margin-top:3px;">{cny_txt}</div>
    </td>
    <td style="padding:13px 16px;text-align:center;width:25%;">
      <div style="{_cell}">PBOC</div>
      <div style="font-family:{SERIF};font-size:12px;color:{INK};margin-top:4px;">{pboc}</div>
    </td>
  </tr>
</table>
{(f'<div style="font-family:{SERIF};font-size:12px;color:{MUTE};padding:8px 4px;">{notes}</div>') if notes else ""}"""

    # ── Calendar ─────────────────────────────────────────────────────────
    cal_html = ""
    for event in (weekly.get("calendar_next_week") or []):
        date    = _esc(event.get("date", ""))
        hl      = _esc(event.get("headline", ""))
        detail  = _esc(event.get("detail", ""))
        cal_html += (f'<tr><td style="padding:9px 0;border-bottom:1px solid {RULE};">'
                     f'<div style="font-family:{SERIF};font-size:14px;color:{INK};line-height:1.4;">'
                     f'<strong style="color:{NAVY};">{date}</strong> &mdash; {hl}</div>'
                     f'<div style="font-family:{SERIF};font-size:12px;color:{BODY_INK};'
                     f'margin-top:3px;line-height:1.5;">{detail}</div>'
                     f'</td></tr>')

    tz = ZoneInfo("America/New_York")
    gen_time    = datetime.now(tz).strftime("%-I:%M %p ET")
    story_count = _esc(str(weekly.get("story_count_total", 0)))

    _re_block = (
        f'<div style="margin-top:14px;padding-top:12px;'
        f'border-top:1px solid rgba(255,255,255,0.28);font-family:{SERIF};'
        f'font-size:13px;color:rgba(255,255,255,0.92);line-height:1.55;">'
        f'<strong style="color:#FFFFFF;font-size:11px;letter-spacing:1.5px;'
        f'font-family:{SANS};">RE:</strong>&nbsp; {re_line}</div>'
    ) if re_line else ""

    sections = "".join([
        _sec("Top 10 Stories of the Week",
             f'<table width="100%" cellpadding="0" cellspacing="0" border="0">{top_html}</table>'),
        _sec("US–China Relationship", usc_html) if (usc_html.strip()) else "",
        f'<div style="padding:0;border-bottom:1px solid {RULE};" class="sec">{xi_band}</div>',
        _sec("Markets", mkt_html) if mkt_html.strip() else "",
        _sec("Next Week",
             f'<table width="100%" cellpadding="0" cellspacing="0" border="0">{cal_html}</table>')
        if cal_html else "",
        _sec("Bottom Line",
             f'<div style="padding:16px;background:{PANEL};border-left:3px solid {NAVY};">'
             f'<div style="font-family:{SERIF};font-size:14px;color:{INK};'
             f'line-height:1.6;">{bottom_line}</div></div>')
        if bottom_line else "",
    ])

    return f"""<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="color-scheme" content="light dark">
<meta name="supported-color-schemes" content="light dark">
<title>China Week in Review &middot; {week_label}</title>
<style type="text/css">
body {{ margin:0;padding:0;background:#F0F0F0; }}
@media (prefers-color-scheme: dark) {{
  body {{ background:#121212 !important; }}
  .wrapper {{ background:#1a1a1a !important; }}
  .wrapper [style*="background:#FFFFFF"] {{ background-color:#262A30 !important; }}
  .wrapper [style*="background:#F8F9FA"] {{ background-color:#1A1D22 !important; }}
  .wrapper [style*="color:#1A222E"],
  .wrapper [style*="color:#1B2A4A"] {{ color:#E8E6E1 !important; }}
  .wrapper [style*="color:#4A5260"] {{ color:#C4C8CE !important; }}
  .wrapper [style*="color:#6B7280"] {{ color:#9AA3AE !important; }}
  .wrapper h1 {{ color:#FFFFFF !important; }}
}}
@media screen and (max-width: 600px) {{
    .wrapper {{ width:100% !important; max-width:680px !important; }}
    .sec {{ padding:16px 14px !important; }}
    .mkt-table td {{ padding:10px 6px !important; }}
  }}
</style>
</head>
<body style="margin:0;padding:0;background:#F0F0F0;">
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#F0F0F0;">
<tr><td align="center" style="padding:20px 0;">
<table role="presentation" class="wrapper" width="680" cellpadding="0" cellspacing="0"
  border="0" align="center"
  style="width:680px;max-width:100%;margin:0 auto;background:#FFFFFF;
         font-family:{SANS};box-shadow:0 2px 20px rgba(0,0,0,0.08);">
<tr><td style="padding:0;">

  <div bgcolor="{BAND}" style="background-color:{BAND};color:#fff;padding:16px 32px;
    border-bottom:1px solid rgba(255,255,255,0.18);" class="sec mast-band">
    <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
      <td class="mast-main" style="vertical-align:top;">
        <div style="font-family:{SANS};font-size:11px;font-weight:700;letter-spacing:2px;
          text-transform:uppercase;color:rgba(255,255,255,0.78);margin-bottom:7px;">CSIS China Programs</div>
        <h1 style="margin:0 0 4px 0;font-size:26px;font-weight:700;font-family:{SERIF};
          color:#fff;letter-spacing:0.5px;">Week in Review</h1>
        <div style="margin-top:2px;font-size:16px;font-weight:400;
          color:rgba(255,255,255,0.85);font-family:{SERIF};">{week_label}</div>
      </td>
      <td class="mast-meta" style="vertical-align:bottom;text-align:right;">
        <div style="font-family:{SANS};font-size:11px;letter-spacing:0.5px;
          color:rgba(255,255,255,0.72);white-space:nowrap;">{story_count} articles this week</div>
      </td>
    </tr></table>
    {_re_block}
  </div>

  {sections}

  <div class="footer" style="background:{NAVY};padding:22px 32px;text-align:center;">
    <div style="font-family:{SERIF};font-size:12px;line-height:1.6;color:rgba(255,255,255,0.80);">
      You are receiving the China Week in Review as a member of the CSIS China Programs distribution list.
    </div>
    <div style="font-family:{SANS};font-size:10px;text-transform:uppercase;letter-spacing:2px;
      color:rgba(255,255,255,0.45);line-height:2;margin-top:10px;">
      CSIS China Programs &nbsp;&middot;&nbsp; Week in Review &nbsp;&middot;&nbsp; Generated {gen_time}
    </div>
  </div>

</td></tr>
</table>
</td></tr></table>
</body></html>"""


def main():
    import argparse
    parser = argparse.ArgumentParser(description="China Daily Brief — Week in Review")
    parser.add_argument("--no-send", action="store_true", help="Render only, no email")
    parser.add_argument("--send-to", default="", help="Override recipients (comma-separated)")
    args = parser.parse_args()

    digests = _load_week_digests()
    if not digests:
        print("⚠  No daily digests found for this week. Run daily pipeline first.")
        return

    dates = [d.get("_date", "?") for d in digests]
    print(f"\U0001f4c5  Found {len(digests)} daily digests: {', '.join(dates)}")

    weekly = generate_weekly(digests)

    tz = ZoneInfo("America/New_York")
    date_slug = datetime.now(tz).strftime("%Y-%m-%d")
    json_path = Path(f"weekly_{date_slug}.json")
    json_path.write_text(json.dumps(weekly, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\U0001f4c4  Weekly JSON: {json_path}")

    html = render_weekly(weekly)
    html_path = Path(f"weekly_{date_slug}.html")
    html_path.write_text(html, encoding="utf-8")
    print(f"\U0001f4c4  Weekly HTML: {html_path}")

    if not args.no_send:
        recipients = args.send_to or os.environ.get("DIGEST_TO", "")
        if recipients:
            from send_email import send_digest
            week_label = weekly.get("week_label", date_slug)
            subject = f"China Week in Review | {week_label}"
            send_digest(html, subject=subject,
                        recipients=[r.strip() for r in recipients.split(",") if r.strip()])
            print("\U0001f4e7  Weekly email sent")
        else:
            print("⚠  DIGEST_TO not set — skipping email")
    else:
        print("  --no-send: skipping email")

    print("\n✅  Week in Review done.\n")


if __name__ == "__main__":
    main()
