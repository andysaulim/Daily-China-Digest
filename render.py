"""
China Daily Brief — HTML Renderer
CSIS China Programs

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



# Grounds already dark in both schemes, or white type on an accent fill:
# these need no dark variant and the coverage guard skips them.
_DARK_EXEMPT = {
    "#041a33", "#0a0f1e", "#0d1b2a", "#0e1c33", "#0f1b30", "#121212",
    "#162340", "#1a1a1a", "#1b2a4a", "#1e2126", "#262a30", "#2e3644",
    "#051f3d", "#6e0019", "#bc002d", "#de2910", "#17798c",
}


def _check_dark_coverage(html: str) -> list[str]:
    """Every inline colour in the output must have a dark counterpart.

    Hand-maintained dark rules drift silently: a colour added to the brief
    keeps its light value in dark mode, so a reader sees near-black type on a
    near-black ground and nothing catches it, because absent CSS is not an
    error. This is that catch, and the render test calls it.
    """
    import re as _re
    body = html.split("<body", 1)[-1]
    _m = _re.search(r"prefers-color-scheme:\s*dark", html)
    dark = html[_m.start():_m.start() + 20000] if _m else ""
    covered = {c.lower() for c in _re.findall(r"#[0-9A-Fa-f]{3,6}", dark)} | _DARK_EXEMPT
    missing = []
    for hexv in {c.lower() for c in
                 _re.findall(r"(?<!-)color:\s*(#[0-9A-Fa-f]{3,6})", body)}:
        if hexv not in covered:
            missing.append(f"text colour {hexv} has no dark rule")
    for hexv in {c.lower() for c in
                 _re.findall(r"background(?:-color)?:\s*(#[0-9A-Fa-f]{3,6})", body)}:
        if hexv not in covered:
            missing.append(f"background {hexv} has no dark rule")
    return sorted(missing)



def _emphasis(text: str) -> str:
    """Turn the model's **bold** and *italic* marks into tags, after escaping.

    Names and figures are what a reader scans a policy brief for, so the
    prompt asks for a person's name in **double asterisks** on first mention
    and a quantity in *single* ones. The model cannot emit HTML — every field
    goes through _esc() first — so this converts a narrow, fixed convention
    afterwards. Anything that is not one of these two exact shapes stays
    literal text, which is what keeps the escaping meaningful.
    """
    import re as _re
    text = _re.sub(r"\*\*(?!\s)([^*]{1,80}?)(?<!\s)\*\*",
                   r'<strong style="font-weight:700;">\1</strong>', text)
    text = _re.sub(r"(?<![*\w])\*(?!\s)([^*]{1,60}?)(?<!\s)\*(?![*\w])",
                   r"<em>\1</em>", text)
    return text


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
               headline_size: str = "13px") -> str:
    """The one card every news section uses. Tag and source in grey small-caps,
    navy headline, body. Colour belongs to the section label,
    not to the item, so a page of twelve regions reads as one page."""
    tag_line = " &middot; ".join(x for x in (_esc(tag), _esc(_clean_src(source))) if x)
    return (f'<div style="margin-bottom:11px;padding-left:12px;border-left:3px solid #1B2A4A;">'
            f'<div style="font-size:10px;color:#6B7280;text-transform:uppercase;'
            f'letter-spacing:1px;font-weight:600;margin-bottom:2px;">{tag_line}</div>'
            f'<div style="font-size:{headline_size};font-weight:600;color:#1B2A4A;'
            f'line-height:1.4;">{_link_or_text(_emphasis(_esc(headline)), url)}</div>'
            f'{("<div style=" + chr(34) + "font-size:13px;line-height:1.5;color:#555;margin-top:2px;" + chr(34) + ">" + _emphasis(_esc(body)) + "</div>") if body else ""}'
            f'</div>')


INK  = "#1A222E"
MUTE = "#6B7280"
PRC_RED = "#DE2910"
# The same red darkened for use as type. On the tinted glance and stat panels
# the flag red falls just under 4.5:1; this clears it without reading as a
# different colour.
PRC_RED_TEXT = "#C82409"


RING_ON_DARK = "#EF4027"   # the accent, lightened to read on the black bar

def _subhead(text: str) -> str:
    """A group label inside a section.

    Also Today ran every category together, so it read as one
    undifferentiated stream. One heading per subject beats a category
    repeated in grey on every row.
    """
    return (f'<div style="font-family:Arial,sans-serif;font-size:11px;font-weight:700;'
            f'text-transform:uppercase;letter-spacing:1.5px;color:#55607A;'
            f'margin:18px 0 9px;padding-bottom:5px;border-bottom:1px solid #E4E7EB;">'
            f'{text}</div>')


def _compact_row(cat: str, headline: str, url: str, src: str, body: str = "") -> str:
    """One wire item, in the same shape as every other news item in the brief.

    This was a two-column table: a category cell on the left, headline and a
    grey meta line on the right. It read as a different kind of object from
    the sections around it — the eye had to change mode to scan it, which is
    the opposite of what a wire is for.

    It is now the house item: a rule down the left, TAG · SOURCE in small grey
    caps, the headline, then the body. Same as the sections that read tightest,
    so The Wire scans like the rest of the brief instead of like a table.
    """
    tag_line = " &middot; ".join(x for x in (cat, src) if x)
    return (f'<div style="margin-bottom:11px;padding-left:12px;'
            f'border-left:3px solid {PRC_RED};">'
            + (f'<div style="font-family:Arial,sans-serif;font-size:10px;color:{MUTE};'
               f'text-transform:uppercase;letter-spacing:1px;font-weight:600;'
               f'margin-bottom:2px;">{tag_line}</div>' if tag_line else "")
            + f'<div style="font-family:Georgia,serif;font-size:14px;font-weight:600;'
              f'color:{INK};line-height:1.4;">{_link_or_text(headline, url)}</div>'
            + (f'<div style="font-family:Georgia,serif;font-size:13px;line-height:1.5;'
               f'color:#4A5260;margin-top:2px;">{body}</div>' if body else "")
            + '</div>')


def _sec_label(label: str, color: str = RING_ON_DARK) -> str:
    """A section bar: black field, an accent ring, a white letterspaced label.

    The label used to be small coloured type over a hairline rule. In a
    2,000-word brief with a dozen sections that gave the reader no stop
    between them: the sections blurred into one another and a scan found no
    purchase. This is a hard stop.

    Black rather than each edition's own colour. Four editions with four
    coloured bars would read as decoration; black reads as structure, and the
    accent lands as one deliberate mark instead of a whole field. It is also
    the only colour that leaves the masthead as the single place a reader
    meets the edition's identity.

    Solid background and a text glyph, so it survives clients that block
    images and clients that drop background images.
    """
    return (
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        'class="sec-bar" style="background:#14181F;margin-bottom:14px;">'
        '<tr><td style="padding:9px 14px;">'
        f'<span style="font-family:Arial,sans-serif;font-size:12px;color:{color};'
        'line-height:1;vertical-align:middle;margin-right:9px;">&#9675;</span>'
        '<span style="font-family:Arial,sans-serif;font-size:11px;font-weight:700;'
        'text-transform:uppercase;letter-spacing:2px;color:#FFFFFF;'
        f'vertical-align:middle;">{label}</span>'
        '</td></tr></table>')

def _word_count(d: dict) -> int:
    """The count shown in the header. Shares wordcount.py with the prompt target
    and the validator so the reader is not shown a fourth number."""
    return wordcount.count_words(d)


# The BEIJING and WIRE chapter dividers are gone. Full-width dark bands
# announcing a chapter are chrome the other editions do not carry, and the
# section labels already say where the reader is.


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

    # ── 0. Utility row: internal-use notice left, links right ────────────
    # The house treatment, matching the other three. This edition had neither
    # the internal-use banner nor the link buttons — just a pale grey line of
    # plain-text links that read as a footnote above the nameplate.
    _base = web_url.rsplit("/", 1)[0] + "/" if "/" in web_url else ""
    _a = ('display:inline-block;padding:6px 14px;margin:0 3px;'
          'font-family:Arial,sans-serif;font-size:11px;font-weight:700;'
          'letter-spacing:0.5px;color:#14181F;'
          'background:#FFFFFF;'
          'border-radius:14px;'
          'text-decoration:none;white-space:nowrap;')
    _links = []
    if web_url:
        _links.append(f'<a class="pill" href="{_esc(web_url)}" style="{_a}">Read online</a>')
    if pdf_url:
        _links.append(f'<a class="pill" href="{_esc(pdf_url)}" style="{_a}">Download PDF</a>')
    _arch = archive_url or (_base + "archive.html" if _base else "")
    if _arch:
        _links.append(f'<a class="pill" href="{_esc(_arch)}" style="{_a}">Past issues</a>')
    sections_pre.append(f"""
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#2E3644;" class="util-row no-print">
      <tr>
        <td class="util-cell" style="padding:7px 32px;font-family:Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:rgba(255,255,255,0.72);white-space:nowrap;">For Internal Use Only</td>
        <td class="util-cell" align="right" style="padding:5px 32px 5px 0;text-align:right;">{''.join(_links)}</td>
      </tr>
    </table>
    """)

    # ── 1. Header ────────────────────────────────────────────────────────
    # The house masthead, identical in all four briefs. Only the band colour,
    # the chair name and the title differ. Left column: chair, title, date.
    # Right column, bottom-aligned: the issue meta. Then a rule and the RE
    # line across the full width.
    #
    # It is written out rather than shared because these are four repositories
    # with no common package — so it is copied verbatim, and any change has to
    # be made in all four.
    sections_pre.append(f"""
    <a name="top" id="top"></a>
    <div bgcolor="#DE2910" style="background-color:#DE2910;color:#fff;padding:16px 32px 16px;border-bottom:1px solid rgba(255,255,255,0.18);" class="sec mast-band">
      <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
        <td class="mast-main" style="vertical-align:top;">
          <div style="font-family:Arial,sans-serif;font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:rgba(255,255,255,0.78);margin-bottom:7px;">CSIS China Programs</div>
          <h1 style="margin:0 0 4px 0;font-size:26px;font-weight:700;font-family:Georgia,'Times New Roman',serif;color:#fff;letter-spacing:0.5px;">
            China Daily Brief
          </h1>
          <div style="margin-top:2px;font-size:16px;font-weight:400;color:rgba(255,255,255,0.85);font-family:Georgia,serif;">{_esc(date_str)}</div>
        </td>
        <td class="mast-meta" style="vertical-align:bottom;text-align:right;">
          <div style="font-family:Arial,sans-serif;font-size:11px;letter-spacing:0.5px;color:rgba(255,255,255,0.72);white-space:nowrap;">{wc:,} words &middot; {read_min} min read</div>
        </td>
      </tr></table>
      {"<div style='margin-top:14px;padding-top:12px;border-top:1px solid rgba(255,255,255,0.28);font-size:13px;color:rgba(255,255,255,0.92);font-family:Georgia,serif;line-height:1.55;'><strong style='color:#FFFFFF;font-size:11px;letter-spacing:1.5px;font-family:Arial,sans-serif;'>RE:</strong>&nbsp; " + re_line + "</div>" if re_line else ""}
    </div>
    """)

    # 2. Market strip — four indicators, directly under the nameplate.
    #
    # It was nine tiles across three tables in three shades of navy, most of
    # them rendering as bare em dashes because they had not fetched. Four is
    # what a reader takes in at a glance, and it matches the other editions.
    # The rates, credit and macro prints are not shown: they are a terminal,
    # not a brief. Anything that did not fetch is still named once underneath,
    # and is never invented or carried forward.
    m = digest.get("market_indicators") or {}
    if m:
        def _has(d):
            """A resolved indicator: present, not flagged unavailable, not a dash."""
            if not isinstance(d, dict) or d.get("unavailable"):
                return False
            v = d.get("value")
            return v not in (None, "", "\u2014", "-")

        _MONO = "'Courier New',Courier,monospace"
        _WANTED = [("usd_cny", "USD/CNY", ""),
                   ("sse_composite", "SSE Composite", ""),
                   ("hang_seng", "Hang Seng", ""),
                   ("brent", "Brent", "$")]
        resolved, missing = [], []
        for key, label, prefix in _WANTED:
            d = m.get(key) or {}
            if _has(d):
                resolved.append((label, prefix + _esc(str(d.get("value"))),
                                 _arrow(d.get("change_pct", 0))))
            else:
                missing.append(label)

        if resolved:
            w = 100 // len(resolved)
            cells = ""
            for i, (label, value, under) in enumerate(resolved):
                edge = ("border-left:1px solid rgba(255,255,255,0.10);" if i else "")
                cells += (f'<td width="{w}%" align="center" '
                          f'style="padding:11px 6px 13px;{edge}">'
                          f'<div style="font-size:10px;text-transform:uppercase;'
                          f'letter-spacing:1px;color:#9DB2CE;">{label}</div>'
                          f'<div style="font-family:{_MONO};font-size:16px;'
                          f'font-weight:700;margin-top:3px;">{value}</div>'
                          f'<div style="font-family:{_MONO};font-size:11px;'
                          f'margin-top:2px;">{under}</div></td>')
            strip = (f'<table class="mkt-table dark-sec" width="100%" cellpadding="0" '
                     f'cellspacing="0" border="0" style="background:#051F3D;color:#fff;'
                     f'border-bottom:1px solid rgba(255,255,255,0.10);">'
                     f'<tr>{cells}</tr></table>')
            if missing:
                strip += (f'<div class="delta-sec" style="background:#0a0f1e;'
                          f'color:rgba(255,255,255,0.4);'
                          f'padding:5px 32px;font-size:10px;letter-spacing:0.4px;'
                          f'border-bottom:1px solid rgba(255,255,255,0.08);">'
                          f'Not fetched today: {_esc(", ".join(missing))} '
                          f'&middot; shown only when sourced, never carried forward</div>')
            # Straight under the nameplate, before the jump row, as in Korea.
            sections_pre.append(strip)

    # Placeholder for the jump row, resolved at the end once every section is
    # known and its anchors can be checked. It sits under the data strip,
    # where Korea puts it: nameplate and the day's figures first, then the way
    # into the brief.
    sections_pre.append("%%NAV%%")

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
<span style="font-size:10px;text-transform:uppercase;letter-spacing:1.2px;color:rgba(255,255,255,0.92);margin-right:8px;vertical-align:middle;">Δ Since Yesterday</span>
{chip_html}
</div>""")

    # 3. Morning Memo
    memo = digest.get("morning_memo") or []
    if memo:
        memo_html = ""
        for idx, mi in enumerate(memo[:3], 1):
            # The memo is the first thing read and the place the prompt most
            # wants a name bolded, so it converts emphasis like any body copy.
            t = _emphasis(_esc(mi) if isinstance(mi, str) else _esc(mi.get("text", "") if isinstance(mi, dict) else str(mi or "")))
            memo_html += f"""<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:10px;">
<tr>
<td width="28" style="vertical-align:top;padding-top:1px;">
<div style="width:24px;height:24px;border-radius:50%;background:{PRC_RED};color:#fff;font-size:13px;font-weight:700;text-align:center;line-height:24px;font-family:Georgia,serif;">{idx}</div>
</td>
<td style="vertical-align:top;padding-left:8px;">
<div style="font-size:14px;line-height:1.5;color:#222;font-family:Georgia,serif;">{t}</div>
</td>
</tr>
</table>"""
        # A tinted panel with a rule down the left, as in Korea. Flat on white
        # it read as the first news section rather than as the summary of all
        # of them, and it was the one heading still set in the old gold.
        sections_today.append(f"""
<div {_SEC}>
<a name="memo" id="memo"></a>
<table width="100%" cellpadding="0" cellspacing="0" border="0" class="glance-panel" style="background:#FDEEEB;border-left:3px solid {PRC_RED};">
  <tr><td style="padding:0;">{_sec_label("Today at a Glance")}</td></tr>
            <tr><td style="padding:0 20px 8px;">
    {memo_html}
  </td></tr>
</table>
</div>""")

    # 4. Top Stories — heaviest visual weight in TODAY chapter
    stories = digest.get("top_stories") or []
    if stories:
        sh = ""
        for s in stories:
            cat = _esc(_str(s.get("category_tag", s.get("category", ""))))
            h = _emphasis(_esc(s.get("headline", "")))
            b_raw = s.get("body", "") or ""
            # Suppress body if it duplicates the headline (Google News RSS quirk)
            b = _emphasis(_esc(b_raw)) if b_raw.strip() and b_raw.strip() != s.get("headline", "").strip() else ""
            sl = _esc(_clean_src(s.get("src_line", s.get("source", ""))))
            url = s.get("url", "")
            sh += f"""
<div class="story-card" style="margin-bottom:12px;padding:14px 16px;background:#fff;border-left:3px solid #1B2A4A;border-bottom:1px solid #F0F0F0;">
<div style="font-size:10px;text-transform:uppercase;letter-spacing:1.5px;color:#6B7280;font-weight:700;margin-bottom:6px;">{cat}</div>
<h3 style="margin:0 0 8px 0;font-size:16px;line-height:1.4;color:#1B2A4A;font-family:Georgia,serif;font-weight:700;">{_link_or_text(h, url, style="color:#1B2A4A;text-decoration:none;")}</h3>
{"<p style='margin:0 0 10px 0;font-size:13px;line-height:1.55;color:#444;'>" + b + "</p>" if b else ""}
<div style="font-size:10px;color:#6B7280;margin-top:6px;text-transform:uppercase;letter-spacing:0.5px;">{sl}</div>
</div>"""
        sections_today.append(f'<div {_SEC}><a name="top-stories" id="top-stories"></a>{_sec_label("Top Stories")}{sh}</div>')
        _after_top = len(sections_today)

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
        sections_today.append(f'<div {_SEC}><a name="us-china" id="us-china"></a>{_sec_label("US&ndash;China")}{uh}</div>')

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
        sections_today.append(f'<div {_SEC}><a name="world" id="world"></a>{_sec_label("China &amp; the World")}{wh}</div>')

    # 4c. Overnight Flash. The residual tier: important items that fit none of
    # the relationship sections. It leads the wire rather than sitting under
    # the top stories, because the sections above it are organised by
    # relationship and this one is organised by time.
    overnight = digest.get("overnight_items") or []
    if overnight:
        # A scan list, not a second Top Stories. One rule down the left, one
        # line per item, so the eye runs vertically instead of stopping at a
        # card border every three lines. The cards above carry the weight;
        # this section carries the breadth.
        fh = ""
        for it in overnight:
            if not isinstance(it, dict):
                continue
            cat = _esc(_str(it.get("category", "")))
            h = _emphasis(_esc(it.get("headline", "")))
            b = _emphasis(_esc(it.get("body_text", "")))
            src = _esc(_clean_src(it.get("source", "")))
            url = it.get("url", "")
            tail = (f'<span style="color:{MUTE};"> &mdash; {b}</span>' if b else "")
            fh += (f'<tr>'
                   f'<td style="padding:7px 10px 7px 0;vertical-align:top;white-space:nowrap;'
                   f'font-family:Arial,sans-serif;font-size:10px;font-weight:700;'
                   f'letter-spacing:0.5px;text-transform:uppercase;color:{PRC_RED};'
                   f'border-bottom:1px solid #EEF0F3;">{cat}</td>'
                   f'<td style="padding:7px 0;vertical-align:top;font-family:Georgia,serif;'
                   f'font-size:13px;line-height:1.45;color:{INK};'
                   f'border-bottom:1px solid #EEF0F3;">'
                   f'{_link_or_text(h, url)}{tail}'
                   f'<span style="font-family:Arial,sans-serif;font-size:11px;color:{MUTE};">'
                   f' &middot; {src}</span></td>'
                   f'</tr>')
        fh = (f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
              f'class="flash-table" style="border-top:2px solid {PRC_RED};">{fh}</table>')
        # Inserted directly after Top Stories, not appended: the relationship
        # sections are built before this block runs, so appending would put
        # Overnight below them. The other three briefs put it immediately
        # after Top Stories, and a reader moving between the briefs should
        # meet the day's news in the same place each time.
        sections_today.insert(
            _after_top if "_after_top" in dir() else len(sections_today),
            f'<div {_SEC}><a name="overnight" id="overnight"></a>{_sec_label("Overnight")}{fh}</div>')

    # 5. Key Stat. Rendered as the first row of the market band, so the page
    # has one dark data band instead of two.
    stat = digest.get("key_stat") or {}
    if stat and stat.get("number"):
        # A light panel, not a second red band. Sitting on the same ground as
        # the masthead it read as more chrome, and centring it took the number
        # out of the column every other section reads down.
        stat_html = f"""
<div {_SEC}>
  <a name="key-stat" id="key-stat"></a>{_sec_label("Stat of the Day")}
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#FDF4F2;border-left:3px solid {PRC_RED};border-radius:3px;">
    <tr><td style="padding:14px 16px;">
      <div class="key-stat-num" style="font-family:Georgia,serif;font-size:26px;font-weight:700;color:{PRC_RED_TEXT};line-height:1;">{_esc(str(stat.get("number", "")))}</div>
      <div style="font-family:Georgia,serif;font-size:14px;color:{INK};margin-top:5px;line-height:1.4;">{_esc(stat.get("label", ""))}</div>
      {"<div style='font-family:Georgia,serif;font-size:13px;color:#4A5260;margin-top:4px;line-height:1.5;'>" + _emphasis(_esc(stat.get("context", ""))) + "</div>" if stat.get("context") else ""}
      {"<div style='font-family:Arial,sans-serif;font-size:11px;color:#55607A;margin-top:7px;'>" + _esc(stat.get("source", "")) + "</div>" if stat.get("source") else ""}
    </td></tr>
  </table>
</div>"""
        sections_today.append(stat_html)

    # 8. PRC Government (2x2 + personnel + NPC + calendar)
    prc_gov = digest.get("prc_government") or []
    personnel = digest.get("personnel_changes") or []
    npc = digest.get("npc_politburo") or []
    # Fixed observances are arithmetic, not recall, so they are computed and
    # merged with whatever dated events the model found today. Upcoming has
    # shipped empty and past-dated in other editions for exactly the reason
    # this removes: a list of dates written into the prompt goes stale, and a
    # model told to fill the section from an exhausted list invents entries.
    try:
        import china_calendar
        calendar = china_calendar.merge(digest.get("calendar_watch"))
    except Exception:
        calendar = digest.get("calendar_watch") or []
    if prc_gov or personnel or npc or calendar:
        # Single-column horizontal cards — no more 2x2 dead cell when count is odd
        gov_rows_html = ""
        for it in prc_gov:
            mn = _esc(it.get("ministry", ""))
            mzh = _esc(it.get("ministry_chinese", ""))
            act = _esc(it.get("action", ""))
            det = _emphasis(_esc(it.get("detail", "")))
            url = it.get("url", "")
            lbl = _esc(it.get("source_label", ""))
            off = _esc(it.get("official", ""))
            hdr_parts = []
            if mzh:
                hdr_parts.append(f'<span style="font-size:11px;color:#666;">{mzh}</span>')
            if mn:
                hdr_parts.append(f'<span style="font-size:10px;color:#6B7280;text-transform:uppercase;letter-spacing:0.6px;">{mn}</span>')
            if off:
                hdr_parts.append(f'<span style="font-size:11px;color:#6B7280;font-style:italic;">{off}</span>')
            hdr = ' <span style="color:#ccc;">·</span> '.join(hdr_parts)
            slink = ""
            if url and url != "#" and url.startswith("http"):
                sl = lbl if lbl else mn.lower()
                slink = f'<div style="margin-top:6px;font-size:11px;color:#6B7280;">→ <a href="{_esc(url)}" style="color:#6B7280;text-decoration:none;">{_esc(sl)} ↗</a></div>'
            elif lbl:
                slink = f'<div style="margin-top:6px;font-size:11px;color:#6B7280;">→ {_esc(lbl)}</div>'
            gov_rows_html += f"""
<div style="margin-bottom:12px;padding:12px 14px;border-left:3px solid #1B2A4A;border-bottom:1px solid #F0F0F0;">
<div style="margin-bottom:6px;">{hdr}</div>
<div style="font-size:14px;font-weight:700;color:#1B2A4A;line-height:1.4;margin-bottom:5px;">{act}</div>
<div style="font-size:13px;line-height:1.55;color:#555;">{det}</div>
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
                det = _emphasis(_esc(p.get("detail", "")))
                pred = _esc(p.get("predecessor", "")) if p.get("predecessor") else ""
                ac_c = ac.get(a, "#1B2A4A")
                bg = f'<span style="display:inline-block;padding:1px 6px;border-radius:3px;font-size:10px;font-weight:600;color:#fff;background:{ac_c};text-transform:uppercase;margin-left:6px;">{_esc(a)}</span>'
                pl = f'<div style="font-size:11px;color:#6B7280;margin-top:2px;">Succeeds: {pred}</div>' if pred else ""
                pi += f"""<div style="margin-bottom:10px;padding-left:12px;border-left:3px solid {ac_c};">
<div style="font-size:13px;font-weight:600;color:#1B2A4A;">{nm}{bg}</div>
<div style="font-size:13px;color:#555;">{pos}</div>
<div style="font-size:13px;line-height:1.4;color:#555;">{det}</div>
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
                body = _emphasis(_esc(n.get("body", "")))
                act = _esc(n.get("action", ""))
                det = _emphasis(_esc(n.get("detail", "")))
                url = n.get("url", "")
                ni += f"""<div style="margin-bottom:8px;padding-left:12px;border-left:3px solid #7F8C8D;">
<div style="font-size:11px;color:#7F8C8D;font-weight:600;text-transform:uppercase;">{body}</div>
<div style="font-size:13px;font-weight:600;color:#1B2A4A;">{_link_or_text(act, url)}</div>
<div style="font-size:13px;line-height:1.4;color:#555;">{det}</div>
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
                ch = _emphasis(_esc(c.get("headline", "")))
                cdet = _emphasis(_esc(c.get("detail", "")))
                ci += f"""<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-bottom:1px solid #E8E8E8;">
<tr>
<td width="54" style="padding:9px 12px 9px 0;vertical-align:top;">
<table cellpadding="0" cellspacing="0" border="0" style="background:{PRC_RED};">
<tr><td align="center" style="padding:4px 0 5px;width:46px;">
<div style="font-family:Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:1.5px;color:rgba(255,255,255,0.85);">{cm}</div>
<div style="font-family:Georgia,serif;font-size:16px;font-weight:700;color:#fff;line-height:1;">{cd}</div>
</td></tr>
</table>
</td>
<td style="padding:9px 0;vertical-align:top;">
<div style="font-family:Georgia,serif;font-size:14px;font-weight:700;color:#1B2A4A;">{ch}</div>
<div style="font-family:Georgia,serif;font-size:13px;line-height:1.45;color:#4A5260;margin-top:3px;">{cdet}</div>
</td>
</tr>
</table>"""
            cal_html = ci

        ds = _esc(str(digest.get("digest_date", "")))
        if gov_grid or pers_html or npc_html:
            sections_analysis.append(f"""
<div {_SEC}>
<a name="beijing" id="beijing"></a>{_sec_label("What Beijing Did")}
<div style="font-size:10px;color:#6B7280;text-transform:uppercase;letter-spacing:1px;margin-top:-10px;margin-bottom:14px;">State Council + Ministries{(" · " + ds) if ds else ""}</div>
{gov_grid}{pers_html}{npc_html}
</div>""")
        # The calendar is a forward look, so it closes the brief rather than
        # sitting halfway down inside a government section.
        if cal_html:
            sections_close.append(f'<div {_SEC}><a name="upcoming" id="upcoming"></a>{_sec_label("Upcoming")}{cal_html}</div>')

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
        sections_today.append(f'<div {_SEC}><a name="business" id="business"></a>{_sec_label("Economy &amp; Business")}{bh}</div>')

    # 14. Public Sentiment — removed (low signal-to-noise)

    # 14b. What Beijing Is Saying — the PRC government's own words today.
    # Sits ahead of Social Statements (which carries everyone else) so the
    # reader gets the official line before the reactions to it.
    official = digest.get("official_line") or []
    if official:
        tone_color = {"warning": "#C0392B", "firm": "#B7770D", "conciliatory": "#27AE60",
                      "routine": "#7F8C8D"}
        oh = ""
        for o in official[:8]:
            body = _emphasis(_esc(o.get("body", "")))
            body_zh = _esc(o.get("body_chinese", ""))
            speaker = _esc(o.get("speaker", ""))
            role = _esc(o.get("role", ""))
            topic = _esc(o.get("topic", ""))
            stmt = _esc(o.get("statement", ""))
            zh = _esc(o.get("original_zh") or "")
            ctx = _emphasis(_esc(o.get("context", "")))
            tone = str(o.get("tone", "routine") or "routine").lower()
            to = _esc(o.get("addressed_to", ""))
            tc = tone_color.get(tone, "#7F8C8D")
            url = o.get("url", "")
            src = _esc(_clean_src(o.get("source", "")))
            src_link = ("<div style='font-size:10px;color:#6B7280;margin-top:4px;'>" +
                        _link_or_text(src or "source", url, style="color:#6B7280;text-decoration:underline;") +
                        "</div>") if url and url.startswith("http") else (
                        f"<div style='font-size:10px;color:#6B7280;margin-top:4px;'>{src}</div>" if src else "")
            head = f"{body_zh} · {body}" if body_zh else body
            who = f"{speaker} <span style='font-size:11px;color:#6B7280;font-weight:400;'>· {role}</span>" if speaker else role
            oh += f"""<div style="margin-bottom:14px;padding:12px;background:#FAFAF5;border-radius:4px;border-left:3px solid {tc};">
<table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
<td style="font-size:13px;color:#1B2A4A;font-weight:700;letter-spacing:0.3px;">{head}</td>
<td align="right" style="font-size:10px;text-transform:uppercase;letter-spacing:1px;color:{tc};font-weight:700;">{_esc(tone)}{(" · to " + to) if to else ""}</td>
</tr></table>
<div style="font-size:13px;font-weight:600;color:#1B2A4A;margin:4px 0 2px;font-family:Georgia,serif;">{topic}</div>
{"<div style='font-size:13px;color:#555;'>" + who + "</div>" if (speaker or role) else ""}
<blockquote style="margin:6px 0;padding:8px 12px;background:#fff;border-left:3px solid {tc};font-style:italic;font-size:13px;line-height:1.5;color:#333;font-family:Georgia,serif;">&ldquo;{stmt}&rdquo;</blockquote>
{"<div style='font-size:13px;color:#666;line-height:1.5;margin:2px 0 0 12px;'>" + zh + "</div>" if zh else ""}
{"<div style='font-size:11px;color:#555;margin-top:4px;'><strong>Context:</strong> " + ctx + "</div>" if ctx else ""}
{src_link}
</div>"""
        sections_analysis.append(
            f'<div {_SEC}><a name="saying" id="saying"></a>{_sec_label("What Beijing Is Saying", "#C0392B")}{oh}</div>')

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
            src_link = ("<div style='font-size:10px;color:#6B7280;margin-top:4px;'>" + _link_or_text("source", url, style="color:#6B7280;text-decoration:underline;") + "</div>") if url and url != "#" and url.startswith("http") else ""
            sh += f"""<div style="margin-bottom:14px;padding:12px;background:#FAFAF5;border-radius:4px;border-left:3px solid {bc};">
<div style="font-size:13px;color:#6B7280;text-transform:uppercase;letter-spacing:0.5px;">{pd}</div>
<div style="font-size:14px;font-weight:600;color:#1B2A4A;margin:2px 0;">{who} <span style="font-size:11px;color:#6B7280;font-weight:400;">· {ctx}</span></div>
<blockquote style="margin:6px 0;padding:8px 12px;background:#fff;border-left:3px solid {bc};font-style:italic;font-size:13px;line-height:1.5;color:#333;font-family:Georgia,serif;">&ldquo;{q}&rdquo;</blockquote>
{"<div style='font-size:11px;color:#555;margin-top:4px;'><strong>Note:</strong> " + nt + "</div>" if nt else ""}
{src_link}
</div>"""
        sections_analysis.append(f'<div {_SEC}><a name="analysis" id="analysis"></a>{_sec_label("What Others Are Saying")}{sh}</div>')

    # 16. Also Today — the one-line wire.
    also = digest.get("also_today") or []
    if also:
        # Grouped by subject. Ungrouped it was a run of identical bars whose
        # only distinguishing mark was a category repeated in grey on every
        # row, so a reader looking for the trade item had to read all of them.
        _groups = {}
        for a in also[:8]:
            if not isinstance(a, dict):
                continue
            key = _str(a.get("category", "")).strip() or "Other"
            _groups.setdefault(key.title(), []).append(a)
        ah = ""
        _multi = len(_groups) > 1
        for _cat, _items in _groups.items():
            rows = "".join(
                _compact_row(cat="" if _multi else _esc(_cat),
                             headline=_emphasis(_esc(i.get("headline", ""))),
                             url=i.get("url", ""),
                             src=_esc(_clean_src(i.get("source", ""))),
                             body=_emphasis(_esc(i.get("body_text", ""))))
                for i in _items)
            ah += ((_subhead(_esc(_cat)) if _multi else "")
                   + rows)
        sections_wire.append(
            f'<div {_SEC}><a name="wire" id="wire"></a>{_sec_label("The Wire")}{ah}</div>')

    # 18. Sanctions Status footer — REMOVED. Will return when trade tracker is wired
    # with verifiable BIS/OFAC/DoD running totals. Placeholder text was misleading.

    # Footer (with the auto-generation disclaimer the Japan brief carries)
    # Both footer links point into the published archive, so neither is
    # rendered when there is no page behind it. "Past issues" was built from
    # digest["archive_url"], which the pipeline does not always set, so it
    # shipped as href="" — a link that looks live and goes nowhere.
    _foot_links = ""
    if web_url or archive_url:
        _fa = 'color:rgba(255,255,255,0.95);text-decoration:none;'
        _fbase = web_url.rsplit("/", 1)[0] + "/" if "/" in web_url else ""
        _parts = []
        if web_url:
            _parts.append(f'<a href="{_esc(web_url)}" style="display:inline-block;padding:6px 15px;margin:0 4px;font-family:Arial,sans-serif;font-size:11px;font-weight:700;letter-spacing:0.5px;color:#14181F;background:#FFFFFF;border-radius:14px;text-decoration:none;white-space:nowrap;">Read online</a>')
        _arch = archive_url or (_fbase + "archive.html" if _fbase else "")
        if _arch:
            _parts.append(f'<a href="{_esc(_arch)}" style="display:inline-block;padding:6px 15px;margin:0 4px;font-family:Arial,sans-serif;font-size:11px;font-weight:700;letter-spacing:0.5px;color:#14181F;background:#FFFFFF;border-radius:14px;text-decoration:none;white-space:nowrap;">Past issues</a>')
        if _parts:
            _foot_links = ('<div style="margin-top:11px;font-family:Arial,sans-serif;'
                           'font-size:11px;letter-spacing:0.5px;">'
                           + '<span style="color:rgba(255,255,255,0.45);">'
                             '&nbsp;&middot;&nbsp;</span>'.join(_parts)
                           + '</div>')

    sections_post.append(f"""
<!-- The house footer. Korea carries a CSIS lockup built in HTML; the other
     editions have no wordmark to reproduce, so this leads with the chair
     name instead. Everything else matches: centred, the city and domain on
     their own line, the links as links rather than a run-on sentence, and
     the disclaimer set in the reading face rather than the label face. -->
<table width="100%" cellpadding="0" cellspacing="0" border="0" class="sec footer" style="background:#14181F;border-top:4px solid #DE2910;">
  <tr><td style="padding:20px 32px 6px;text-align:center;">
    <div style="font-family:Georgia,serif;font-size:38px;font-weight:700;color:#FFFFFF;letter-spacing:1px;line-height:1.1;">CSIS China Programs</div>
    <div style="font-family:Arial,sans-serif;font-size:10px;letter-spacing:2px;text-transform:uppercase;color:rgba(255,255,255,0.72);margin-top:6px;">China Daily Brief</div>
    <div style="font-family:Georgia,serif;font-size:13px;color:rgba(255,255,255,0.72);margin-top:12px;">Washington, D.C.</div>
    {_foot_links}
  </td></tr>
  <tr><td style="padding:16px 32px 4px;text-align:center;">
    <div style="font-family:Georgia,serif;font-size:12px;line-height:1.6;color:rgba(255,255,255,0.80);max-width:none;margin:0 auto;white-space:normal;">
      You are receiving the China Daily Brief as a member of the CSIS China Programs distribution list.
    </div>
  </td></tr>
  <tr><td style="padding:14px 32px 10px;text-align:center;">
    <div style="border-top:1px solid rgba(255,255,255,0.14);padding-top:12px;font-family:Georgia,serif;font-size:13px;line-height:1.6;color:rgba(255,255,255,0.82);max-width:560px;margin:0 auto;">
      This newsletter is automatically generated, so it may contain errors. Please check all information and sources before citing.
      To report errors or other issues, please contact Andy Lim at <a href="mailto:alim@csis.org" style="color:rgba(255,255,255,0.95);">alim@csis.org</a>.
    </div>
  </td></tr>
  <tr><td style="padding:0 32px 20px;text-align:center;">
    <div style="font-family:Arial,sans-serif;font-size:10px;letter-spacing:0.5px;color:rgba(255,255,255,0.70);margin-bottom:9px;">generated {gen_time}</div>
    <a href="#top" style="font-family:Arial,sans-serif;font-size:10px;letter-spacing:1.5px;text-transform:uppercase;color:rgba(255,255,255,0.95);text-decoration:none;">&#8593; Back to top</a>
  </td></tr>
</table>
<table width="100%" cellpadding="0" cellspacing="0" border="0" class="footer-end" style="background:#FFFFFF;">
  <tr><td style="padding:12px 32px 18px;text-align:center;font-family:Arial,sans-serif;font-size:10px;letter-spacing:0.5px;color:#6B7280;">
    &copy; {now.year} Center for Strategic and International Studies
  </td></tr>
</table>""")

    # Assembly. Organised by RELATIONSHIP, not by time: the frame, the biggest
    # stories, then US–China, China & the World, Economy & Business; the data
    # band; Beijing's propaganda, words and actions; the voices; the wire; and
    # the forward look to close. Two chapter dividers, not four.
    sections = (
        sections_pre +
        sections_today +
        sections_markets +
        sections_analysis +
        sections_wire +
        sections_close +
        sections_post
    )

    # ── Jump row ──────────────────────────────────────────────────────────
    # The brief is too long to scan end to end and the only link in it was
    # "back to top". Label and anchor are paired here and each pair is kept
    # only when the section actually emitted its anchor, so a quiet day that
    # drops sections simply gets fewer links rather than dead ones.
    _NAV = [("Top Stories", "top-stories"), ("US-China", "us-china"),
            ("The World", "world"), ("Beijing", "beijing"),
            ("Markets", "business"), ("Statements", "saying"),
            ("Analysis", "analysis"), ("Overnight", "overnight"),
            ("The Wire", "wire"), ("Upcoming", "upcoming")]
    body_html = "\n".join(s for s in sections if s)
    _links = [f'<a href="#{_a}" style="color:{PRC_RED_TEXT};text-decoration:underline;'
              f'text-underline-offset:2px;white-space:nowrap;">{_l}</a>'
              for _l, _a in _NAV if f'a name="{_a}"' in body_html]
    _nav_html = ""
    if len(_links) >= 4:
        # Named and underlined. Unlabelled and unadorned it reads as a
        # subtitle rather than a menu, and goes unused.
        _nav_html = ('<div class="nav-row sec" style="background:#F7F8FA;'
                     'border-bottom:1px solid #E4E7EB;padding:9px 32px;'
                     'text-align:center;font-family:Arial,sans-serif;'
                     'font-size:11px;line-height:1.9;color:#6B7280;">'
                     '<span style="font-size:10px;font-weight:700;'
                     'text-transform:uppercase;letter-spacing:1.5px;'
                     'color:#6B7280;">In this issue &nbsp;</span>'
                     + ' &nbsp;&middot;&nbsp; '.join(_links) + '</div>')
    body_html = body_html.replace("%%NAV%%", _nav_html)
    return f"""<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<!-- Both schemes. This declared light only while the stylesheet below
     carried a full dark-mode palette, so the dark rules could never fire in
     a client that honours the declaration. It was the one edition of four
     whose dark mode was switched off by its own header. -->
<meta name="color-scheme" content="light dark">
<meta name="supported-color-schemes" content="light dark">
<title>China Daily Brief</title>
<style>
:root {{ color-scheme: light; }}
body {{ margin:0; padding:0; background:#ffffff; font-family:Arial,sans-serif; color:#333333; -webkit-text-size-adjust:100%; }}
.container {{ width:680px; max-width:100%; margin:0 auto; background:#ffffff; text-align:left; }}
/* The wrapper <td align="center"> centres the container for Outlook, which
   ignores margin:auto. Without the reset above it also centred every line
   of text in the brief. */
/* Lock dark sections - prevent iOS Mail light-mode override */
/* No background here. This class exists to force light-on-dark type in
   clients that recolour; the ground is set inline per band, and an
   !important background here silently overrode the red masthead. */
.dark-sec {{ color:#ffffff !important; }}
.dark-navy {{ background-color:#1B2A4A !important; }}
.dark-sec * {{ color:#ffffff !important; }}
.dark-sec a {{ color:#D4AC0D !important; }}
.mid-sec {{ background-color:#162340 !important; color:#ffffff !important; }}
.deep-sec {{ background-color:#0F1B30 !important; color:#ffffff !important; }}
.delta-sec {{ background-color:#0a0f1e !important; color:#ffffff !important; }}
/* The tablet band, which this brief did not have. Between 601 and 768 the
   frame was uncapped while the other three held 680, so the same brief read
   wider here in a desktop preview pane. */
@media only screen and (min-width: 601px) and (max-width: 768px) {{
  .container {{ width:100% !important; max-width:680px !important; }}
}}

@media only screen and (max-width: 600px) {{
  /* The notice and the links will not sit side by side on a phone. The other
     three briefs stack them; this one kept them in one row, so the pills were
     squeezed against the right edge. No width:100% here - a cell set to
     display:block already fills its row, and 100% plus horizontal padding is
     measured content-box, which pushes the table wider than the screen. */
  .util-row .util-cell {{ display:block !important; text-align:center !important;
    padding:5px 8px !important; white-space:normal !important; }}
  .util-row .util-cell a {{ margin:2px !important; }}
  /* The data strip is four tiles of monospaced figures in one row. At 320px
     that is 80px a tile, and "18,220.10" in 16px Courier does not fit, so the
     row set a min-content floor wider than the screen and the whole brief
     scrolled sideways. Smaller figures and tighter padding, which is what the
     other briefs already do. */
  .mkt-table td {{ padding:8px 3px 10px !important; }}
  .mkt-table div[style*="font-size:16px"] {{ font-size:13px !important; }}
  /* 10px stays: 9px is below the floor the visual check enforces, and the
     tracking is what was costing the width, not the size. */
  .mkt-table div[style*="font-size:10px"] {{ letter-spacing:0.2px !important; }}
  .mkt-table div[style*="font-size:11px"] {{ font-size:10px !important; }}
  /* The masthead had no mobile rule at all, so its two columns stayed side by
     side on a phone: the nameplate squeezed into a narrow column while the
     meta line held its own width on the right. The other three briefs stack
     these; this one now does too, at the same nameplate size. */
  h1 {{ font-size:22px !important; }}
  .mast-main, .mast-meta {{ display:block !important; width:100% !important; }}
  .mast-meta {{ text-align:left !important; padding-top:10px !important; }}
  .container {{ width:100% !important; max-width:100% !important; text-align:left !important; }}
  .sec {{ padding-left:16px !important; padding-right:16px !important; }}
  h1 {{ font-size:22px !important; }}
  .key-stat-num {{ font-size:26px !important; }}
  .market-val {{ font-size:16px !important; }}
}}
@media (prefers-color-scheme: dark) {{
  /* The terminal strip is white by design in light mode. Left unmapped it
     stays white in dark mode, a bright band across the bottom of an otherwise
     dark brief. The coverage guard misses it because #FFFFFF is on the exempt
     list, being legitimate as type on an accent fill. */
  .container .footer-end, .container .footer-end {{ background:#1a1a1a !important; }}
      /* Keep the filled buttons filled. The generic white-background
         rule darkens them while their type stays dark, which measured
         1.23:1 - a button you cannot read. */
    
  .container .footer-end td, .container .footer-end td {{ color:#9AA3AE !important; }}
    /* There was no dark block at all, and body is hardcoded white, so a client
       in dark mode inverted the ground and left dark type on it. These rules
       are generated from the colours this template actually uses, rather than
       from a guess at which elements carry them - Korea's hand-written
       selectors matched h3, div and a while the markup also used td, p and
       span, and most of its body text stayed unreadable as a result. */
    body {{ background:#121212 !important; }}
    .container {{ background:#1a1a1a !important; }}
    .container h1, .container h2, .container h3 {{ color:#E8E6E1 !important; }}
    .container a {{ color:#6FA8E8 !important; }}
    .container [style*="color:#1B2A4A"] {{ color:#E8E6E1 !important; }}
    .container [style*="color:#1b2a4a"] {{ color:#E8E6E1 !important; }}
    .container [style*="color:#27AE60"] {{ color:#9AA3AE !important; }}
    .container [style*="color:#27ae60"] {{ color:#9AA3AE !important; }}
    .container [style*="color:#2980B9"] {{ color:#9AA3AE !important; }}
    .container [style*="color:#2980b9"] {{ color:#9AA3AE !important; }}
    .container [style*="color:#2c3e50"] {{ color:#E8E6E1 !important; }}
    .container [style*="color:#2C3E50"] {{ color:#E8E6E1 !important; }}
    .container [style*="color:#333333"] {{ color:#E8E6E1 !important; }}
    .container [style*="color:#6B7280"] {{ color:#9AA3AE !important; }}
    .container [style*="color:#6b7280"] {{ color:#9AA3AE !important; }}
    .container [style*="color:#7f8c8d"] {{ color:#9AA3AE !important; }}
    .container [style*="color:#7F8C8D"] {{ color:#9AA3AE !important; }}
    .container [style*="color:#c0392b"] {{ color:#C4C8CE !important; }}
    .container [style*="color:#C0392B"] {{ color:#C4C8CE !important; }}
    .container [style*="background:#f0f0f0"] {{ background-color:#262A30 !important; }}
    .container [style*="background:#F0F0F0"] {{ background-color:#262A30 !important; }}
    .container [style*="background:#fafaf5"] {{ background-color:#262A30 !important; }}
    .container [style*="background:#FAFAF5"] {{ background-color:#262A30 !important; }}
    .container [style*="background:#ffffff"] {{ background-color:#262A30 !important; }}
    .container [style*="background:#FFFFFF"] {{ background-color:#262A30 !important; }}
    /* Filled from a measured audit of the rendered brief: these
       colours reached the output with no dark rule, so they kept
       their light values and rendered near-black on near-black. */
    .container [style*="color:#1a222e"] {{ color:#E8E6E1 !important; }}
    .container [style*="color:#1A222E"] {{ color:#E8E6E1 !important; }}
    .container [style*="color:#222"] {{ color:#E8E6E1 !important; }}
    .container [style*="color:#444"] {{ color:#C4C8CE !important; }}
    .container [style*="color:#4a5260"] {{ color:#C4C8CE !important; }}
    .container [style*="color:#4A5260"] {{ color:#C4C8CE !important; }}
    .container [style*="color:#55607a"] {{ color:#C4C8CE !important; }}
    .container [style*="color:#55607A"] {{ color:#C4C8CE !important; }}
    .container [style*="color:#888"] {{ color:#9AA3AE !important; }}
    .container [style*="color:#aaa"] {{ color:#9AA3AE !important; }}
    .container [style*="color:#AAA"] {{ color:#9AA3AE !important; }}
    .container [style*="color:#d4ac0d"] {{ color:#E8C86A !important; }}
    .container [style*="color:#D4AC0D"] {{ color:#E8C86A !important; }}
    .container [style*="color:#de2910"] {{ color:#FF8A7A !important; }}
    .container [style*="color:#DE2910"] {{ color:#FF8A7A !important; }}
    .container [style*="background:#f7f8fa"] {{ background-color:#1A1D22 !important; }}
    .container [style*="background:#F7F8FA"] {{ background-color:#1A1D22 !important; }}
    .container [style*="background:#fdeeeb"] {{ background-color:#2A1815 !important; }}
    .container [style*="background:#FDEEEB"] {{ background-color:#2A1815 !important; }}
    .container [style*="background:#fdf4f2"] {{ background-color:#2A1D1A !important; }}
    .container [style*="background:#FDF4F2"] {{ background-color:#2A1D1A !important; }}
    .container [style*="background:#fff"] {{ background-color:#262A30 !important; }}
    .container [style*="background:#FFF"] {{ background-color:#262A30 !important; }}
    /* Last in the block, so these win: equal specificity, so order decides.
     The pill is dark type on a white fill and the generic white-background
     rule above darkens the fill while the type stays dark - 1.23:1, a button
     you cannot read. The stat figure and the nameplate sit on grounds the
     rules above change underneath them. */
  .container .pill {{ background:#E8E6E1 !important; color:#14181F !important; }}
  .container [style*="color:#C82409"] {{ color:#FF8A7A !important; }}
  .container .mast-band h1 {{ color:#FFFFFF !important; }}
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
<a name="top" id="top"></a>
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
