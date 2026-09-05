"""
Offline smoke tests. No network, no API key. Runs in the workflow before the
pipeline and locally before a commit:

    python smoke_test.py

Covers the code paths a live run depends on but that a live run only tests
once a day at 6 AM: the Google News decoder, the article-text extractor, the
SOURCE-OR-SKIP gate and headline repair, within-edition and cross-day dedup,
the validator's critical/advisory split, calendar and on-this-day date
filters, baseline expiry, prompt assembly, rendering, the feed registry, and
the model pins (no prefill, IDs in the known set).
"""
import base64
import json
import re
import sys
import traceback
from datetime import date

FAILURES = []
PASSED = 0


def check(name, cond, detail=""):
    global PASSED
    if cond:
        PASSED += 1
    else:
        FAILURES.append(f"{name}: {detail}")
        print(f"  FAIL  {name} {detail}")


def section(title):
    print(f"\n[{title}]")


# ── fixtures ─────────────────────────────────────────────────────────────────

TODAY = date(2026, 9, 4)
TODAY_STR = "Friday, September 4, 2026"


def make_payload():
    return {
        "tier1": [
            {"title": "China imposes export curbs on two more rare-earth compounds",
             "url": "https://www.reuters.com/world/china/rare-earth-curbs-2026-09-03/",
             "summary": "China's commerce ministry said on Wednesday it would restrict exports of "
                        "two rare-earth compounds, citing national security. MOFCOM spokesperson "
                        "He Yadong said the measures \"are not aimed at any specific country\" and "
                        "take effect on October 1.",
             "source": "Reuters China", "lang": "EN", "prestige_outlet": True,
             "flagged_journalist": "Joe Cash", "fulltext": True},
            {"title": "PLA sends 41 aircraft across Taiwan Strait median line",
             "url": "https://www.taipeitimes.com/News/front/archives/2026/09/04/2003841234",
             "summary": "Taiwan's defense ministry said 41 PLA aircraft and nine vessels were detected, "
                        "28 of which crossed the median line.",
             "source": "Taipei Times", "lang": "EN"},
            {"title": "Beijing warns Manila after Scarborough Shoal collision",
             "url": "https://www.scmp.com/news/china/diplomacy/article/3300001/scarborough",
             "summary": "China's coast guard said a Philippine vessel \"dangerously approached\" "
                        "one of its ships near Scarborough Shoal.",
             "source": "SCMP", "lang": "EN"},
            {"title": "WSJ: Nvidia weighs China-specific chip as export rules tighten",
             "url": "https://www.wsj.com/tech/nvidia-china-chip-2026",
             "summary": "Nvidia is designing a chip for China that complies with the new rules.",
             "source": "WSJ China", "lang": "EN", "prestige_outlet": True},
            {"title": "外交部发言人林剑主持例行记者会",
             "url": "https://www.fmprc.gov.cn/fyrbt_673021/202609/t20260903_1.shtml",
             "summary": "林剑：中方敦促美方停止以任何形式向台湾提供武器。台湾问题是中国核心利益中的核心。",
             "source": "外交部 (MOFA ZH)", "lang": "ZH", "government_primary": True},
        ],
        "tier2": [
            {"title": "The Trade War Has a New Front: Rare Earths",
             "url": "https://www.csis.org/analysis/rare-earths-new-front",
             "summary": "CSIS analysis of the September export controls.",
             "source": "CSIS China", "prestige_tier": "A", "china_primary": True},
        ],
        "tier3": [],
        "tier4": [
            {"title": "Xi Jinping meets Vietnamese leader in Beijing",
             "url": "http://www.news.cn/english/20260903/xi-vietnam.html",
             "summary": "Xi Jinping held talks with the General Secretary of the Communist Party of Vietnam.",
             "source": "Xinhua English", "lang": "EN"},
        ],
        "xi_tracker_articles": [], "hidden_reach_articles": [], "gray_zone_articles": [],
        "market_indicators": {
            "sse_composite": {"value": "3,450.12", "change_pct": 0.4, "as_of": "Sep 3"},
            "cgb_10y": {"value": "—", "as_of": "", "unavailable": True},
        },
        "xinhua_summary": {"total_articles": 1, "direct_count": 1, "indirect_count": 0,
                           "categories": {}, "sources": {"Xinhua English": 1},
                           "headlines": ["[Xinhua English] Xi Jinping meets Vietnamese leader"]},
        "resolve_stats": {"resolved": 40, "cached": 5, "failed": 3, "budget_hit": 0,
                          "gnews_total": 48},
        "fulltext_stats": {"considered": 60, "fetched": 60, "enriched": 45, "gnews_skipped": 3},
        "feed_report": {"feeds_total": 200, "feeds_ok": 170, "major_empty": [],
                        "fallback_used": [], "dead": []},
    }


def make_digest():
    body = ("China's commerce ministry restricted exports of two rare-earth compounds effective "
            "October 1, citing national security. MOFCOM said the measures are not aimed at any "
            "specific country. The curbs follow the April 2025 controls on seven elements.")
    return {
        "digest_date": TODAY_STR,
        "re_line": "Rare-earth curbs · 41 PLA aircraft · Scarborough warning",
        "editor_note": "Export controls and the Strait dominate.",
        "market_indicators": {},
        "morning_memo": ["Beijing restricts two more rare-earth compounds from October 1.",
                         "PLA sends 41 aircraft across the median line in one day.",
                         "China Coast Guard warns Manila after a Scarborough Shoal collision."],
        "top_stories": [
            {"url": "https://www.reuters.com/world/china/rare-earth-curbs-2026-09-03/",
             "source": "Reuters China", "category_tag": "Sanctions",
             "headline": "China imposes export curbs on two more rare-earth compounds",
             "body": body, "so_what": "Affects the October 1 effective date.", "pattern_note": None},
            {"url": "https://www.taipeitimes.com/News/front/archives/2026/09/04/2003841234",
             "source": "Taipei Times", "category_tag": "PLA",
             "headline": "PLA sends 41 aircraft across Taiwan Strait median line",
             "body": "Taiwan's defense ministry detected 41 PLA aircraft and nine vessels; 28 aircraft "
                     "crossed the median line, the highest single-day count since May.",
             "so_what": None, "pattern_note": None},
            # Hallucinated URL on a known domain: must be repaired by headline match.
            {"url": "https://www.scmp.com/news/china/article/9999999/made-up-path",
             "source": "SCMP", "category_tag": "Indo-Pacific",
             "headline": "Beijing warns Manila after Scarborough Shoal collision",
             "body": "The China Coast Guard said a Philippine vessel dangerously approached one of its "
                     "ships near Scarborough Shoal and warned Manila against provocations.",
             "so_what": None, "pattern_note": None},
        ],
        "overnight_items": [
            {"url": "https://www.wsj.com/tech/nvidia-china-chip-2026", "source": "WSJ China",
             "category": "Technology", "headline": "Nvidia weighs China-specific chip as export rules tighten",
             "body_text": "Nvidia is designing a chip for China that complies with the new rules, "
                          "people familiar with the plan said, with a decision expected this quarter."},
            # Duplicate of a top story by headline: must be removed.
            {"url": "https://www.reuters.com/world/china/rare-earth-curbs-2026-09-03/",
             "source": "Reuters China", "category": "Sanctions",
             "headline": "China imposes export curbs on two more rare-earth compounds",
             "body_text": "Repeat of the top story that should be deduplicated away by the validator."},
            # Fabricated item on an unknown domain: must be deleted.
            {"url": "https://www.brookings.edu/articles/china-export-controls-analysis/",
             "source": "Brookings China", "category": "Sanctions",
             "headline": "Brookings examines evolving export control environment",
             "body_text": "A generic think-tank piece that does not exist in the input data at all."},
            {"url": "", "source": "Xinhua English", "category": "Diplomacy",
             "headline": "Xi Jinping meets Vietnamese leader in Beijing",
             "body_text": "Xi held talks with Vietnam's party chief in Beijing on Wednesday, the second "
                          "meeting this year, with both sides pledging to manage South China Sea differences."},
            {"url": "", "source": "Global Times", "category": "Diplomacy",
             "headline": "MOFA held its daily press briefing",
             "body_text": "The spokesperson addressed several topics; specific details were not provided."},
        ],
        "also_today": [],
        "official_line": [
            {"body": "MOFA", "body_chinese": "外交部", "speaker": "Lin Jian", "role": "MOFA spokesperson",
             "topic": "US arms sales to Taiwan",
             "statement": "China urges the US to stop providing weapons to Taiwan in any form.",
             "original_zh": "中方敦促美方停止以任何形式向台湾提供武器",
             "addressed_to": "US", "tone": "firm", "context": "Asked about a reported arms package.",
             "source": "外交部 (MOFA ZH)",
             "url": "https://www.fmprc.gov.cn/fyrbt_673021/202609/t20260903_1.shtml"},
            {"body": "MOFCOM", "body_chinese": "商务部", "speaker": "He Yadong", "role": "MOFCOM spokesperson",
             "topic": "Rare-earth export controls",
             "statement": "The measures are not aimed at any specific country.",
             "original_zh": None, "addressed_to": "other", "tone": "routine",
             "context": "Announcing the October 1 controls.", "source": "Reuters China",
             "url": "https://www.reuters.com/world/china/rare-earth-curbs-2026-09-03/"},
        ],
        "social_statements": [],
        "opeds_today": [
            {"title": "The Trade War Has a New Front: Rare Earths",
             "url": "https://www.csis.org/analysis/rare-earths-new-front", "source": "CSIS China",
             "prestige_tier": "A", "china_primary": True, "relevance_score": 9,
             "central_argument": "Rare earths are now the main lever.", "summary": "CSIS analysis of the controls."},
        ],
        "academic_today": [],
        "prc_government": [], "npc_politburo": [], "congressional_watch": [], "personnel_changes": [],
        "business_economy": [], "indo_pacific": [],
        "calendar_watch": [
            {"month": "Oct", "day": 1, "headline": "PRC National Day", "detail": "77th anniversary."},
            {"month": "Oct", "day": 1, "headline": "Rare-earth curbs take effect", "detail": "MOFCOM measures."},
            {"month": "Aug", "day": 1, "headline": "PLA Day (past)", "detail": "Should be dropped."},
            {"month": "Oct", "day": 25, "headline": "UNGA 2758 anniversary", "detail": "55th."},
        ],
        "on_this_day": [{"date": "September 8, 1951", "event": "Wrong-day event", "relevance": "x"}],
        "xinhua_delta": {"xi_appearance_today": True, "bottom_line": "Xi hosted Vietnam's party chief — routine."},
        "monitored_locations": [{"name": f"loc{i}", "block": "gray_zone", "status": "normal",
                                 "note": "n", "last_source_date": "", "direction": "",
                                 "csis_product": ""} for i in range(16)],
        "us_china_trade": {"deals": [], "cfius": []},
    }


# ── tests ────────────────────────────────────────────────────────────────────

def test_resolve():
    section("resolve.py")
    import resolve
    embedded = "https://www.reuters.com/world/china/example-2026-09-04/"
    payload = b"\x08\x13\x22" + bytes([len(embedded)]) + embedded.encode() + b"\xd2\x01\x00"
    fake_id = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    check("base64 decode", resolve._decode_base64(fake_id) == embedded)
    check("article id parse", resolve._article_id(f"https://news.google.com/rss/articles/{fake_id}?oc=5") == fake_id)
    check("new-format id yields None offline", resolve._decode_base64("CBMiAU_yqLNfakenewformatid") is None)
    check("is_gnews", resolve.is_gnews("https://news.google.com/rss/x") and not resolve.is_gnews(embedded))


def test_fulltext():
    section("fulltext.py")
    import fulltext
    html = ('<html><head><meta property="og:description" content="Beijing tied subsidies to milestones.">'
            '</head><body><nav><p>Home</p></nav><article>'
            '<p>China will release the next tranche of semiconductor subsidies only once SMIC reaches an agreed milestone.</p>'
            '<p>Short.</p></article></body></html>')
    check("meta extract", fulltext.extract_meta(html).startswith("Beijing tied"))
    body = fulltext.extract_body(html)
    check("body extract", "China will release" in body and "Home" not in body and "Short." not in body)
    check("paywall meta-only", "China will release" not in fulltext.extract(html, want_body=False))
    check("paywall list", fulltext._is_paywalled("https://www.wsj.com/x") and not fulltext._is_paywalled("https://amti.csis.org/x"))


def test_collect_registry():
    section("collect.py registry")
    import collect
    all_feeds = {}
    for name, d in (("tier1", collect.TIER1_FEEDS), ("tier2", collect.TIER2_FEEDS),
                    ("tier3", collect.TIER3_FEEDS), ("tier4", collect.TIER4_FEEDS),
                    ("xi", collect.XI_TRACKER_FEEDS), ("hr", collect.HIDDEN_REACH_FEEDS),
                    ("gz", collect.GRAY_ZONE_FEEDS)):
        for src, val in d.items():
            url = val[0] if isinstance(val, tuple) else val
            check(f"feed url {src}", isinstance(url, str) and url.startswith("http"), url)
            if name in ("tier2", "tier3"):
                check(f"tiered tuple {src}", isinstance(val, tuple) and len(val) == 2)
            all_feeds.setdefault(src, []).append(name)
    dupes = [s for s, tiers in all_feeds.items() if len(tiers) > 1]
    check("no source name in two tiers", not dupes, str(dupes))
    total = sum(len(d) for d in (collect.TIER1_FEEDS, collect.TIER2_FEEDS, collect.TIER3_FEEDS,
                                 collect.TIER4_FEEDS, collect.XI_TRACKER_FEEDS,
                                 collect.HIDDEN_REACH_FEEDS, collect.GRAY_ZONE_FEEDS))
    check("200+ feeds", total >= 200, str(total))
    zh = [s for s in collect._CHINESE_LANG_SOURCES]
    check("20+ Chinese-language sources", len(zh) >= 20, str(len(zh)))
    check("MacroPolo removed", "MacroPolo" not in collect.TIER1_FEEDS)
    check("fallbacks registered", len(collect._FALLBACK) >= 15, str(len(collect._FALLBACK)))
    check("prestige outlet sources in tier1",
          all(s in collect.TIER1_FEEDS for s in ("WSJ China", "Reuters China", "NYT China")))
    check("150+ correspondents", len(collect.PRESTIGE_JOURNALISTS) >= 150, str(len(collect.PRESTIGE_JOURNALISTS)))
    check("boilerplate scrub", collect._clean_summary("The latest news and analysis from Reuters", "t") == "")
    check("title-repeat scrub", collect._clean_summary("China warns Manila.", "China warns Manila") == "")
    check("title key", collect._title_key("China’s BYD Q1 profit rises 20% - Reuters") == "china s byd q1 profit rises 20 reuters")
    arts = [{"url": "https://a/1", "title": "Same headline here for dedup test", "lang": "EN"},
            {"url": "https://a/2", "title": "Same headline here for dedup test", "lang": "EN"},
            {"url": "https://a/3", "title": "Different headline entirely, unrelated", "lang": "EN"}]
    check("cross-feed title dedup", len(collect._dedup(arts)) == 2)
    zh_arts = [{"url": f"https://z/{i}", "title": f"t{i}", "lang": "ZH", "source": "X (ZH)",
                "pub_date": f"2026-09-04T00:{i:02d}:00"} for i in range(20)]
    check("ZH per-source cap", len(collect._cap_zh(zh_arts)) == collect.ZH_PER_SOURCE_CAP)
    check("market unavailable shape", collect._UNAVAILABLE.get("unavailable") is True)


def test_digest_module():
    section("digest.py")
    import digest, pipeline_health
    src = open("digest.py", encoding="utf-8").read()
    check("no assistant prefill", '"role": "assistant"' not in src and "_JSON_PREFILL" not in src)
    # anthropic 1.x runners have httpx2 only; an unconditional httpx import
    # crashed the first CI run of this pipeline while passing locally.
    check("no unconditional httpx import", not re.search(r"^import httpx\s*$", src, re.M))
    for mod in ("digest", "run", "collect", "render", "send_email", "resolve", "fulltext"):
        msrc = open(f"{mod}.py", encoding="utf-8").read()
        check(f"{mod}.py imports only installed deps",
              not re.search(r"^(import|from) (httpx|playwright|bs4|lxml)\b", msrc, re.M), mod)
    check("FAST_MODEL known", digest.FAST_MODEL in pipeline_health.KNOWN_MODEL_IDS, digest.FAST_MODEL)
    check("PRIMARY_MODEL known", digest.PRIMARY_MODEL in pipeline_health.KNOWN_MODEL_IDS, digest.PRIMARY_MODEL)
    check("no date-suffixed model", not re.search(r"claude-[a-z]+-\d(-\d)?-\d{8}", digest.FAST_MODEL + digest.PRIMARY_MODEL))
    check("pricing for pinned models", digest.FAST_MODEL in digest.MODEL_PRICING and digest.PRIMARY_MODEL in digest.MODEL_PRICING)
    check("max tokens >= 32k", digest.MAX_OUTPUT_TOKENS >= 32000)
    up = digest._filter_upcoming(digest._VERIFIED_UPCOMING, TODAY)
    check("past upcoming dates removed", "May 14-15 2026" not in up and "Jul 24 2026" not in up and "Aug 2026" not in up)
    check("future upcoming dates kept", "Oct 1 2026" in up and "Recurring" in up)
    check("baseline age computed", digest.baseline_age_days(TODAY) > 0)
    check("stale note when old", "UNCONFIRMED" in digest._baseline_staleness_note(TODAY))
    parsed = digest._robust_json_parse('```json\n{"a": 1}\n```')
    check("fence-stripped parse", parsed == {"a": 1})
    parsed = digest._robust_json_parse('Here is the JSON: {"b": [1,2]} thanks')
    check("preamble-stripped parse", parsed == {"b": [1, 2]})
    payload = make_payload()
    prompt = digest.build_user_prompt(payload, TODAY_STR)
    for needle in ("official_line", "ALREADY COVERED" if payload.get("recent_coverage") else "TIER 1",
                   "BASELINE AGE", "prestige_outlet", "FINAL CHECKS", "unavailable"):
        check(f"prompt contains {needle}", needle in prompt)
    check("prompt orders prestige first",
          prompt.find("rare-earth-curbs") < prompt.find("taipeitimes"))
    ranked = digest._prioritize(payload["tier1"])
    check("ZH government item ranks above plain item",
          [a["source"] for a in ranked].index("外交部 (MOFA ZH)") < [a["source"] for a in ranked].index("Taipei Times"))
    for needle in ("OFFICIAL LINE", "VERBATIM ONLY", "HOLLOW ITEMS", "MARKET AND RATE DATA",
                   "USING THE ARTICLE TEXT", "CHINESE-LANGUAGE SOURCES", "PROPER NOUNS"):
        check(f"system prompt has {needle}", needle in digest.SYSTEM_PROMPT)
    # Length discipline must agree between the prompt and the validator, or the
    # model writes to one target and the gate measures against another.
    import run
    check("prompt states the 1,500-1,900 target", "1,500 and 1,900" in prompt)
    check("prompt floor matches validator floor", "HARD MINIMUM 1,200" in prompt,
          f"validator floor {run.WORD_FLOOR_CRITICAL}")
    check("prompt ceiling matches validator ceiling", "exceed 2,100" in prompt,
          f"validator ceiling {run.WORD_CEILING}")
    check("editor_note briefed as the lead", "THE BOTTOM LINE" in prompt)


def test_run_postprocess_and_validate():
    section("run.py post-process + validator")
    import run
    payload = make_payload()
    d = make_digest()
    d, log = run._postprocess_digest(d, payload, set(), set(), TODAY)
    joined = "\n".join(log)
    top_urls = [t["url"] for t in d["top_stories"]]
    check("hallucinated known-domain URL repaired by headline",
          "https://www.scmp.com/news/china/diplomacy/article/3300001/scarborough" in top_urls, joined)
    on_heads = [o["headline"] for o in d["overnight_items"]]
    check("fabricated unknown-domain item deleted", not any("Brookings" in h for h in on_heads), joined)
    check("duplicate headline removed across sections",
          sum(1 for h in on_heads if "rare-earth" in h) == 0, joined)
    check("url-less item repaired by exact title",
          any(o.get("url", "").startswith("http://www.news.cn") for o in d["overnight_items"]), joined)
    check("hollow presser item dropped", not any("daily press briefing" in h for h in on_heads), joined)
    check("past calendar entry dropped", all(c["headline"] != "PLA Day (past)" for c in d["calendar_watch"]), joined)
    check("off-date on_this_day dropped", d["on_this_day"] == [], joined)
    check("em-dash replaced", "—" not in d["xinhua_delta"]["bottom_line"])
    check("source_count set", d.get("source_count", 0) >= 5)
    check("official_line kept with corpus URL", len(d["official_line"]) == 2)

    findings = run.validate_digest(d, payload=payload, today=TODAY, check_links=False)
    critical = [f for f in findings if "CRITICAL" in f]
    # The fixture is deliberately tiny, so the two size floors fire; nothing else may.
    unexpected = [f for f in critical if not (f.startswith("WORD COUNT") or f.startswith("OVERNIGHT ITEMS"))]
    check("size floors fire on tiny fixture", len(critical) == 2, str(critical))
    check("no other critical findings on good fixture", not unexpected, str(unexpected))
    check("word count computed", run._count_words(d) > 150, str(run._count_words(d)))
    check("official_line counted in words", run._count_words({"official_line": d["official_line"]}) > 20)

    # Break it: too few top stories, wrong date, duplicate memo.
    bad = json.loads(json.dumps(d))
    bad["top_stories"] = bad["top_stories"][:1]
    bad["digest_date"] = "Thursday, September 3, 2026"
    bad["morning_memo"] = ["same", "same", "same"]
    findings = run.validate_digest(bad, payload=payload, today=TODAY, check_links=False)
    critical = [f for f in findings if "CRITICAL" in f]
    check("top stories floor is critical", any("TOP STORIES CRITICAL" in f for f in critical), str(critical))
    check("date mismatch is critical", any("DATE MISMATCH" in f for f in critical))
    check("memo duplicates critical", any("MORNING MEMO CRITICAL" in f for f in critical))

    # Cross-day: an item already published must be removed.
    d2 = make_digest()
    prev_urls = {"https://www.wsj.com/tech/nvidia-china-chip-2026"}
    d2, log2 = run._postprocess_digest(d2, payload, prev_urls, set(), TODAY)
    check("cross-day repeat removed", not any("Nvidia" in o["headline"] for o in d2["overnight_items"]))

    # Unsourced-count gate.
    d3 = make_digest()
    for i in range(5):
        d3["overnight_items"].append({"url": f"https://www.example-invented.com/{i}", "source": "X",
                                      "category": "c", "headline": f"Invented story number {i} about something",
                                      "body_text": "Not in the corpus at all, this should be deleted."})
    d3, _ = run._postprocess_digest(d3, payload, set(), set(), TODAY)
    findings = run.validate_digest(d3, payload=payload, today=TODAY, check_links=False)
    check("mass unsourced is critical", any("UNSOURCED CRITICAL" in f for f in findings), str(findings))
    check("source normalisation", run._normalize_source("Reuters China") == run._normalize_source("Reuters"))


def test_ledger_roundtrip(tmp_name="published_ledger.smoke.json"):
    section("run.py ledger")
    import run
    from pathlib import Path
    orig = run.LEDGER_JSON
    run.LEDGER_JSON = Path(tmp_name)
    try:
        d = make_digest()
        run._record_ledger(d, "2026-09-03")
        entries = run._load_ledger()
        check("ledger written", len(entries) >= 3)
        urls, titles, heads = run._ledger_recent(entries, TODAY)
        check("ledger recent excludes nothing for yesterday", len(urls) >= 2 and len(heads) >= 2)
        urls_t, _, _ = run._ledger_recent(entries, date(2026, 9, 3))
        check("same-day entries excluded", not urls_t)
    finally:
        try:
            Path(tmp_name).unlink()
        except OSError:
            pass
        run.LEDGER_JSON = orig


def test_render():
    section("render.py")
    import run, render
    payload = make_payload()
    d, _ = run._postprocess_digest(make_digest(), payload, set(), set(), TODAY)
    d["market_indicators"] = payload["market_indicators"]
    html = render.render_html(d)
    check("html renders", len(html) > 20000, str(len(html)))
    check("official line section rendered", "What Beijing Is Saying" in html and "中方敦促美方" in html)
    check("disclaimer footer", "generated automatically" in html)
    # Format order: the frame and the news come before the data strip.
    i_note, i_top, i_mkt = html.find("The Bottom Line"), html.find("Top Stories"), html.find("SSE Composite")
    check("editor_note rendered as The Bottom Line", i_note > 0)
    check("bottom line above top stories", 0 < i_note < i_top, f"{i_note} vs {i_top}")
    check("market strip below the news", i_top < i_mkt, f"top {i_top} vs markets {i_mkt}")
    d["web_url"] = "https://example.org/2026-09-04.html"
    d["pdf_url"] = "https://example.org/2026-09-04.pdf"
    d["archive_url"] = "https://example.org/archive.html"
    html2 = render.render_html(d)
    check("online / print / archive links", all(s in html2 for s in ("Read online", "Print / PDF", "Archive")))
    check("no placeholder links", 'href="#"' not in html.replace('href="#top"', ""))
    check("unavailable market shows dash", "1.75%" not in html)
    check("repaired scmp link present", "scarborough" in html)


def test_word_count_is_one_definition():
    section("wordcount.py (single length definition)")
    import wordcount, run, digest, render
    payload = make_payload()
    d, _ = run._postprocess_digest(make_digest(), payload, set(), set(), TODAY)
    a, b, c = run._count_words(d), digest._count_digest_words(d), render._word_count(d)
    check("validator, prompt target and header agree", a == b == c, f"run={a} digest={b} render={c}")
    check("count is non-trivial", a > 100, str(a))
    check("empty digest counts zero", wordcount.count_words({}) == 0)
    check("None-safe", wordcount.count_words(None) == 0)
    check("list fields counted", wordcount.count_words({"opeds_today": [{"authors": ["a b", "c"]}]}) == 3)
    # official_line carries a lot of prose; it must be inside the definition, or
    # the model writes to a target the gate does not measure (run 114: 1,787 vs 2,253).
    only_official = wordcount.count_words(
        {"official_line": [{"statement": "one two three four", "context": "five six"}]})
    check("official_line prose is counted", only_official == 6, str(only_official))
    check("editor_note is counted", wordcount.count_words({"editor_note": "a b c"}) == 3)


def test_state_merge():
    section("merge_state.py (concurrent-run state)")
    import merge_state
    fh = merge_state.merge_feed_health(
        {"Reuters China": {"last_seen": "2026-09-05", "last_count": 100, "empty_runs": 0},
         "Only Mine": {"last_seen": "2026-09-05", "last_count": 7}},
        {"Reuters China": {"last_seen": "2026-09-04", "last_count": 0, "empty_runs": 2},
         "Only Theirs": {"last_seen": "2026-09-04", "last_count": 3}})
    check("newer measurement wins", fh["Reuters China"]["last_count"] == 100)
    check("remote-only feed kept", fh["Only Theirs"]["last_count"] == 3)
    check("local-only feed kept", fh["Only Mine"]["last_count"] == 7)
    check("older local does not clobber newer remote",
          merge_state.merge_feed_health({"A": {"last_seen": "2026-09-01", "last_count": 0}},
                                        {"A": {"last_seen": "2026-09-04", "last_count": 50}}
                                        )["A"]["last_count"] == 50)
    uc = merge_state.merge_url_cache({"g1": "https://a", "g2": "https://b"},
                                     {"g1": "https://a", "g3": "https://c"})
    check("url cache is a union", uc == {"g1": "https://a", "g2": "https://b", "g3": "https://c"}, str(uc))
    mm = merge_state.merge_metrics(['{"d":2}'], ['{"d":1}', '{"d":2}'])
    check("metrics union without duplicates", mm == ['{"d":1}', '{"d":2}'], str(mm))
    wf = open(".github/workflows/daily-digest.yml", encoding="utf-8").read()
    check("workflow never rebases state", "git rebase" not in wf)
    check("both state steps merge", wf.count("merge_state.py") == 2, str(wf.count("merge_state.py")))
    check("state steps set a git identity", wf.count('git config user.name') == 2)


def test_email_size_guard():
    section("email size guard (Gmail clipping)")
    import run
    check("headroom below the warn line", run.check_email_size("x" * 50_000) == [])
    warn = run.check_email_size("x" * (run.EMAIL_BYTES_WARN + 100))
    check("warns before Gmail clips", warn and "CRITICAL" not in warn[0], str(warn))
    crit = run.check_email_size("x" * (run.EMAIL_BYTES_CRITICAL + 100))
    check("blocks before Gmail clips", crit and "CRITICAL" in crit[0], str(crit))
    check("critical threshold under Gmail's limit", run.EMAIL_BYTES_CRITICAL < run.GMAIL_CLIP_BYTES)
    # Multibyte safety: the Chinese in official_line costs 3 bytes per char, so
    # the guard must measure encoded bytes, not str length.
    zh = "中" * 40_000                       # 40k chars, 120k bytes
    check("counts UTF-8 bytes, not characters",
          "CRITICAL" in (run.check_email_size(zh) or [""])[0])
    check("word ceiling leaves byte headroom",
          run.WORD_CEILING * 30 < run.EMAIL_BYTES_CRITICAL,
          f"{run.WORD_CEILING} words x ~30 B/word vs {run.EMAIL_BYTES_CRITICAL}")


def test_archive_and_pdf():
    section("archive index + pdf export")
    import run, pdf_export
    html = run._build_archive_index([
        {"date": "2026-09-04", "re_line": "Rare-earth curbs · PLA sorties", "word_count": 2310, "pdf": True},
        {"date": "2026-09-03", "re_line": "Xi in Hanoi", "word_count": 2105, "pdf": False},
    ])
    check("archive index lists issues", "2026-09-04.html" in html and "2026-09-03.html" in html)
    check("archive index links pdf only when present", html.count(".pdf") == 1)
    check("archive index has latest link", "index.html" in html)
    check("web base default", run._web_base().startswith("https://"))
    check("pdf export degrades without browser", callable(pdf_export.export_pdf))
    src = open("render.py", encoding="utf-8").read()
    check("print stylesheet present", "@media print" in src and "no-print" in src)


def test_health():
    section("pipeline_health.py")
    import pipeline_health
    payload = make_payload()
    payload["tier1"] = payload["tier1"][:2]
    payload["resolve_stats"] = {"resolved": 1, "cached": 0, "failed": 40, "budget_hit": 0, "gnews_total": 41}
    rep = pipeline_health.check(payload, make_digest())
    check("thin corpus alert", any("CORPUS" in a for a in rep["alerts"]), str(rep))
    check("resolve collapse alert", any("RESOLVE" in a for a in rep["alerts"]), str(rep))


def test_workflow_and_docs():
    section("workflow + docs")
    wf = open(".github/workflows/daily-digest.yml", encoding="utf-8").read()
    check("guard step", "last_sent.txt" in wf)
    check("failure alert", "Send failure alert" in wf)
    check("staggered crons", wf.count("- cron:") >= 4)
    check("test mode input", "send_to" in wf and "smoke_test.py" in wf)
    check("state files committed", all(f in wf for f in ("published_ledger.json", "url_cache.json", "feed_health.json")))
    req = open("requirements.txt", encoding="utf-8").read()
    check("anthropic 1.x floor", "anthropic>=1" in req)
    try:
        import list_sources
        generated = list_sources.build()
        current = open("SOURCES.md", encoding="utf-8").read()
        check("SOURCES.md up to date (run python list_sources.py)", generated.strip() == current.strip())
    except FileNotFoundError:
        check("SOURCES.md exists", False, "run python list_sources.py")


if __name__ == "__main__":
    for t in (test_resolve, test_fulltext, test_collect_registry, test_digest_module,
              test_run_postprocess_and_validate, test_ledger_roundtrip, test_render,
              test_word_count_is_one_definition, test_state_merge,
              test_email_size_guard, test_archive_and_pdf,
              test_health, test_workflow_and_docs):
        try:
            t()
        except Exception as e:                               # noqa: BLE001
            FAILURES.append(f"{t.__name__}: crashed: {e}")
            traceback.print_exc()
    print(f"\n{PASSED} checks passed, {len(FAILURES)} failed")
    if FAILURES:
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print("smoke tests OK")
