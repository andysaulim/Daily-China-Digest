"""
China Daily Brief — HTML Renderer
CSIS Korea Chair

Mirrors Daily-Korea-Digest visual language exactly:
- Navy #1B2A4A header + saturated CSIS palette
- Arial/Georgia stack (NOT v3.1 Libre Baskerville)
- Status pills (rounded), status badges (small rounded)
- Colored left-borders for category coding
- Dark Xinhua Delta panel mirroring KCNA Delta dark theme
"""

import re as _re
from datetime import datetime, timezone
from urllib.parse import urlparse as _urlparse


def _clean_src(raw: str) -> str:
    if not raw:
        return raw
    stripped = raw.strip()
    if _re.match(r'^https?://', stripped) and ' ' not in stripped:
        try:
            host = _urlparse(stripped).hostname or ""
            if host.startswith("www."):
                host = host[4:]
            return host if host else raw
        except Exception:
            return raw
    cleaned = _re.sub(r'https?://\S+', '', raw).strip()
    cleaned = _re.sub(r' +', ' ', cleaned)
    return cleaned if cleaned else raw


def _str(val) -> str:
    if isinstance(val, list):
        return val[0] if val else ""
    return val if isinstance(val, str) else str(val) if val is not None else ""


def _esc(text) -> str:
    if text is None or text == "":
        return ""
    text = str(text)
    if text == "None":
        return ""
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                .replace('"', "&quot;"))


def _signal_badge(signal_type: str) -> str:
    colors = {"ESCALATION": "#C0392B", "ANOMALY": "#8E44AD", "DEVELOPMENT": "#2980B9",
              "CONFIRMATION": "#27AE60", "CONTEXT": "#7F8C8D"}
    c = colors.get(signal_type, "#7F8C8D")
    return (f'<span style="display:inline-block;padding:2px 8px;border-radius:3px;'
            f'font-size:11px;font-weight:600;color:#fff;background:{c};'
            f'letter-spacing:0.5px;">{_esc(signal_type)}</span>')


def _social_badge(badge_class: str) -> str:
    return {"sb-p": "#1B2A4A", "sb-r": "#C0392B", "sb-s": "#8E44AD"}.get(badge_class, "#1B2A4A")


def _arrow(val) -> str:
    try:
        val = float(val)
    except (TypeError, ValueError):
        return '<span style="color:#7F8C8D;">—</span>'
    if val > 0:
        return f'<span style="color:#27AE60;">&#9650; +{val:.2f}%</span>'
    if val < 0:
        return f'<span style="color:#C0392B;">&#9660; {val:.2f}%</span>'
    return '<span style="color:#7F8C8D;">— flat</span>'


def _cds_arrow(val) -> str:
    try:
        val = float(val)
    except (TypeError, ValueError):
        return '<span style="color:#7F8C8D;">—</span>'
    if val > 0:
        return f'<span style="color:#C0392B;">&#9650; +{val:.1f} bps</span>'
    if val < 0:
        return f'<span style="color:#27AE60;">&#9660; {val:.1f} bps</span>'
    return '<span style="color:#7F8C8D;">— flat</span>'


def _link_or_text(text: str, url: str,
                  style: str = "color:#1B2A4A;text-decoration:underline;") -> str:
    if url and url != "#" and url.startswith("http"):
        return f'<a href="{_esc(url)}" style="{style}">{text}</a>'
    return text


_SEC = 'style="padding:14px 32px;border-bottom:1px solid #E0E0E0;" class="sec"'
_SEC_BG = lambda bg: f'style="padding:14px 32px;background:{bg};border-bottom:1px solid #E0E0E0;" class="sec"'
_PILL = lambda bg: f'style="display:inline-block;background:{bg};color:#fff;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;padding:5px 14px;border-radius:2px;font-family:Arial,sans-serif;margin-bottom:10px;"'


def _word_count(d: dict) -> int:
    """Count words in ALL visible text — headlines, bodies, notes, every section."""
    w = 0

    def _w(s):
        return len(str(s).split()) if s else 0

    # Header
    w += _w(d.get("re_line"))

    # Morning memo
    for mi in (d.get("morning_memo") or []):
        w += _w(mi) if isinstance(mi, str) else _w(mi.get("text", "")) if isinstance(mi, dict) else 0

    # Δ Since Yesterday
    for item in ((d.get("delta_since_yesterday") or {}).get("items") or []):
        w += _w(item)

    # Top stories — headline + body + so_what + pattern + src_line
    for s in (d.get("top_stories") or []):
        for f in ("headline", "body", "so_what", "pattern_note", "src_line"):
            w += _w(s.get(f, ""))

    # Lists with headline + body_text
    for key in ("overnight_items", "also_today", "business_economy", "indo_pacific"):
        for it in (d.get(key) or []):
            w += _w(it.get("headline", ""))
            w += _w(it.get("body_text", ""))

    # Op-eds + academic — title + summary + analytical
    for o in (d.get("opeds_today") or []):
        for f in ("title", "summary", "central_argument", "policy_so_what", "authors"):
            w += _w(o.get(f, ""))
    for a in (d.get("academic_today") or []):
        for f in ("title", "summary", "authors"):
            w += _w(a.get(f, ""))

    # PRC government / Congress / NPC / Personnel
    for g in (d.get("prc_government") or []):
        for f in ("action", "detail", "official", "ministry"):
            w += _w(g.get(f, ""))
    for c in (d.get("congressional_watch") or []):
        for f in ("committee", "action", "detail"):
            w += _w(c.get(f, ""))
    for n in (d.get("npc_politburo") or []):
        for f in ("body", "action", "detail"):
            w += _w(n.get(f, ""))
    for p in (d.get("personnel_changes") or []):
        for f in ("name", "position", "detail", "predecessor"):
            w += _w(p.get(f, ""))

    # Calendar + on this day
    for c in (d.get("calendar_watch") or []):
        for f in ("headline", "detail"):
            w += _w(c.get(f, ""))
    for o in (d.get("on_this_day") or []):
        for f in ("event", "relevance"):
            w += _w(o.get(f, ""))

    # Monitored locations
    for loc in (d.get("monitored_locations") or []):
        for f in ("name", "note", "csis_product"):
            w += _w(loc.get(f, ""))

    # Key stat
    ks = d.get("key_stat") or {}
    for f in ("label", "context", "source"):
        w += _w(ks.get(f, ""))

    # Xinhua Delta — full coverage
    xd = d.get("xinhua_delta") or {}
    for f in ("bottom_line", "doctrinal_shift", "output_volume",
              "xi_activity", "notable_omissions",
              "peoples_daily_front_page", "global_times_editorial",
              "baseline_period"):
        w += _w(xd.get(f, ""))
    for p in (xd.get("propaganda_focus") or []):
        w += _w(p)
    for q in (xd.get("key_quotes") or []):
        if isinstance(q, dict):
            w += _w(q.get("quote", ""))
            w += _w(q.get("source_article", ""))
    for v in (xd.get("tone_shifts") or {}).values():
        w += _w(v)
    sc = xd.get("xinhua_commentary") or {}
    w += _w(sc.get("topic", ""))
    w += _w(sc.get("key_argument", ""))
    mofa_p = xd.get("mofa_presser") or {}
    if isinstance(mofa_p, dict):
        w += _w(mofa_p.get("key_qa", ""))
    for p in (xd.get("key_phrase_changes") or []):
        w += _w(p.get("phrase", ""))
        w += _w(p.get("delta_label", ""))

    # Social statements
    for s in (d.get("social_statements") or []):
        for f in ("who", "handle_context", "platform_date", "quote_text", "analyst_note"):
            w += _w(s.get(f, ""))

    # Public sentiment
    ps = d.get("public_sentiment") or {}
    cs = ps.get("censorship_signals") or {}
    for t in (cs.get("blocked_terms") or []):
        w += _w(t)
    cf = ps.get("capital_flow_proxies") or {}
    for f in ("stock_connect_net", "cny_pressure", "gold_signal"):
        w += _w(cf.get(f, ""))
    for p in (ps.get("protest_tracker") or []):
        for f in ("location", "type", "date"):
            w += _w(p.get(f, ""))
    tp = ps.get("taiwan_polling") or {}
    w += _w(tp.get("finding", ""))
    w += _w(ps.get("discourse_flag", ""))

    # Sanctions status footer
    w += _w((d.get("sanctions_status") or {}).get("line", ""))

    return w


def _chapter(label: str) -> str:
    """Chapter divider — thin warm-gray band with centered navy uppercase letterspaced label."""
    return f"""
<div style="padding:22px 32px 18px;background:#F0EDE5;border-top:1px solid #D8D2C7;border-bottom:1px solid #D8D2C7;text-align:center;" class="sec">
<span style="font-size:11px;font-family:Arial,sans-serif;color:#1B2A4A;text-transform:uppercase;letter-spacing:4px;font-weight:700;">{label}</span>
<div style="height:2px;width:42px;background:#1B2A4A;margin:7px auto 0;"></div>
</div>"""


def render_html(digest: dict) -> str:
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo("America/New_York"))
    date_str = now.strftime("%A, %B %-d, %Y")
    gen_time = now.strftime("%-I:%M %p ET")
    re_line = _esc(digest.get("re_line", ""))
    wc = _word_count(digest)
    read_min = max(1, round(wc / 250))
    web_url = digest.get("web_url", "")
    # Chapter buckets — assembled with chapter dividers at end
    sections_pre = []       # View-in-browser, header, markets, Δ Since Yesterday
    sections_today = []     # Morning Memo, Top Stories, Overnight Flash, Key Stat
    sections_analysis = []  # Xinhua Delta, Expert Analysts, Public Sentiment, Social Statements
    sections_trackers = []  # Satellite Watch, PRC Gov, US-China Trade, Congressional Watch
    sections_wire = []      # Business, Indo-Pacific, Also Today, On This Day
    sections_post = []      # Footer

    # 0. View in browser
    if web_url:
        sections_pre.append(f"""
<div style="background:#F0F0F0;padding:6px 32px;text-align:center;font-size:11px;color:#888;" class="sec">
Email not rendering? <a href="{_esc(web_url)}" style="color:#2980B9;text-decoration:none;">Read online &#8594;</a>
</div>""")

    # 1. Header
    sections_pre.append(f"""
<div style="background:#1B2A4A;color:#fff;padding:18px 32px 14px;" class="sec">
<table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
<td style="vertical-align:top;">
<div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:2px;color:#D4AC0D;font-family:Arial,sans-serif;margin-bottom:6px;">CSIS Korea Chair</div>
<h1 style="margin:0 0 4px 0;font-size:28px;font-weight:700;font-family:Georgia,serif;color:#fff;letter-spacing:0.3px;">China Daily Brief</h1>
<div style="font-size:16px;font-weight:400;color:rgba(255,255,255,0.85);font-family:Georgia,serif;">{_esc(date_str)}</div>
</td>
<td style="vertical-align:top;text-align:right;">
<div style="font-size:10px;text-transform:uppercase;letter-spacing:1px;color:rgba(255,255,255,0.55);margin-bottom:3px;">{gen_time}</div>
<div style="font-size:10px;color:rgba(255,255,255,0.4);">{wc:,} words &middot; {read_min} min read</div>
</td>
</tr></table>
{"<div style='margin-top:12px;padding-top:12px;border-top:1px solid #D4AC0D;font-size:13px;color:rgba(255,255,255,0.9);font-family:Georgia,serif;'><strong style='color:#D4AC0D;font-family:Arial,sans-serif;font-size:11px;letter-spacing:1px;'>RE:</strong>&nbsp; " + re_line + "</div>" if re_line else ""}
</div>""")

    # 2. Market strip (3 rows)
    m = digest.get("market_indicators") or {}
    if m:
        sse = m.get("sse_composite") or {}
        hsi = m.get("hang_seng") or {}
        cny = m.get("usd_cny") or {}
        cnh = m.get("usd_cnh") or {}
        brent = m.get("brent") or {}
        cgb = m.get("cgb_10y") or {}
        cds = m.get("china_cds") or {}
        lpr = m.get("pboc_lpr") or {}
        gdp = m.get("gdp_yoy") or {}
        sections_pre.append(f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#1B2A4A;color:#fff;border-bottom:1px solid rgba(255,255,255,0.1);">
<tr>
<td width="33%" align="center" style="padding:12px 8px 10px;">
<div style="font-size:9px;text-transform:uppercase;letter-spacing:1.2px;opacity:0.55;">SSE Composite</div>
<div style="font-size:20px;font-weight:700;margin:2px 0;">{_esc(str(sse.get("value", "—")))}</div>
<div style="font-size:11px;">{_arrow(sse.get("change_pct", 0))}</div>
<div style="font-size:9px;opacity:0.4;margin-top:2px;">as of {now.strftime("%b %-d")}</div>
</td>
<td width="34%" align="center" style="padding:12px 8px 10px;border-left:1px solid rgba(255,255,255,0.12);border-right:1px solid rgba(255,255,255,0.12);">
<div style="font-size:9px;text-transform:uppercase;letter-spacing:1.2px;opacity:0.55;">Hang Seng</div>
<div style="font-size:20px;font-weight:700;margin:2px 0;">{_esc(str(hsi.get("value", "—")))}</div>
<div style="font-size:11px;">{_arrow(hsi.get("change_pct", 0))}</div>
<div style="font-size:9px;opacity:0.4;margin-top:2px;">as of {now.strftime("%b %-d")}</div>
</td>
<td width="33%" align="center" style="padding:12px 8px 10px;">
<div style="font-size:9px;text-transform:uppercase;letter-spacing:1.2px;opacity:0.55;">USD/CNY</div>
<div style="font-size:20px;font-weight:700;margin:2px 0;">{_esc(str(cny.get("value", "—")))}</div>
<div style="font-size:11px;">{_arrow(cny.get("change_pct", 0))}</div>
<div style="font-size:9px;opacity:0.4;margin-top:2px;">as of {now.strftime("%b %-d")}</div>
</td>
</tr>
</table>
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#162340;color:#fff;border-bottom:1px solid rgba(255,255,255,0.08);">
<tr>
<td width="25%" align="center" style="padding:8px;">
<div style="font-size:10px;text-transform:uppercase;letter-spacing:1px;opacity:0.6;">USD/CNH</div>
<div style="font-size:15px;font-weight:700;">{_esc(str(cnh.get("value", "—")))}</div>
<div style="font-size:10px;">{_arrow(cnh.get("change_pct", 0))}</div>
</td>
<td width="25%" align="center" style="padding:8px;border-left:1px solid rgba(255,255,255,0.1);">
<div style="font-size:10px;text-transform:uppercase;letter-spacing:1px;opacity:0.6;">Brent</div>
<div style="font-size:15px;font-weight:700;">${_esc(str(brent.get("value", "—")))}</div>
<div style="font-size:10px;">{_arrow(brent.get("change_pct", 0))}</div>
</td>
<td width="25%" align="center" style="padding:8px;border-left:1px solid rgba(255,255,255,0.1);">
<div style="font-size:10px;text-transform:uppercase;letter-spacing:1px;opacity:0.6;">10Y CGB</div>
<div style="font-size:15px;font-weight:700;">{_esc(str(cgb.get("value", "—")))}</div>
<div style="font-size:10px;">{_cds_arrow(cgb.get("change_bps", 0))}</div>
</td>
<td width="25%" align="center" style="padding:8px;border-left:1px solid rgba(255,255,255,0.1);">
<div style="font-size:10px;text-transform:uppercase;letter-spacing:1px;opacity:0.6;">China 5Y CDS</div>
<div style="font-size:15px;font-weight:700;">{_esc(str(cds.get("value", "—")))} bps</div>
<div style="font-size:10px;">{_cds_arrow(cds.get("change_bps", 0))}</div>
</td>
</tr>
</table>
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#0F1B30;color:#fff;border-bottom:1px solid rgba(255,255,255,0.08);">
<tr>
<td width="33%" align="center" style="padding:8px;">
<div style="font-size:10px;text-transform:uppercase;letter-spacing:1px;opacity:0.6;">PBOC 1Y LPR</div>
<div style="font-size:15px;font-weight:700;">{_esc(str(lpr.get("lpr_1y", "—")))}</div>
<div style="font-size:10px;opacity:0.6;">{_esc(str(lpr.get("last_change", "")))}</div>
</td>
<td width="34%" align="center" style="padding:8px;border-left:1px solid rgba(255,255,255,0.1);border-right:1px solid rgba(255,255,255,0.1);">
<div style="font-size:10px;text-transform:uppercase;letter-spacing:1px;opacity:0.6;">PBOC 5Y LPR</div>
<div style="font-size:15px;font-weight:700;">{_esc(str(lpr.get("lpr_5y", "—")))}</div>
<div style="font-size:10px;opacity:0.5;">benchmark</div>
</td>
<td width="33%" align="center" style="padding:8px;">
<div style="font-size:10px;text-transform:uppercase;letter-spacing:1px;opacity:0.6;">GDP YoY</div>
<div style="font-size:15px;font-weight:700;">{_esc(str(gdp.get("value", "—")))}</div>
<div style="font-size:10px;opacity:0.6;">{_esc(str(gdp.get("source", "NBS")))}{" · " + _esc(str(gdp.get("period", ""))) if gdp.get("period") else ""}</div>
</td>
</tr>
</table>""")

    # 2c. Δ Since Yesterday Bar — single-row chip strip of key deltas
    delta = digest.get("delta_since_yesterday") or {}
    items = delta.get("items") or []
    if items:
        chip_html = ""
        for it in items[:6]:
            chip_html += (f'<span style="display:inline-block;margin:0 4px 4px 0;'
                          f'padding:3px 10px;background:rgba(255,255,255,0.06);'
                          f'border:1px solid rgba(255,255,255,0.12);border-radius:14px;'
                          f'font-size:11px;color:rgba(255,255,255,0.85);'
                          f'font-family:Arial,sans-serif;">{_esc(it)}</span>')
        sections_pre.append(f"""
<div style="padding:10px 32px;background:#0a0f1e;color:#fff;border-bottom:1px solid rgba(255,255,255,0.08);" class="sec">
<span style="font-size:10px;text-transform:uppercase;letter-spacing:1.2px;color:rgba(255,255,255,0.55);margin-right:8px;vertical-align:middle;">Δ Since Yesterday</span>
{chip_html}
</div>""")

    # 3. Morning Memo
    memo = digest.get("morning_memo") or []
    if memo:
        memo_html = ""
        for idx, mi in enumerate(memo[:3], 1):
            t = _esc(mi) if isinstance(mi, str) else _esc(mi.get("text", "") if isinstance(mi, dict) else str(mi or ""))
            memo_html += f"""<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:10px;">
<tr>
<td width="28" style="vertical-align:top;padding-top:1px;">
<div style="width:22px;height:22px;border-radius:50%;background:#1B2A4A;color:#fff;font-size:11px;font-weight:700;text-align:center;line-height:22px;font-family:Arial,sans-serif;">{idx}</div>
</td>
<td style="vertical-align:top;padding-left:8px;">
<div style="font-size:14px;line-height:1.5;color:#222;font-family:Georgia,serif;">{t}</div>
</td>
</tr>
</table>"""
        sections_today.append(f"""
<div style="padding:16px 32px 12px;border-bottom:1px solid #E8E8E8;" class="sec">
<div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:2px;color:#D4AC0D;font-family:Arial,sans-serif;margin-bottom:12px;padding-bottom:6px;border-bottom:2px solid #D4AC0D;display:inline-block;">Today at a Glance</div>
{memo_html}
</div>""")

    # 4. Top Stories — heaviest visual weight in TODAY chapter
    stories = digest.get("top_stories") or []
    if stories:
        sh = ""
        for s in stories:
            cat = _esc(_str(s.get("category_tag", s.get("category", ""))))
            h = _esc(s.get("headline", ""))
            b_raw = s.get("body", "") or ""
            # Suppress body if it duplicates the headline (Google News RSS quirk)
            b = _esc(b_raw) if b_raw.strip() and b_raw.strip() != s.get("headline", "").strip() else ""
            sw = _esc(s.get("so_what", ""))
            pn = _esc(s.get("pattern_note", ""))
            sl = _esc(_clean_src(s.get("src_line", s.get("source", ""))))
            url = s.get("url", "")
            sh += f"""
<div class="story-card" style="margin-bottom:14px;padding:14px 16px;background:#fff;border-left:4px solid #1B2A4A;border-radius:2px;box-shadow:0 1px 3px rgba(0,0,0,0.06);">
<div style="font-size:10px;text-transform:uppercase;letter-spacing:1.2px;color:#2980B9;font-weight:700;margin-bottom:6px;">{cat}</div>
<h3 style="margin:0 0 8px 0;font-size:16px;line-height:1.4;color:#1B2A4A;font-family:Georgia,serif;font-weight:700;">{_link_or_text(h, url, style="color:#1B2A4A;text-decoration:none;")}</h3>
{"<p style='margin:0 0 10px 0;font-size:13px;line-height:1.55;color:#333;'>" + b + "</p>" if b else ""}
{"<p style='margin:0 0 6px 0;font-size:12px;line-height:1.5;color:#2980B9;'><strong>So what:</strong> " + _link_or_text(sw, url, style="color:#2980B9;text-decoration:underline;") + "</p>" if sw else ""}
{"<p style='margin:0 0 6px 0;font-size:12px;line-height:1.5;color:#5D6D7E;font-style:italic;'><strong>Pattern:</strong> " + pn + "</p>" if pn else ""}
<div style="font-size:10px;color:#999;margin-top:6px;">{sl}</div>
</div>"""
        sections_today.append(f'<div {_SEC}><span {_PILL("#2980B9")}>Top Stories</span>{sh}</div>')

    # 4b. Overnight Flash
    overnight = digest.get("overnight_items") or []
    if overnight:
        cat_colors = {"Cross-Strait": "#8E44AD", "PLA": "#C0392B"}
        fh = ""
        for it in overnight:
            cat_raw = _str(it.get("category", ""))
            cat = _esc(cat_raw)
            h = _esc(it.get("headline", ""))
            b = _esc(it.get("body_text", ""))
            src = _esc(_clean_src(it.get("source", "")))
            url = it.get("url", "")
            bar = cat_colors.get(cat_raw, "#1B2A4A")
            fh += f"""
<div style="margin-bottom:10px;padding-left:12px;border-left:3px solid {bar};">
<div style="font-size:11px;color:#C0392B;text-transform:uppercase;font-weight:600;">{cat} &middot; {src}</div>
<div style="font-size:13px;font-weight:600;color:#1B2A4A;">{_link_or_text(h, url)}</div>
<div style="font-size:12px;line-height:1.4;color:#555;">{b}</div>
</div>"""
        sections_today.append(f'<div {_SEC_BG("#FFF8F0")}><span {_PILL("#C0392B")}>&#9889; Overnight Flash</span>{fh}</div>')

    # 5. Key Stat
    stat = digest.get("key_stat") or {}
    if stat and stat.get("number"):
        sections_today.append(f"""
<div style="padding:12px 32px;background:#1B2A4A;color:#fff;border-bottom:1px solid #E0E0E0;text-align:center;" class="sec">
<div style="font-size:10px;text-transform:uppercase;letter-spacing:1.5px;opacity:0.6;margin-bottom:2px;">Stat of the Day</div>
<div class="key-stat-num" style="font-size:32px;font-weight:700;font-family:Georgia,serif;">{_esc(str(stat.get("number", "")))}</div>
<div style="font-size:12px;opacity:0.85;margin-top:2px;">{_esc(stat.get("label", ""))}</div>
<div style="font-size:11px;opacity:0.65;margin-top:4px;font-style:italic;">{_esc(stat.get("context", ""))}</div>
{"<div style='font-size:10px;opacity:0.45;margin-top:4px;'>Source: " + _esc(stat.get("source", "")) + "</div>" if stat.get("source") else ""}
</div>""")

    # 7. Satellite & Location Watch — CONSOLIDATED, only sites with real evidence today
    locations = digest.get("monitored_locations") or []
    if locations:
        badge_styles = {
            "activity": ("#D4AC0D", "#FDF6E3", "Active"),
            "elevated": ("#E67E22", "#FFF3E0", "Elevated"),
            "alert": ("#C0392B", "#FBE9E7", "Alert"),
        }
        # Filter: only sites with real evidence (non-normal status)
        active = [l for l in locations if l.get("status") not in ("normal", None, "")]
        total = len(locations)
        gz_baseline = sum(1 for l in locations
                          if l.get("block") == "gray_zone" and l.get("status") == "normal")
        hr_baseline = sum(1 for l in locations
                          if l.get("block") == "hidden_reach" and l.get("status") == "normal")

        if active:
            loc_cards = ""
            for i in range(0, len(active), 2):
                rc = ""
                for j in range(i, min(i + 2, len(active))):
                    loc = active[j]
                    nm = _esc(loc.get("name", ""))
                    st = loc.get("status", "activity")
                    note = _esc(loc.get("note", ""))
                    last = _esc(loc.get("last_source_date", ""))
                    dirn = loc.get("direction", "")
                    csis = _esc(loc.get("csis_product", ""))
                    block = loc.get("block", "")
                    block_label = ("Gray-Zone" if block == "gray_zone"
                                   else "Hidden Reach" if block == "hidden_reach"
                                   else "")
                    block_color = ("#2C3E50" if block == "gray_zone"
                                   else "#16A085" if block == "hidden_reach"
                                   else "#7F8C8D")
                    bc, bb, bl = badge_styles.get(st, ("#7F8C8D", "#F5F5F5", "Monitor"))
                    if dirn == "up":
                        bl += " &#9650;"
                    elif dirn == "down":
                        bl += " &#9660;"
                    badge = (f'<span style="display:inline-block;padding:2px 8px;'
                             f'border-radius:3px;font-size:9px;font-weight:700;color:#fff;'
                             f'background:{bc};letter-spacing:0.5px;">{bl}</span>')
                    block_tag = (f'<div style="font-size:9px;color:{block_color};'
                                 f'text-transform:uppercase;letter-spacing:0.6px;'
                                 f'font-weight:600;margin-bottom:3px;">{block_label}</div>'
                                 if block_label else "")
                    nh = (f'<div style="font-size:11px;line-height:1.4;color:#555;'
                          f'margin-top:4px;">{note}</div>' if note else "")
                    lh = (f'<div style="font-size:9px;color:#999;margin-top:3px;">'
                          f'&#9201; {last}</div>' if last else "")
                    ch = (f'<div style="font-size:9px;color:#aaa;margin-top:2px;'
                          f'font-family:monospace;">{csis}</div>' if csis else "")
                    rc += f"""<td style="width:50%;padding:4px;vertical-align:top;">
<div style="background:{bb};border-radius:4px;padding:10px 12px;border-left:3px solid {bc};">
{block_tag}
<div style="font-size:12px;font-weight:700;color:#1B2A4A;margin-bottom:4px;">{nm}</div>
<div style="margin-bottom:2px;">{badge}</div>
{nh}
{lh}
{ch}
</div>
</td>"""
                if len(active) - i == 1:
                    rc += '<td style="width:50%;padding:4px;"></td>'
                loc_cards += f"<tr>{rc}</tr>"

            baseline_footer = (f'<div style="font-size:10px;color:#999;margin-top:10px;'
                               f'padding-top:8px;border-top:1px solid #EEE;font-style:italic;">'
                               f'{gz_baseline} other Gray-Zone sites and {hr_baseline} Hidden Reach sites '
                               f'tracked at baseline · See <a href="https://amti.csis.org" '
                               f'style="color:#888;">CSIS AMTI</a>, '
                               f'<a href="https://chinapower.csis.org" style="color:#888;">China Power</a>, '
                               f'and <a href="https://features.csis.org/hiddenreach/" '
                               f'style="color:#888;">Hidden Reach</a></div>')

            sections_trackers.append(f"""<div {_SEC}>
<span {_PILL("#C0392B")}>Satellite &amp; Location Watch</span>
<div style="font-size:11px;color:#888;font-style:italic;margin-top:-2px;margin-bottom:8px;">New evidence from monitored areas of interest · {len(active)} of {total} sites flagged</div>
<table width="100%" cellpadding="0" cellspacing="0" border="0">{loc_cards}</table>
{baseline_footer}
</div>""")
        else:
            # All sites at baseline — single line
            sections_trackers.append(f"""<div {_SEC}>
<span {_PILL("#C0392B")}>Satellite &amp; Location Watch</span>
<div style="font-size:12px;color:#555;margin-top:6px;">All {total} monitored sites at baseline today. No new satellite imagery or activity flags.</div>
<div style="font-size:10px;color:#999;margin-top:6px;">Tracked: CSIS AMTI · China Power Project · Hidden Reach</div>
</div>""")

    # 8. PRC Government (2x2 + personnel + NPC + calendar)
    prc_gov = digest.get("prc_government") or []
    personnel = digest.get("personnel_changes") or []
    npc = digest.get("npc_politburo") or []
    calendar = digest.get("calendar_watch") or []
    if prc_gov or personnel or npc or calendar:
        # Single-column horizontal cards — no more 2x2 dead cell when count is odd
        gov_rows_html = ""
        for it in prc_gov:
            mn = _esc(it.get("ministry", ""))
            mzh = _esc(it.get("ministry_chinese", ""))
            act = _esc(it.get("action", ""))
            det = _esc(it.get("detail", ""))
            url = it.get("url", "")
            lbl = _esc(it.get("source_label", ""))
            off = _esc(it.get("official", ""))
            hdr_parts = []
            if mzh:
                hdr_parts.append(f'<span style="font-size:11px;color:#666;">{mzh}</span>')
            if mn:
                hdr_parts.append(f'<span style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:0.6px;">{mn}</span>')
            if off:
                hdr_parts.append(f'<span style="font-size:11px;color:#999;font-style:italic;">{off}</span>')
            hdr = ' <span style="color:#ccc;">·</span> '.join(hdr_parts)
            slink = ""
            if url and url != "#" and url.startswith("http"):
                sl = lbl if lbl else mn.lower()
                slink = f'<div style="margin-top:6px;font-size:11px;color:#888;">→ <a href="{_esc(url)}" style="color:#888;text-decoration:none;">{_esc(sl)} ↗</a></div>'
            elif lbl:
                slink = f'<div style="margin-top:6px;font-size:11px;color:#888;">→ {_esc(lbl)}</div>'
            gov_rows_html += f"""
<div style="margin-bottom:12px;padding:14px 16px;background:#FAFAF5;border-left:4px solid #C0392B;border-radius:2px;">
<div style="margin-bottom:8px;">{hdr}</div>
<div style="font-size:14px;font-weight:700;color:#1B2A4A;line-height:1.4;margin-bottom:6px;">{act}</div>
<div style="font-size:12px;line-height:1.55;color:#555;">{det}</div>
{slink}
</div>"""
        gov_grid = gov_rows_html if prc_gov else ""

        pers_html = ""
        if personnel:
            ac = {"appointed": "#27AE60", "nominated": "#2980B9", "resigned": "#E67E22",
                  "dismissed": "#C0392B", "confirmed": "#16A085", "rotated": "#8E44AD"}
            pi = ""
            for p in personnel:
                pos = _esc(p.get("position", ""))
                nm = _esc(p.get("name", ""))
                a = p.get("action", "appointed")
                det = _esc(p.get("detail", ""))
                pred = _esc(p.get("predecessor", "")) if p.get("predecessor") else ""
                ac_c = ac.get(a, "#1B2A4A")
                bg = f'<span style="display:inline-block;padding:1px 6px;border-radius:3px;font-size:10px;font-weight:600;color:#fff;background:{ac_c};text-transform:uppercase;margin-left:6px;">{_esc(a)}</span>'
                pl = f'<div style="font-size:11px;color:#888;margin-top:2px;">Succeeds: {pred}</div>' if pred else ""
                pi += f"""<div style="margin-bottom:10px;padding-left:12px;border-left:3px solid {ac_c};">
<div style="font-size:13px;font-weight:600;color:#1B2A4A;">{nm}{bg}</div>
<div style="font-size:12px;color:#555;">{pos}</div>
<div style="font-size:12px;line-height:1.4;color:#555;">{det}</div>
{pl}
</div>"""
            pers_html = f"""<div style="margin-top:16px;">
<div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:#2C3E50;margin-bottom:8px;padding-bottom:4px;border-bottom:1px solid #E8E8E8;">Personnel Changes</div>
{pi}
</div>"""

        npc_html = ""
        if npc:
            ni = ""
            for n in npc:
                body = _esc(n.get("body", ""))
                act = _esc(n.get("action", ""))
                det = _esc(n.get("detail", ""))
                url = n.get("url", "")
                ni += f"""<div style="margin-bottom:8px;padding-left:12px;border-left:3px solid #7F8C8D;">
<div style="font-size:11px;color:#7F8C8D;font-weight:600;text-transform:uppercase;">{body}</div>
<div style="font-size:13px;font-weight:600;color:#1B2A4A;">{_link_or_text(act, url)}</div>
<div style="font-size:12px;line-height:1.4;color:#555;">{det}</div>
</div>"""
            npc_html = f"""<div style="margin-top:16px;">
<div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:#7F8C8D;margin-bottom:8px;padding-bottom:4px;border-bottom:1px solid #E8E8E8;">NPC / Politburo Watch</div>
{ni}
</div>"""

        cal_html = ""
        if calendar:
            ci = ""
            for c in calendar:
                cm = _esc(c.get("month", ""))
                cd = _esc(str(c.get("day", "")))
                ch = _esc(c.get("headline", ""))
                cdet = _esc(c.get("detail", ""))
                ci += f"""<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-bottom:1px solid #E8E8E8;">
<tr>
<td width="50" style="padding:10px 10px 10px 0;text-align:center;vertical-align:top;">
<div style="font-size:10px;text-transform:uppercase;color:#888;letter-spacing:0.5px;">{cm}</div>
<div style="font-size:18px;font-weight:300;color:#1B2A4A;line-height:1.2;">{cd}</div>
</td>
<td style="padding:10px 0;vertical-align:top;">
<div style="font-size:13px;font-weight:600;color:#1B2A4A;margin-bottom:2px;">{ch}</div>
<div style="font-size:12px;line-height:1.4;color:#555;">{cdet}</div>
</td>
</tr>
</table>"""
            cal_html = f"""<div style="margin-top:20px;">
<div style="padding:8px 0;border-bottom:1px solid #1B2A4A;margin-bottom:4px;">
<span style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:#1B2A4A;">Upcoming</span>
</div>
{ci}
</div>"""

        ds = _esc(str(digest.get("digest_date", "")))
        sections_trackers.append(f"""
<div {_SEC}>
<span {_PILL("#C0392B")}>PRC Government</span> <span style="font-size:10px;color:#888;font-family:Arial,sans-serif;">State Council + Ministries &middot; {ds}</span>
<div style="padding-top:4px;">{gov_grid}{pers_html}{npc_html}{cal_html}</div>
</div>""")

    # 9. US-China Trade
    trade = digest.get("us_china_trade") or {}
    if trade:
        body = ""
        tt = trade.get("tariff_tracker") or {}
        if tt:
            h301 = _esc(str(tt.get("headline_section_301_rate", "")))
            ieepa = _esc(str(tt.get("ieepa_fentanyl_rate", "")))
            s122 = _esc(str(tt.get("section_122_surcharge", "")))
            lc = _esc(str(tt.get("last_change", "")))
            nt = _esc(str(tt.get("next_trigger", "")))
            s232 = tt.get("section_232_rates", {})
            sr = ""
            for sec, rate in s232.items():
                sr += f"""<tr style="border-bottom:1px solid #F0E0E0;">
<td style="padding:4px 6px 4px 0;font-size:11px;font-weight:600;color:#1B2A4A;">{_esc(sec.title())}</td>
<td style="padding:4px 6px;font-size:13px;font-weight:700;color:#C0392B;text-align:center;">{_esc(str(rate))}</td>
<td style="padding:4px 6px;font-size:9px;color:#888;text-transform:uppercase;">Section 232</td>
</tr>"""
            nl = f'<div style="margin-top:4px;font-size:10px;color:#2980B9;">Next trigger: {nt}</div>' if nt else ""
            body += f"""<div style="margin-bottom:16px;padding:12px 14px;background:#FFF5F5;border-radius:4px;border:1px solid #F0D0D0;">
<div style="font-size:10px;text-transform:uppercase;letter-spacing:1px;color:#C0392B;font-weight:600;margin-bottom:6px;">US Tariff Architecture · China</div>
<div style="margin-bottom:6px;">
<span style="font-size:11px;color:#666;">Section 301:</span> <span style="font-size:14px;font-weight:700;color:#C0392B;">{h301}</span> ·
<span style="font-size:11px;color:#666;">IEEPA fentanyl:</span> <span style="font-size:14px;font-weight:700;color:#C0392B;">{ieepa}</span> ·
<span style="font-size:11px;color:#666;">Section 122:</span> <span style="font-size:14px;font-weight:700;color:#E67E22;">{s122}</span>
</div>
{'<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:8px;border-top:1px solid #F0E0E0;">' + sr + '</table>' if sr else ''}
<div style="margin-top:8px;font-size:10px;color:#999;">{lc}</div>
{nl}
</div>"""

        el = trade.get("entity_list_tracker") or {}
        if el:
            tot = _esc(str(el.get("total_count", "")))
            adds = el.get("recent_adds_7day", [])
            recent = _esc(str(el.get("most_recent_add", "")))
            ah = ""
            for a in adds[:5]:
                if isinstance(a, dict):
                    en = _esc(a.get("entity_name", ""))
                    sec = _esc(a.get("sector", ""))
                    dt = _esc(a.get("date", ""))
                    ah += f"""<tr style="border-bottom:1px solid #E8EDF3;">
<td style="padding:4px 6px 4px 0;font-size:11px;font-weight:600;color:#1B2A4A;">{en}</td>
<td style="padding:4px 6px;font-size:10px;color:#666;">{sec}</td>
<td style="padding:4px 0 4px 6px;font-size:10px;color:#888;text-align:right;">{dt}</td>
</tr>"""
            at = f'<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:8px;">{ah}</table>' if ah else ""
            body += f"""<div style="margin-bottom:16px;padding:12px 14px;background:#F0F7FF;border-radius:4px;border:1px solid #D6E9F8;">
<div style="font-size:10px;text-transform:uppercase;letter-spacing:1px;color:#1B2A4A;font-weight:600;margin-bottom:6px;">BIS Entity List · China</div>
<div style="margin-bottom:4px;">
<span style="font-size:22px;font-weight:700;color:#1B2A4A;">{tot}</span>
<span style="font-size:11px;color:#888;"> PRC-located entities</span>
</div>
<div style="font-size:11px;color:#666;">Most recent: {recent}</div>
{at}
</div>"""


        cf = trade.get("cfius") or []
        if cf:
            cr = ""
            for c in cf[:4]:
                co = _esc(c.get("company", ""))
                sec = _esc(c.get("sector", ""))
                act = _esc(c.get("action", ""))
                dt = _esc(c.get("date", ""))
                cr += f"""<div style="margin-bottom:6px;padding-left:10px;border-left:2px solid #8E44AD;">
<div style="font-size:12px;font-weight:600;color:#1B2A4A;">{co} <span style="color:#888;font-weight:400;font-size:11px;">· {sec}</span></div>
<div style="font-size:11px;color:#555;">{act} <span style="color:#888;font-size:10px;">({dt})</span></div>
</div>"""
            body += f"""<div style="margin-bottom:16px;">
<div style="font-size:10px;text-transform:uppercase;letter-spacing:1px;color:#8E44AD;font-weight:600;margin-bottom:6px;">CFIUS Actions</div>
{cr}
</div>"""

        if body:
            sections_trackers.append(f'<div {_SEC}><span {_PILL("#C0392B")}>US-China Trade &amp; Sanctions</span>{body}</div>')

    # 10. Business & Economy
    biz = digest.get("business_economy") or []
    if biz:
        bh = ""
        for b in biz[:6]:
            h = _esc(b.get("headline", ""))
            bt = _esc(b.get("body_text", ""))
            url = b.get("url", "")
            src = _esc(b.get("source", ""))
            sec = _esc(b.get("sector", ""))
            comps = b.get("companies", [])
            cs = ", ".join(_esc(c) for c in comps) if comps else ""
            bh += f"""<div style="margin-bottom:10px;padding-left:12px;border-left:3px solid #D4AC0D;">
<div style="font-size:11px;color:#888;text-transform:uppercase;">{sec} · {src}{(' · ' + cs) if cs else ''}</div>
<div style="font-size:13px;font-weight:600;color:#1B2A4A;">{_link_or_text(h, url)}</div>
<div style="font-size:12px;line-height:1.4;color:#555;">{bt}</div>
</div>"""
        sections_wire.append(f'<div {_SEC}><span {_PILL("#7F8C8D")}>Business &amp; Economy</span>{bh}</div>')

    # 11. Indo-Pacific
    ip = digest.get("indo_pacific") or []
    if ip:
        rc = {"Cross-Strait": "#8E44AD", "Japan-China": "#2C3E50", "Philippines-China": "#2C3E50",
              "Australia-China": "#2C3E50", "India-China": "#2C3E50", "Korea-China": "#2C3E50",
              "Trilateral": "#2C3E50", "Indo-Pacific": "#7F8C8D"}
        ih = ""
        for it in ip[:6]:
            r = it.get("region_tag", "Indo-Pacific")
            bar = rc.get(r, "#7F8C8D")
            h = _esc(it.get("headline", ""))
            bt = _esc(it.get("body_text", ""))
            url = it.get("url", "")
            src = _esc(_clean_src(it.get("source", "")))
            ih += f"""<div style="margin-bottom:10px;padding-left:12px;border-left:3px solid {bar};">
<div style="font-size:11px;color:{bar};text-transform:uppercase;font-weight:600;">{_esc(r)} · {src}</div>
<div style="font-size:13px;font-weight:600;color:#1B2A4A;">{_link_or_text(h, url)}</div>
<div style="font-size:12px;line-height:1.4;color:#555;">{bt}</div>
</div>"""
        sections_wire.append(f'<div {_SEC}><span {_PILL("#7F8C8D")}>Indo-Pacific</span>{ih}</div>')

    # 12. Congressional Watch
    cw = digest.get("congressional_watch") or []
    if cw:
        ch = ""
        for c in cw:
            comm = _esc(c.get("committee", ""))
            act = _esc(c.get("action", ""))
            det = _esc(c.get("detail", ""))
            url = c.get("url", "")
            ch += f"""<div style="margin-bottom:10px;padding-left:12px;border-left:3px solid #2C3E50;">
<div style="font-size:11px;color:#7F8C8D;font-weight:600;text-transform:uppercase;">{comm}</div>
<div style="font-size:13px;font-weight:600;color:#1B2A4A;">{_link_or_text(act, url)}</div>
<div style="font-size:12px;line-height:1.4;color:#555;">{det}</div>
</div>"""
        sections_trackers.append(f'<div {_SEC}><span {_PILL("#C0392B")}>Congressional Watch</span>{ch}</div>')

    # 13. Expert Analysts
    opeds = digest.get("opeds_today") or []
    academics = digest.get("academic_today") or []
    if opeds or academics:
        body = ""
        if opeds:
            body += '<div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:#1B2A4A;margin-bottom:8px;padding-bottom:4px;border-bottom:1px solid #E8E8E8;">Op-Eds &amp; Think Tank Commentary</div>'
            for o in opeds[:6]:
                title = _esc(o.get("title") or o.get("headline", ""))
                src = _esc(o.get("source", ""))
                auth = _esc(o.get("authors", ""))
                ca = _esc(o.get("central_argument", ""))
                sm = _esc(o.get("summary", ""))
                ps = _esc(o.get("policy_so_what", ""))
                url = o.get("url", "")
                body += f"""<div style="margin-bottom:14px;padding:12px 14px;background:#fff;border-radius:2px;border-left:3px solid #1B2A4A;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
<div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:4px;">{src}{(' · ' + auth) if auth else ''}</div>
<div style="font-size:14px;font-weight:700;color:#1B2A4A;font-family:Georgia,serif;line-height:1.35;margin-bottom:6px;">{_link_or_text(title, url, style="color:#1B2A4A;text-decoration:none;")}</div>
{"<div style='font-size:12px;color:#444;font-style:italic;line-height:1.45;margin-bottom:5px;padding-left:8px;border-left:2px solid #D5D5D5;'>" + ca + "</div>" if ca else ""}
{"<div style='font-size:11px;line-height:1.5;color:#666;'>" + sm + "</div>" if sm else ""}
{"<div style='font-size:11px;color:#2980B9;margin-top:4px;font-weight:600;'>" + ps + "</div>" if ps else ""}
</div>"""
        if academics:
            body += '<div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:#8E44AD;margin:14px 0 8px 0;padding-bottom:4px;border-bottom:1px solid #E8E8E8;">Academic Journals</div>'
            for a in academics[:4]:
                title = _esc(a.get("title", ""))
                src = _esc(a.get("source", ""))
                tier = _esc(a.get("journal_tier", ""))
                auth = _esc(a.get("authors", ""))
                sm = _esc(a.get("summary", ""))
                url = a.get("url", "")
                body += f"""<div style="margin-bottom:12px;padding:12px 14px;background:#fff;border-radius:2px;border-left:3px solid #8E44AD;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
<div style="font-size:10px;color:#8E44AD;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:4px;">{src} · {tier}{(' · ' + auth) if auth else ''}</div>
<div style="font-size:13px;font-weight:700;color:#1B2A4A;font-family:Georgia,serif;line-height:1.35;margin-bottom:5px;">{_link_or_text(title, url, style="color:#1B2A4A;text-decoration:none;")}</div>
<div style="font-size:12px;line-height:1.5;color:#555;">{sm}</div>
</div>"""
        sections_analysis.append(f'<div {_SEC}><span {_PILL("#7F8C8D")}>Expert Analysts</span>{body}</div>')

    # 14. Public Sentiment — removed (low signal-to-noise)

    # 15. Social Statements
    stmts = digest.get("social_statements") or []
    if stmts:
        sh = ""
        for s in stmts[:6]:
            who = _esc(s.get("who", ""))
            ctx = _esc(s.get("handle_context", ""))
            pd = _esc(s.get("platform_date", ""))
            q = _esc(s.get("quote_text", ""))
            nt = _esc(s.get("analyst_note", ""))
            bc = _social_badge(s.get("badge_class", "sb-p"))
            url = s.get("url", "")
            src_link = ("<div style='font-size:10px;color:#888;margin-top:4px;'>" + _link_or_text("source", url, style="color:#888;text-decoration:underline;") + "</div>") if url and url != "#" and url.startswith("http") else ""
            sh += f"""<div style="margin-bottom:14px;padding:12px;background:#FAFAF5;border-radius:4px;border-left:3px solid {bc};">
<div style="font-size:12px;color:#888;text-transform:uppercase;letter-spacing:0.5px;">{pd}</div>
<div style="font-size:14px;font-weight:600;color:#1B2A4A;margin:2px 0;">{who} <span style="font-size:11px;color:#888;font-weight:400;">· {ctx}</span></div>
<blockquote style="margin:6px 0;padding:8px 12px;background:#fff;border-left:3px solid {bc};font-style:italic;font-size:13px;line-height:1.5;color:#333;font-family:Georgia,serif;">&ldquo;{q}&rdquo;</blockquote>
{"<div style='font-size:11px;color:#555;margin-top:4px;'><strong>Note:</strong> " + nt + "</div>" if nt else ""}
{src_link}
</div>"""
        sections_analysis.append(f'<div {_SEC}><span {_PILL("#7F8C8D")}>Social Statements</span>{sh}</div>')

    # 16. Also Today
    also = digest.get("also_today") or []
    if also:
        wc_ = {"Cross-Strait": "#8E44AD", "PLA": "#C0392B"}
        ah = ""
        for a in also[:6]:
            cr_ = _str(a.get("category", ""))
            c = _esc(cr_)
            h = _esc(a.get("headline", ""))
            b = _esc(a.get("body_text", ""))
            url = a.get("url", "")
            src = _esc(_clean_src(a.get("source", "")))
            bar = wc_.get(cr_, "#7F8C8D")
            ah += f"""<div style="margin-bottom:10px;padding-left:12px;border-left:3px solid {bar};">
<div style="font-size:10px;color:#888;text-transform:uppercase;">{c} &middot; {src}</div>
<div style="font-size:13px;font-weight:600;color:#1B2A4A;">{_link_or_text(h, url)}</div>
<div style="font-size:12px;line-height:1.4;color:#555;">{b}</div>
</div>"""
        sections_wire.append(f'<div {_SEC}><span {_PILL("#7F8C8D")}>Also Today / The Wire</span>{ah}</div>')

    # 17. On This Day
    otd = digest.get("on_this_day") or []
    if otd:
        oh = ""
        for it in otd[:1]:
            oh += f"""<div style="padding:12px 14px;background:#FAFAF5;border-radius:4px;border-left:3px solid #7F8C8D;">
<div style="font-size:11px;color:#7F8C8D;text-transform:uppercase;letter-spacing:0.5px;font-weight:600;">{_esc(it.get("date", ""))}</div>
<div style="font-size:14px;font-weight:600;color:#1B2A4A;font-family:Georgia,serif;margin:4px 0;">{_esc(it.get("event", ""))}</div>
<div style="font-size:12px;color:#555;font-style:italic;line-height:1.5;">{_esc(it.get("relevance", ""))}</div>
</div>"""
        sections_wire.append(f'<div {_SEC}><span {_PILL("#7F8C8D")}>On This Day</span>{oh}</div>')

    # 18. Sanctions Status footer — REMOVED. Will return when trade tracker is wired
    # with verifiable BIS/OFAC/DoD running totals. Placeholder text was misleading.

    # Footer
    sections_post.append(f"""
<div style="padding:18px 32px;background:#F5F5F5;text-align:center;font-size:11px;color:#888;font-family:Arial,sans-serif;line-height:1.6;">
CSIS Korea Chair · Daily China Brief<br>
Generated {gen_time} · Prepared by Andy Lim<br>
<a href="#top" style="color:#1B2A4A;text-decoration:none;">↑ Back to top</a>
</div>""")

    # Assemble with chapter dividers — Option B: existing dark bands serve as natural
    # transitions within TODAY (Key Stat closes) and into ANALYSIS (Xinhua Delta opens).
    # TRACKERS and WIRE get explicit chapter dividers.
    sections = (
        sections_pre +
        sections_today +
        sections_analysis +
        ([_chapter("TRACKERS")] if sections_trackers else []) + sections_trackers +
        ([_chapter("WIRE")] if sections_wire else []) + sections_wire +
        sections_post
    )

    body_html = "\n".join(s for s in sections if s)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>China Daily Brief</title>
<style>
body {{ margin:0; padding:0; background:#fff; font-family:Arial,sans-serif; color:#333; }}
.container {{ max-width:680px; margin:0 auto; background:#fff; }}
@media only screen and (max-width: 600px) {{
  .container {{ width:100% !important; }}
  .sec {{ padding-left:16px !important; padding-right:16px !important; }}
}}
</style>
</head>
<body>
<a name="top"></a>
<div class="container">
{body_html}
</div>
</body>
</html>"""


if __name__ == "__main__":
    import json
    with open("test_digest.json") as f:
        d = json.load(f)
    html = render_html(d)
    with open("preview.html", "w") as f:
        f.write(html)
    print(f"Rendered {len(html):,} bytes")
