"""
China Daily Brief — HTML Renderer
CSIS Korea Chair

Mirrors Daily-Korea-Digest visual language exactly:
- Navy #1B2A4A header + saturated CSIS palette
- Arial/Georgia stack (NOT v3.1 Libre Baskerville)
- Status pills (rounded), status badges (small rounded)
- Colored left-borders for category coding
- Sections organised by relationship: Top Stories, US-China, China & the World,
  Economy & Business; one data band; the BEIJING chapter (Propaganda Delta,
  What Beijing Is Saying, What Beijing Did, Voices, What Others Are Saying);
  the WIRE (Overnight Flash, Also Today); What We Are Watching to close
"""

import re as _re
from datetime import datetime, timezone
from urllib.parse import urlparse as _urlparse

import wordcount


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


_SEC = 'style="padding:20px 32px;border-bottom:1px solid #EBEBEB;" class="sec"'
_SEC_ALERT = 'style="padding:20px 32px;border-top:3px solid #C0392B;border-bottom:1px solid #EBEBEB;" class="sec"'

def _item_card(tag: str, source: str, headline: str, url: str, body: str = "",
               so_what: str = "", so_what_label: str = "So what",
               headline_size: str = "13px") -> str:
    """The one card every news section uses. Tag and source in grey small-caps,
    navy headline, body, optional so-what. Colour belongs to the section label,
    not to the item, so a page of twelve regions reads as one page."""
    tag_line = " &middot; ".join(x for x in (_esc(tag), _esc(_clean_src(source))) if x)
    sw = (f"<div style='font-size:12px;line-height:1.5;color:#555;font-style:italic;"
          f"margin-top:4px;'><strong style='color:#1B2A4A;font-style:normal;'>"
          f"{_esc(so_what_label)}:</strong> {_esc(so_what)}</div>") if so_what else ""
    return (f'<div style="margin-bottom:11px;padding-left:12px;border-left:3px solid #1B2A4A;">'
            f'<div style="font-size:9px;color:#6B7280;text-transform:uppercase;'
            f'letter-spacing:1px;font-weight:600;margin-bottom:2px;">{tag_line}</div>'
            f'<div style="font-size:{headline_size};font-weight:600;color:#1B2A4A;'
            f'line-height:1.4;">{_link_or_text(_esc(headline), url)}</div>'
            f'{("<div style=" + chr(34) + "font-size:12px;line-height:1.5;color:#555;margin-top:2px;" + chr(34) + ">" + _esc(body) + "</div>") if body else ""}'
            f'{sw}</div>')


def _sec_label(label: str, color: str = "#1B2A4A") -> str:
    """Section label — small-caps with rule, no background pill."""
    return (f'<div style="font-size:10px;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:2px;color:{color};font-family:Arial,sans-serif;'
            f'margin-bottom:14px;padding-bottom:8px;border-bottom:2px solid {color};">'
            f'{label}</div>')


def _word_count(d: dict) -> int:
    """The count shown in the header. Shares wordcount.py with the prompt target
    and the validator so the reader is not shown a fourth number."""
    return wordcount.count_words(d)


def _chapter(label: str) -> str:
    """Chapter divider — dark navy band with gold rule, white letterspaced label."""
    return f"""
<div style="padding:12px 32px;background:#1B2A4A;text-align:center;" class="sec dark-sec">
<div style="height:1px;background:rgba(212,172,13,0.4);margin-bottom:10px;"></div>
<span style="font-size:9px;font-family:Arial,sans-serif;color:rgba(255,255,255,0.65);text-transform:uppercase;letter-spacing:5px;font-weight:700;">{label}</span>
<div style="height:1px;background:rgba(212,172,13,0.4);margin-top:10px;"></div>
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
    sections_pre = []       # View-in-browser, header, bottom line
    sections_markets = []   # Market strip + Δ Since Yesterday (render below the news)
    sections_today = []     # Morning Memo, Top Stories, Overnight Flash, Key Stat
    sections_analysis = []  # Beijing's words and actions, experts, social statements
    sections_wire = []      # Business, Indo-Pacific, Congressional Watch, Also Today
    sections_close = []     # What We Are Watching (the forward look closes the brief)
    sections_post = []      # Footer

    # 0. Read online · Print/PDF · Archive
    pdf_url = digest.get("pdf_url", "")
    archive_url = digest.get("archive_url", "")
    if web_url or pdf_url or archive_url:
        links = []
        if web_url:
            links.append(f'<a href="{_esc(web_url)}" style="color:#2980B9;text-decoration:none;">Read online</a>')
        if pdf_url:
            links.append(f'<a href="{_esc(pdf_url)}" style="color:#2980B9;text-decoration:none;">Print / PDF</a>')
        if archive_url:
            links.append(f'<a href="{_esc(archive_url)}" style="color:#2980B9;text-decoration:none;">Archive</a>')
        sections_pre.append(f"""
<div style="background:#F0F0F0;padding:6px 32px;text-align:center;font-size:11px;color:#888;" class="sec no-print">
{" &nbsp;&middot;&nbsp; ".join(links)}
</div>""")

    # 1. Header
    sections_pre.append(f"""
<div style="background:#1B2A4A;color:#ffffff;padding:18px 32px 14px;" class="sec dark-sec">
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

    # 1b. The Bottom Line — the day's frame, in the model's own editor_note.
    # This field was generated and word-counted on every run since May and never
    # rendered, so the reader got twenty sections of facts and no lead. Every
    # digest worth reading (Axios "1 big thing", Politico's lead, Bloomberg's
    # opener) puts one of these above everything else.
    editor_note = _esc(str(digest.get("editor_note") or "").strip())
    if editor_note:
        sections_pre.append(f"""
<div style="padding:16px 32px;background:#FAFAF5;border-bottom:1px solid #EBEBEB;" class="sec">
<div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:2px;color:#C0392B;font-family:Arial,sans-serif;margin-bottom:6px;">The Bottom Line</div>
<div style="font-size:15px;line-height:1.55;color:#1B2A4A;font-family:Georgia,serif;">{editor_note}</div>
</div>""")

    # 2. Market strip. Built from what actually resolved, never from a fixed
    # grid. The old strip hard-coded nine tiles across three tables; four of the
    # nine indicators (10Y CGB, PBOC LPR, China 5Y CDS, GDP) have failed to fetch
    # on every recent run, so five of nine cells rendered as a bare em dash and
    # the section read as broken rather than as honest. Now: a tile appears only
    # when it has a number, the rows reflow to fill, and anything missing is named
    # once in a footnote. The market-honesty rule is unchanged — a figure that was
    # not fetched is still never invented — it just no longer costs the layout.
    m = digest.get("market_indicators") or {}
    if m:
        def _has(d):
            """A resolved indicator: present, not flagged unavailable, not a dash."""
            if not isinstance(d, dict) or d.get("unavailable"):
                return False
            v = d.get("value")
            return v not in (None, "", "—", "-")

        def _tile(label, value, sub, big=False):
            vs = "20px" if big else "15px"
            sub_html = (f'<div style="font-size:{"11px" if big else "10px"};'
                        f'opacity:0.75;margin-top:2px;">{sub}</div>' if sub else "")
            return (f'<div style="font-size:{"9px" if big else "10px"};'
                    f'text-transform:uppercase;letter-spacing:1.1px;opacity:0.55;">{label}</div>'
                    f'<div style="font-size:{vs};font-weight:700;margin:2px 0;">{value}</div>'
                    f'{sub_html}')

        def _row(tiles, bg, pad):
            if not tiles:
                return ""
            w = 100 // len(tiles)
            cells = ""
            for i, t in enumerate(tiles):
                border = ('border-left:1px solid rgba(255,255,255,0.12);' if i else "")
                cells += (f'<td width="{w}%" align="center" '
                          f'style="padding:{pad};{border}vertical-align:top;">{t}</td>')
            return (f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
                    f'class="dark-sec" style="background:{bg};color:#ffffff;'
                    f'border-bottom:1px solid rgba(255,255,255,0.1);">'
                    f'<tr>{cells}</tr></table>')

        as_of = now.strftime("%b %-d")
        missing = []

        # Row 1 — the headline markets, at full size.
        hero = []
        for key, label in (("sse_composite", "SSE Composite"),
                           ("hang_seng", "Hang Seng"),
                           ("usd_cny", "USD/CNY")):
            d = m.get(key) or {}
            if _has(d):
                hero.append(_tile(label, _esc(str(d.get("value"))),
                                  f'{_arrow(d.get("change_pct", 0))}'
                                  f'<div style="font-size:9px;opacity:0.45;margin-top:2px;">'
                                  f'as of {as_of}</div>', big=True))
            else:
                missing.append(label)

        # Row 2 — rates, credit and commodities.
        second = []
        d = m.get("usd_cnh") or {}
        if _has(d):
            second.append(_tile("USD/CNH", _esc(str(d.get("value"))), _arrow(d.get("change_pct", 0))))
        else:
            missing.append("USD/CNH")
        d = m.get("brent") or {}
        if _has(d):
            second.append(_tile("Brent", "$" + _esc(str(d.get("value"))), _arrow(d.get("change_pct", 0))))
        else:
            missing.append("Brent")
        d = m.get("cgb_10y") or {}
        if _has(d):
            second.append(_tile("10Y CGB", _esc(str(d.get("value"))), _cds_arrow(d.get("change_bps", 0))))
        else:
            missing.append("10Y CGB")
        d = m.get("china_cds") or {}
        if _has(d):
            second.append(_tile("China 5Y CDS", _esc(str(d.get("value"))) + " bps",
                                _cds_arrow(d.get("change_bps", 0))))
        else:
            missing.append("China 5Y CDS")
        lpr = m.get("pboc_lpr") or {}
        if not lpr.get("unavailable"):
            for fld, label in (("lpr_1y", "PBOC 1Y LPR"), ("lpr_5y", "PBOC 5Y LPR")):
                v = lpr.get(fld)
                if v not in (None, "", "—", "-"):
                    second.append(_tile(label, _esc(str(v)), _esc(str(lpr.get("last_change", "")))))
                else:
                    missing.append(label)
        else:
            missing.extend(["PBOC 1Y LPR", "PBOC 5Y LPR"])

        # Row 3 — the macro prints. collect._fetch_china_macro has gathered CPI,
        # PPI, manufacturing PMI and retail sales on every run since the pipeline
        # was built and nothing has ever rendered them, the same way editor_note
        # was generated and dropped. They are the numbers a China desk actually
        # asks for, and they are the ones that fill this strip.
        third = []
        d = m.get("gdp_yoy") or {}
        if _has(d):
            sub = " · ".join(x for x in (_esc(str(d.get("source") or "NBS")),
                                         _esc(str(d.get("period") or ""))) if x)
            third.append(_tile("GDP YoY", _esc(str(d.get("value"))), sub))
        else:
            missing.append("GDP")
        macro = m.get("china_macro") or {}
        for fld, label in (("cpi_yoy", "CPI YoY"), ("ppi_yoy", "PPI YoY"),
                           ("pmi_mfg", "Mfg PMI"), ("retail", "Retail Sales YoY")):
            v = macro.get(fld)
            if v not in (None, "", "—", "-"):
                third.append(_tile(label, _esc(str(v)), ""))

        strip = (_row(hero, "#1B2A4A", "12px 8px 10px")
                 + _row(second, "#162340", "9px 8px")
                 + _row(third, "#0F1B30", "9px 8px"))
        if strip:
            if missing:
                strip += (f'<div class="delta-sec" style="background:#0a0f1e;'
                          f'color:rgba(255,255,255,0.4);'
                          f'padding:5px 32px;font-size:9px;letter-spacing:0.4px;'
                          f'border-bottom:1px solid rgba(255,255,255,0.08);">'
                          f'Not fetched today: {_esc(", ".join(missing))} '
                          f'&middot; shown only when sourced, never carried forward</div>')
            sections_markets.append(strip)

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
        sections_markets.append(f"""
<div style="padding:10px 32px;background:#0a0f1e;color:#ffffff;border-bottom:1px solid rgba(255,255,255,0.08);" class="sec delta-sec">
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
<div style="padding:20px 32px;border-bottom:1px solid #EBEBEB;" class="sec">
<div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:2px;color:#D4AC0D;font-family:Arial,sans-serif;margin-bottom:14px;padding-bottom:8px;border-bottom:2px solid #D4AC0D;">Today at a Glance</div>
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
<div class="story-card" style="margin-bottom:12px;padding:14px 16px;background:#fff;border-left:3px solid #1B2A4A;border-bottom:1px solid #F0F0F0;">
<div style="font-size:9px;text-transform:uppercase;letter-spacing:1.5px;color:#888;font-weight:700;margin-bottom:6px;">{cat}</div>
<h3 style="margin:0 0 8px 0;font-size:16px;line-height:1.4;color:#1B2A4A;font-family:Georgia,serif;font-weight:700;">{_link_or_text(h, url, style="color:#1B2A4A;text-decoration:none;")}</h3>
{"<p style='margin:0 0 10px 0;font-size:13px;line-height:1.55;color:#444;'>" + b + "</p>" if b else ""}
{"<p style='margin:0 0 6px 0;font-size:12px;line-height:1.5;color:#555;font-style:italic;'><strong style='color:#1B2A4A;font-style:normal;'>So what:</strong> " + _link_or_text(sw, url, style="color:#555;text-decoration:underline;") + "</p>" if sw else ""}
{"<p style='margin:0 0 6px 0;font-size:12px;line-height:1.5;color:#777;font-style:italic;'><strong style='color:#555;font-style:normal;'>Pattern:</strong> " + pn + "</p>" if pn else ""}
<div style="font-size:10px;color:#aaa;margin-top:6px;text-transform:uppercase;letter-spacing:0.5px;">{sl}</div>
</div>"""
        sections_today.append(f'<div {_SEC}>{_sec_label("Top Stories")}{sh}</div>')

    # 4a. US–China. One format for the whole relationship: trade, export
    # controls, sanctions, CFIUS, diplomacy, military, Congress. This replaces
    # the tracker tables (a tariff stack, an entity-list count, a CFIUS list
    # and a deals list, four sub-formats in one section) that were hard to read
    # and rebuilt from stale baselines. Each item is news, tagged by instrument.
    usc = digest.get("us_china") or []
    if usc:
        uh = "".join(_item_card(it.get("instrument", ""), it.get("source", ""),
                                it.get("headline", ""), it.get("url", ""),
                                it.get("body_text", ""), headline_size="14px")
                     for it in usc if isinstance(it, dict))
        sections_today.append(f'<div {_SEC}>{_sec_label("US&ndash;China")}{uh}</div>')

    # 4b. China & the World. Everyone except the United States, region-tagged,
    # with a Cross-Strait item guaranteed by the prompt and Korea and Japan
    # given standing weight for this readership. Replaces Indo-Pacific (Asia
    # only) and the standalone Korea section: for a brief read by NSC, State,
    # Pentagon and Select Committee staff a Korea-only section reads parochial,
    # while a China-Korea story here sits beside the Russia and EU items it
    # competes with for attention.
    cw = digest.get("china_world") or []
    if cw:
        wh = "".join(_item_card(it.get("region", ""), it.get("source", ""),
                                it.get("headline", ""), it.get("url", ""),
                                it.get("body_text", ""), headline_size="14px")
                     for it in cw if isinstance(it, dict))
        sections_today.append(f'<div {_SEC}>{_sec_label("China &amp; the World")}{wh}</div>')

    # 4c. Overnight Flash. The residual tier: important items that fit none of
    # the relationship sections. It leads the wire rather than sitting under
    # the top stories, because the sections above it are organised by
    # relationship and this one is organised by time.
    overnight = digest.get("overnight_items") or []
    if overnight:
        fh = "".join(_item_card(_str(it.get("category", "")), it.get("source", ""),
                                it.get("headline", ""), it.get("url", ""),
                                it.get("body_text", ""))
                     for it in overnight if isinstance(it, dict))
        sections_wire.append(f'<div {_SEC}>{_sec_label("Overnight Flash")}{fh}</div>')

    # 5. Key Stat. Rendered as the first row of the market band, so the page
    # has one dark data band instead of two.
    stat = digest.get("key_stat") or {}
    if stat and stat.get("number"):
        stat_html = f"""
<div style="padding:14px 32px 12px;background:#1B2A4A;color:#ffffff;text-align:center;border-bottom:1px solid rgba(255,255,255,0.12);" class="sec dark-sec">
<div style="font-size:9px;text-transform:uppercase;letter-spacing:1.5px;color:rgba(255,255,255,0.55);margin-bottom:2px;">Stat of the Day</div>
<div class="key-stat-num" style="font-size:30px;font-weight:700;font-family:Georgia,serif;color:#ffffff;line-height:1.1;">{_esc(str(stat.get("number", "")))}</div>
<div style="font-size:12px;color:rgba(255,255,255,0.85);margin-top:3px;">{_esc(stat.get("label", ""))}</div>
<div style="font-size:11px;color:rgba(255,255,255,0.6);margin-top:3px;font-style:italic;">{_esc(stat.get("context", ""))}</div>
{"<div style='font-size:9px;color:rgba(255,255,255,0.4);margin-top:3px;'>Source: " + _esc(stat.get("source", "")) + "</div>" if stat.get("source") else ""}
</div>"""
        sections_markets.insert(0, stat_html)

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
<div style="margin-bottom:12px;padding:12px 14px;border-left:3px solid #1B2A4A;border-bottom:1px solid #F0F0F0;">
<div style="margin-bottom:6px;">{hdr}</div>
<div style="font-size:14px;font-weight:700;color:#1B2A4A;line-height:1.4;margin-bottom:5px;">{act}</div>
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
            cal_html = ci

        ds = _esc(str(digest.get("digest_date", "")))
        if gov_grid or pers_html or npc_html:
            sections_analysis.append(f"""
<div {_SEC}>
{_sec_label("What Beijing Did")}
<div style="font-size:10px;color:#aaa;text-transform:uppercase;letter-spacing:1px;margin-top:-10px;margin-bottom:14px;">State Council + Ministries{(" · " + ds) if ds else ""}</div>
{gov_grid}{pers_html}{npc_html}
</div>""")
        # The calendar is a forward look, so it closes the brief rather than
        # sitting halfway down inside a government section.
        if cal_html:
            sections_close.append(f'<div {_SEC}>{_sec_label("What We Are Watching")}{cal_html}</div>')

    # 10. Economy & Business — inside China.
    biz = digest.get("business_economy") or []
    if biz:
        bh = ""
        for b in biz:
            if not isinstance(b, dict):
                continue
            comps = [str(c) for c in (b.get("companies") or [])[:3]]
            tag = " / ".join(x for x in (str(b.get("sector") or ""), ", ".join(comps)) if x)
            bh += _item_card(tag, b.get("source", ""), b.get("headline", ""),
                             b.get("url", ""), b.get("body_text", ""))
        sections_today.append(f'<div {_SEC}>{_sec_label("Economy &amp; Business")}{bh}</div>')

    # 13. Voices — the only analysis section. Op-eds and think-tank arguments
    # from the watch-listed experts, US and China-based. Academic journal
    # pieces no longer have a section of their own: a daily brief is not the
    # place for them unless one says something a policymaker acts on this week,
    # in which case the prompt lets it in here.
    opeds = digest.get("opeds_today") or []
    if opeds:
        body = ""
        for o in opeds[:5]:
            title = _esc(o.get("title") or o.get("headline", ""))
            src = _esc(o.get("source", ""))
            auth = _esc(o.get("authors", ""))
            ca = _esc(o.get("central_argument", ""))
            ps = _esc(o.get("policy_so_what", ""))
            url = o.get("url", "")
            cb = ('<span style="margin-left:6px;padding:1px 6px;border-radius:3px;font-size:9px;'
                  'background:#EEF2F7;color:#1B2A4A;letter-spacing:0.5px;">CHINA-BASED</span>'
                  if o.get("china_based") else "")
            body += f"""<div style="margin-bottom:12px;padding:12px 14px;background:#fff;border-left:3px solid #D4AC0D;border-bottom:1px solid #F0F0F0;">
<div style="font-size:9px;color:#6B7280;text-transform:uppercase;letter-spacing:1px;font-weight:600;margin-bottom:3px;">{src}{(' &middot; ' + auth) if auth else ''}{cb}</div>
<div style="font-size:14px;font-weight:700;color:#1B2A4A;font-family:Georgia,serif;line-height:1.35;margin-bottom:5px;">{_link_or_text(title, url, style="color:#1B2A4A;text-decoration:none;")}</div>
{"<div style='font-size:12px;color:#444;line-height:1.5;'>" + ca + "</div>" if ca else ""}
{"<div style='font-size:11px;color:#555;margin-top:4px;font-style:italic;'><strong style='color:#1B2A4A;font-style:normal;'>For policy:</strong> " + ps + "</div>" if ps else ""}
</div>"""
        sections_analysis.append(f'<div {_SEC}>{_sec_label("Voices")}{body}</div>')

    # 14. Public Sentiment — removed (low signal-to-noise)

    # 14a. Propaganda Delta — reading Xinhua, People's Daily and Global Times.
    # The module docstring has promised this panel since the file was written and
    # it was never built: xinhua_delta is generated on every run, counted toward
    # the word total (wordcount.DELTA_FIELDS) and dropped by the renderer, the
    # third field to have that happen after editor_note and china_macro. It is
    # the section no wire service carries — doctrinal phrase movement and what
    # Beijing conspicuously stopped saying — so it leads the Beijing block.
    xd = digest.get("xinhua_delta") or {}
    if isinstance(xd, dict) and any(xd.get(k) for k in
                                    ("bottom_line", "propaganda_focus", "xi_activity",
                                     "peoples_daily_front_page", "key_phrase_changes",
                                     "doctrinal_shift", "notable_omissions",
                                     "global_times_editorial", "key_quotes")):
        def _line(label, value, color="rgba(255,255,255,0.9)"):
            if not value:
                return ""
            if isinstance(value, (list, tuple)):
                value = ", ".join(str(v) for v in value if v)
                if not value:
                    return ""
            return (f'<div style="margin-bottom:8px;">'
                    f'<span style="font-size:9px;text-transform:uppercase;'
                    f'letter-spacing:1.2px;color:rgba(255,255,255,0.45);">{label}</span>'
                    f'<div style="font-size:12px;line-height:1.5;color:{color};'
                    f'margin-top:2px;">{_esc(str(value))}</div></div>')

        body = ""
        bl = str(xd.get("bottom_line") or "").strip()
        if bl:
            body += (f'<div style="font-size:14px;line-height:1.55;color:#ffffff;'
                     f'font-family:Georgia,serif;margin-bottom:14px;'
                     f'padding-bottom:12px;border-bottom:1px solid rgba(255,255,255,0.15);">'
                     f'{_esc(bl)}</div>')

        # Doctrinal phrase movement — the distinctive part, so it renders as chips.
        chips = ""
        for ph in (xd.get("key_phrase_changes") or [])[:5]:
            if not isinstance(ph, dict):
                continue
            phrase = _esc(str(ph.get("phrase", "")))
            lbl = _esc(str(ph.get("delta_label", "")))
            if not phrase:
                continue
            up = "\u2191" in lbl or "new" in lbl.lower()
            down = "\u2193" in lbl
            col = "#E8B84B" if up else "#7FB3D5" if down else "rgba(255,255,255,0.75)"
            chips += (f'<span style="display:inline-block;margin:0 5px 5px 0;'
                      f'padding:3px 9px;background:rgba(255,255,255,0.07);'
                      f'border:1px solid rgba(255,255,255,0.14);border-radius:12px;'
                      f'font-size:11px;color:{col};">{phrase}'
                      f'{(" &middot; " + lbl) if lbl else ""}</span>')
        if chips:
            body += (f'<div style="margin-bottom:10px;">'
                     f'<div style="font-size:9px;text-transform:uppercase;'
                     f'letter-spacing:1.2px;color:rgba(255,255,255,0.45);'
                     f'margin-bottom:5px;">Doctrinal Phrase Movement</div>{chips}</div>')

        body += _line("Xi Today", xd.get("xi_activity"))
        body += _line("People&#39;s Daily Front Page", xd.get("peoples_daily_front_page"))
        body += _line("Propaganda Focus", xd.get("propaganda_focus"))
        body += _line("Global Times Editorial", xd.get("global_times_editorial"))
        # A doctrinal shift or a conspicuous silence is the highest-value signal
        # in the whole panel, so it is coloured, not buried in the run of lines.
        body += _line("Doctrinal Shift", xd.get("doctrinal_shift"), color="#E8B84B")
        body += _line("Notable Omissions", xd.get("notable_omissions"), color="#E8B84B")

        for q in (xd.get("key_quotes") or [])[:1]:
            if not isinstance(q, dict) or not q.get("quote"):
                continue
            attrib = " &middot; ".join(x for x in (_esc(str(q.get("speaker") or "")),
                                                   _esc(str(q.get("source_article") or ""))) if x)
            attrib_html = ('<div style="font-size:10px;color:rgba(255,255,255,0.5);'
                           f'margin-top:5px;">{attrib}</div>') if attrib else ""
            body += (f'<div style="margin-top:12px;padding:10px 12px;'
                     f'background:rgba(255,255,255,0.05);border-left:3px solid #E8B84B;">'
                     f'<div style="font-size:13px;line-height:1.55;color:#ffffff;'
                     f'font-family:Georgia,serif;font-style:italic;">'
                     f'&ldquo;{_esc(str(q.get("quote")))}&rdquo;</div>'
                     f'{attrib_html}</div>')

        vol = _esc(str(xd.get("output_volume") or ""))
        flag = ('<span style="display:inline-block;margin-left:8px;padding:2px 8px;'
                'border-radius:3px;font-size:9px;font-weight:700;letter-spacing:0.5px;'
                'background:#C0392B;color:#ffffff;">WATCH</span>'
                if xd.get("watch_flag") else "")
        foot = (f'<div style="margin-top:12px;padding-top:10px;'
                f'border-top:1px solid rgba(255,255,255,0.12);font-size:10px;'
                f'color:rgba(255,255,255,0.45);">{vol}{flag}</div>' if (vol or flag) else "")

        if body:
            sections_analysis.append(f"""
<div style="padding:20px 32px;background:#14213D;border-bottom:1px solid rgba(255,255,255,0.1);" class="sec dark-sec">
<div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:2px;color:#E8B84B;font-family:Arial,sans-serif;margin-bottom:14px;padding-bottom:8px;border-bottom:2px solid #E8B84B;">Propaganda Delta</div>
{body}{foot}
</div>""")

    # 14b. What Beijing Is Saying — the PRC government's own words today.
    # Sits ahead of Social Statements (which carries everyone else) so the
    # reader gets the official line before the reactions to it.
    official = digest.get("official_line") or []
    if official:
        tone_color = {"warning": "#C0392B", "firm": "#B7770D", "conciliatory": "#27AE60",
                      "routine": "#7F8C8D"}
        oh = ""
        for o in official[:8]:
            body = _esc(o.get("body", ""))
            body_zh = _esc(o.get("body_chinese", ""))
            speaker = _esc(o.get("speaker", ""))
            role = _esc(o.get("role", ""))
            topic = _esc(o.get("topic", ""))
            stmt = _esc(o.get("statement", ""))
            zh = _esc(o.get("original_zh") or "")
            ctx = _esc(o.get("context", ""))
            tone = str(o.get("tone", "routine") or "routine").lower()
            to = _esc(o.get("addressed_to", ""))
            tc = tone_color.get(tone, "#7F8C8D")
            url = o.get("url", "")
            src = _esc(_clean_src(o.get("source", "")))
            src_link = ("<div style='font-size:10px;color:#888;margin-top:4px;'>" +
                        _link_or_text(src or "source", url, style="color:#888;text-decoration:underline;") +
                        "</div>") if url and url.startswith("http") else (
                        f"<div style='font-size:10px;color:#888;margin-top:4px;'>{src}</div>" if src else "")
            head = f"{body_zh} · {body}" if body_zh else body
            who = f"{speaker} <span style='font-size:11px;color:#888;font-weight:400;'>· {role}</span>" if speaker else role
            oh += f"""<div style="margin-bottom:14px;padding:12px;background:#FAFAF5;border-radius:4px;border-left:3px solid {tc};">
<table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
<td style="font-size:12px;color:#1B2A4A;font-weight:700;letter-spacing:0.3px;">{head}</td>
<td align="right" style="font-size:10px;text-transform:uppercase;letter-spacing:1px;color:{tc};font-weight:700;">{_esc(tone)}{(" · to " + to) if to else ""}</td>
</tr></table>
<div style="font-size:13px;font-weight:600;color:#1B2A4A;margin:4px 0 2px;font-family:Georgia,serif;">{topic}</div>
{"<div style='font-size:12px;color:#555;'>" + who + "</div>" if (speaker or role) else ""}
<blockquote style="margin:6px 0;padding:8px 12px;background:#fff;border-left:3px solid {tc};font-style:italic;font-size:13px;line-height:1.5;color:#333;font-family:Georgia,serif;">&ldquo;{stmt}&rdquo;</blockquote>
{"<div style='font-size:12px;color:#666;line-height:1.5;margin:2px 0 0 12px;'>" + zh + "</div>" if zh else ""}
{"<div style='font-size:11px;color:#555;margin-top:4px;'><strong>Context:</strong> " + ctx + "</div>" if ctx else ""}
{src_link}
</div>"""
        sections_analysis.append(
            f'<div {_SEC}>{_sec_label("What Beijing Is Saying", "#C0392B")}{oh}</div>')

    # 15. Social Statements
    stmts = digest.get("social_statements") or []
    if stmts:
        sh = ""
        for s in stmts[:4]:
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
        sections_analysis.append(f'<div {_SEC}>{_sec_label("What Others Are Saying")}{sh}</div>')

    # 16. Also Today — the one-line wire.
    also = digest.get("also_today") or []
    if also:
        ah = "".join(_item_card(_str(a.get("category", "")), a.get("source", ""),
                                a.get("headline", ""), a.get("url", ""),
                                a.get("body_text", ""))
                     for a in also[:8] if isinstance(a, dict))
        sections_wire.append(f'<div {_SEC}>{_sec_label("Also Today")}{ah}</div>')

    # 18. Sanctions Status footer — REMOVED. Will return when trade tracker is wired
    # with verifiable BIS/OFAC/DoD running totals. Placeholder text was misleading.

    # Footer (with the auto-generation disclaimer the Japan brief carries)
    sections_post.append(f"""
<div style="padding:20px 32px;background:#1B2A4A;text-align:center;" class="sec dark-sec">
<div style="font-size:9px;text-transform:uppercase;letter-spacing:2px;color:rgba(255,255,255,0.45);font-family:Arial,sans-serif;line-height:2;">
CSIS Korea Chair &nbsp;·&nbsp; China Daily Brief &nbsp;·&nbsp; Generated {gen_time}
</div>
<div style="font-size:10px;color:rgba(255,255,255,0.55);font-family:Arial,sans-serif;line-height:1.6;max-width:520px;margin:8px auto 0;">
This brief is generated automatically from {_esc(str(digest.get("source_count") or "the day's"))} collected sources and may contain errors. Every item links to its source; check the source before citing. Prepared by Andy Lim, CSIS Korea Chair.
</div>
<a href="#top" style="font-size:10px;color:rgba(255,255,255,0.4);text-decoration:none;letter-spacing:1px;">&#8593; Back to top</a>
</div>""")

    # Assembly. Organised by RELATIONSHIP, not by time: the frame, the biggest
    # stories, then US–China, China & the World, Economy & Business; the data
    # band; Beijing's propaganda, words and actions; the voices; the wire; and
    # the forward look to close. Two chapter dividers, not four.
    sections = (
        sections_pre +
        sections_today +
        sections_markets +
        ([_chapter("BEIJING")] if sections_analysis else []) + sections_analysis +
        ([_chapter("WIRE")] if sections_wire else []) + sections_wire +
        sections_close +
        sections_post
    )

    body_html = "\n".join(s for s in sections if s)
    return f"""<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<meta name="supported-color-schemes" content="light">
<title>China Daily Brief</title>
<style>
:root {{ color-scheme: light; }}
body {{ margin:0; padding:0; background:#ffffff; font-family:Arial,sans-serif; color:#333333; -webkit-text-size-adjust:100%; }}
.container {{ max-width:680px; margin:0 auto; background:#ffffff; }}
/* Lock dark sections — prevent iOS Mail light-mode override */
.dark-sec {{ background-color:#1B2A4A !important; color:#ffffff !important; }}
.dark-sec * {{ color:#ffffff !important; }}
.dark-sec a {{ color:#D4AC0D !important; }}
.mid-sec {{ background-color:#162340 !important; color:#ffffff !important; }}
.deep-sec {{ background-color:#0F1B30 !important; color:#ffffff !important; }}
.delta-sec {{ background-color:#0a0f1e !important; color:#ffffff !important; }}
@media only screen and (max-width: 600px) {{
  .container {{ width:100% !important; }}
  .sec {{ padding-left:16px !important; padding-right:16px !important; }}
  h1 {{ font-size:22px !important; }}
  .key-stat-num {{ font-size:26px !important; }}
  .market-val {{ font-size:16px !important; }}
}}
@media print {{
  .no-print {{ display: none !important; }}
  .sec {{ page-break-inside: avoid; }}
  a {{ color: #1B2A4A !important; text-decoration: none !important; }}
  body {{ background: #fff !important; }}
}}
</style>
</head>
<body style="margin:0;padding:0;background:#ffffff;">
<a name="top"></a>
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff;">
<tr><td align="center">
<div class="container">
{body_html}
</div>
</td></tr>
</table>
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
